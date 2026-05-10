"""PDF converter — maps PyMuPDF page content to IR blocks.

Supported mappings:

* Text blocks (sorted for reading order)  → :class:`HeadingBlock` / :class:`ParagraphBlock`
* Tables (via PyMuPDF table finder)        → :class:`TableBlock`
* Raster images                            → :class:`EmbeddedAsset` + :class:`ImageBlock`
* Vector path clusters (get_drawings)      → PNG via get_pixmap(clip=bbox)
                                             → :class:`EmbeddedAsset` + :class:`ImageBlock`
* Unrenderable elements                    → :class:`UnsupportedBlock`

Heuristics applied:
* Page numbers, headers, and footers (text near top/bottom margins, short
  numeric-only text) are skipped.
* Multi-column layouts are linearized by sorting blocks first by y-band then
  by x position within each band.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import fitz  # PyMuPDF
except ImportError as _fitz_err:  # pragma: no cover
    raise ImportError(
        "PyMuPDF is required for PDFConverter. Install it with: pip install PyMuPDF"
    ) from _fitz_err

from document2markdown.config import RASTER_DPI
from document2markdown.converter_base import BaseConverter
from document2markdown.document_model import (
    ConversionResult,
    EmbeddedAsset,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
    UnsupportedBlock,
)

if TYPE_CHECKING:
    from document2markdown.document_model import Block

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic constants
# ---------------------------------------------------------------------------

# Fraction of page height treated as header/footer zone (top and bottom).
_MARGIN_FRACTION: float = 0.07

# Maximum character count for a text span to be considered a page number.
# Covers patterns up to "Page 9999 of 99999" (19 chars).
_PAGE_NUMBER_MAX_LEN: int = 20

# Regex that matches typical page-number text: digits, "Page N", "N of M", etc.
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*$", re.IGNORECASE
)

# Minimum font size (points) to be considered a heading candidate.
_HEADING_MIN_SIZE: float = 13.0

# Font size thresholds for heading levels (descending).
# Blocks whose dominant font size is >= threshold are mapped to that level.
_HEADING_LEVELS: list[tuple[float, int]] = [
    (28.0, 1),
    (22.0, 2),
    (18.0, 3),
    (15.0, 4),
    (13.0, 5),
]

# Y-band tolerance for grouping blocks into the same "row" during
# multi-column linearization (fraction of page height).
_YBAND_TOLERANCE: float = 0.015

# Minimum area (pt²) for a vector cluster to be extracted as an image.
# Tiny clusters (hairlines, borders) are skipped.
_MIN_VECTOR_AREA: float = 400.0

# Maximum fraction of page area a vector cluster may occupy.
# Clusters larger than this are likely backgrounds/decorations and are skipped.
_MAX_VECTOR_PAGE_FRACTION: float = 0.6

# Proximity threshold (points) for merging adjacent drawing bounding boxes
# into a single vector cluster.
_CLUSTER_PROXIMITY: float = 8.0

# Minimum dimension (points) for a raster image to be extracted.
# Images smaller than this in either width or height are skipped as
# decorative elements (icons, bullets, spacers).  50pt ≈ 0.7 inches.
_MIN_IMAGE_DIM: float = 50.0


# ---------------------------------------------------------------------------
# Bounding-box helpers
# ---------------------------------------------------------------------------

def _bbox_area(bbox: fitz.Rect) -> float:
    return max(0.0, bbox.width) * max(0.0, bbox.height)


def _bbox_expand(a: fitz.Rect, b: fitz.Rect) -> fitz.Rect:
    """Return the smallest rect that contains both *a* and *b*."""
    return fitz.Rect(
        min(a.x0, b.x0),
        min(a.y0, b.y0),
        max(a.x1, b.x1),
        max(a.y1, b.y1),
    )


def _bboxes_close(a: fitz.Rect, b: fitz.Rect, threshold: float) -> bool:
    """Return True if the two rects are within *threshold* points of each other."""
    # Check horizontal and vertical gaps
    h_gap = max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1))
    v_gap = max(0.0, max(a.y0, b.y0) - min(a.y1, b.y1))
    return h_gap <= threshold and v_gap <= threshold


# ---------------------------------------------------------------------------
# Vector cluster grouping
# ---------------------------------------------------------------------------

def _cluster_drawings(drawings: list[dict], proximity: float) -> list[fitz.Rect]:
    """Group drawing path bounding boxes into spatial clusters.

    Uses a simple single-pass greedy merge: each new drawing is merged into
    the first existing cluster it is close to; otherwise it starts a new one.

    Returns a list of merged bounding-box :class:`fitz.Rect` objects.
    """
    clusters: list[fitz.Rect] = []

    for d in drawings:
        raw = d.get("rect")
        if raw is None:
            continue
        bbox = fitz.Rect(raw)
        if bbox.is_empty or bbox.is_infinite:
            continue

        merged = False
        for i, cluster_bbox in enumerate(clusters):
            if _bboxes_close(cluster_bbox, bbox, proximity):
                clusters[i] = _bbox_expand(cluster_bbox, bbox)
                merged = True
                break
        if not merged:
            clusters.append(bbox)

    return clusters


# ---------------------------------------------------------------------------
# Header / footer / page-number heuristics
# ---------------------------------------------------------------------------

def _is_header_footer(bbox: fitz.Rect, page_height: float) -> bool:
    """Return True if *bbox* falls within the top or bottom margin zone."""
    margin = page_height * _MARGIN_FRACTION
    return bbox.y1 <= margin or bbox.y0 >= page_height - margin


def _is_page_number(text: str) -> bool:
    """Return True if *text* looks like a page number."""
    stripped = text.strip()
    if len(stripped) > _PAGE_NUMBER_MAX_LEN:
        return False
    return bool(_PAGE_NUMBER_RE.match(stripped))


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

def _dominant_font_size(block: dict) -> float:
    """Return the largest font size found in a text block's spans."""
    max_size = 0.0
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            size = span.get("size", 0.0)
            if size > max_size:
                max_size = size
    return max_size


def _is_bold(block: dict) -> bool:
    """Return True if any span in the block uses a bold font."""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            flags = span.get("flags", 0)
            # PyMuPDF font flags: bit 4 (0x10) = bold
            if flags & 0x10:
                return True
    return False


def _font_size_to_heading_level(size: float) -> int | None:
    """Map a font size to a heading level (1–5), or None if not a heading."""
    for threshold, level in _HEADING_LEVELS:
        if size >= threshold:
            return level
    return None


# ---------------------------------------------------------------------------
# Bullet / numbered list detection
# ---------------------------------------------------------------------------

# Bullet characters that indicate an unordered list item.
_BULLET_CHARS: set[str] = {"•", "●", "○", "■", "□", "▪", "▸", "▹", "‣", "⁃"}

# Pattern for numbered list items: "1.", "2)", "(a)", etc.
_NUMBERED_RE = re.compile(r"^(\d+[\.\)]\s|[\(\[]?\d+[\)\]]\s|\(?[a-z][\)\.])")


def _extract_list_items(lines: list[str]) -> tuple[bool, list[str]] | None:
    """Detect if *lines* form a bullet or numbered list.

    Returns ``(ordered, items)`` if the block looks like a list, or ``None``
    if it does not.  A block is considered a list if the majority of its
    lines start with a bullet character or a numbered pattern.
    """
    if len(lines) < 2:
        return None

    bullet_count = 0
    numbered_count = 0

    for line in lines:
        first_char = line[0] if line else ""
        if first_char in _BULLET_CHARS:
            bullet_count += 1
        elif _NUMBERED_RE.match(line):
            numbered_count += 1

    total = len(lines)
    # Require at least half the lines to be list items
    if bullet_count >= total * 0.5:
        # Unordered list — strip the bullet character from each item
        items: list[str] = []
        for line in lines:
            if line and line[0] in _BULLET_CHARS:
                items.append(line[1:].strip())
            else:
                # Non-bullet line: append to previous item if exists
                if items:
                    items[-1] += " " + line
                else:
                    items.append(line)
        return (False, items)

    if numbered_count >= total * 0.5:
        # Ordered list — strip the number prefix from each item
        items = []
        for line in lines:
            m = _NUMBERED_RE.match(line)
            if m:
                items.append(line[m.end():].strip())
            else:
                if items:
                    items[-1] += " " + line
                else:
                    items.append(line)
        return (True, items)

    return None


# ---------------------------------------------------------------------------
# Multi-column linearization
# ---------------------------------------------------------------------------

def _linearize_blocks(blocks: list[dict], page_height: float) -> list[dict]:
    """Sort text/image blocks into single reading order.

    Strategy:
    1. Group blocks into horizontal bands by y-coordinate proximity.
    2. Within each band, sort by x0 (left-to-right).
    3. Bands are ordered top-to-bottom.

    This handles two-column layouts where left-column blocks interleave with
    right-column blocks in raw extraction order.
    """
    if not blocks:
        return blocks

    band_tolerance = page_height * _YBAND_TOLERANCE

    # Assign each block to a band based on its y0
    bands: list[list[dict]] = []
    band_y: list[float] = []

    for block in blocks:
        bbox = fitz.Rect(block["bbox"])
        y0 = bbox.y0
        placed = False
        for i, by in enumerate(band_y):
            if abs(y0 - by) <= band_tolerance:
                bands[i].append(block)
                # Update band representative y to average
                band_y[i] = (band_y[i] + y0) / 2.0
                placed = True
                break
        if not placed:
            bands.append([block])
            band_y.append(y0)

    # Sort bands top-to-bottom, blocks within each band left-to-right
    sorted_pairs = sorted(zip(band_y, bands), key=lambda p: p[0])
    result: list[dict] = []
    for _, band_blocks in sorted_pairs:
        band_blocks.sort(key=lambda b: fitz.Rect(b["bbox"]).x0)
        result.extend(band_blocks)

    return result


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

class PDFConverter(BaseConverter):
    """Convert a ``.pdf`` file to a :class:`ConversionResult`.

    Parameters
    ----------
    raster_dpi:
        DPI used when rasterizing vector graphics as a last resort.
    """

    def __init__(self, raster_dpi: int = RASTER_DPI) -> None:
        self._raster_dpi = raster_dpi
        self._body_font_size: float = 12.0  # updated per-document in convert()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def convert(self, source_path: Path) -> ConversionResult:
        """Convert *source_path* (.pdf) to a :class:`ConversionResult`."""
        blocks: list[Block] = []
        embedded: list[EmbeddedAsset] = []
        warnings: list[str] = []

        try:
            doc = fitz.open(str(source_path))
        except Exception as exc:
            msg = f"failed to open PDF '{source_path}': {exc}"
            logger.error(msg)
            warnings.append(msg)
            return ConversionResult(blocks=[], embedded=[], warnings=warnings)

        try:
            # First pass: compute the document's median body font size so
            # heading detection can use relative thresholds.
            self._body_font_size = self._compute_body_font_size(doc)

            for page_num in range(len(doc)):
                page = doc[page_num]
                self._process_page(page, blocks, embedded, warnings)
        finally:
            doc.close()

        return ConversionResult(blocks=blocks, embedded=embedded, warnings=warnings)

    @staticmethod
    def _compute_body_font_size(doc: fitz.Document) -> float:
        """Estimate the dominant body font size across the document.

        Collects font sizes weighted by character count and returns the mode
        (most common size).  Falls back to 12.0 if no text is found.
        """
        size_counts: dict[float, int] = {}
        # Sample up to 20 pages for performance on large documents.
        sample_pages = min(len(doc), 20)
        for page_num in range(sample_pages):
            page = doc[page_num]
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text.strip():
                            continue
                        size = round(span.get("size", 0), 1)
                        if size > 0:
                            size_counts[size] = size_counts.get(size, 0) + len(text)

        if not size_counts:
            return 12.0

        # The body font size is the one with the most total characters.
        return max(size_counts, key=size_counts.get)  # type: ignore[arg-type]

    def _relative_heading_level(self, font_size: float) -> int | None:
        """Determine heading level relative to the document's body font size.

        A block is only considered a heading if its font size is significantly
        larger than the body text.  This prevents presentation PDFs (where body
        text is 24pt+) from classifying everything as headings.

        Ratios:
          >= 2.0x body → H1
          >= 1.6x body → H2
          >= 1.3x body → H3
          >= 1.15x body → H4

        Also requires the font to be bold for borderline cases (1.15-1.3x).
        """
        body = self._body_font_size
        if body <= 0:
            # Fallback to absolute thresholds
            return _font_size_to_heading_level(font_size)

        ratio = font_size / body

        if ratio >= 2.0:
            return 1
        if ratio >= 1.6:
            return 2
        if ratio >= 1.3:
            return 3
        if ratio >= 1.15:
            return 4
        return None

    # ------------------------------------------------------------------
    # Per-page processing
    # ------------------------------------------------------------------

    def _process_page(
        self,
        page: fitz.Page,
        blocks: list[Block],
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> None:
        """Extract all content from *page* and append to *blocks*/*embedded*."""
        page_rect = page.rect
        page_height = page_rect.height

        # ------------------------------------------------------------------
        # 1. Extract vector clusters first (so we know which regions to skip
        #    when processing text/image blocks).
        # ------------------------------------------------------------------
        vector_bboxes = self._extract_vector_clusters(
            page, page_height, blocks, embedded, warnings
        )

        # ------------------------------------------------------------------
        # 2. Extract tables via PyMuPDF's table finder.
        # ------------------------------------------------------------------
        table_bboxes = self._extract_tables(page, blocks, warnings)

        # ------------------------------------------------------------------
        # 3. Extract raw text/image blocks and linearize reading order.
        # ------------------------------------------------------------------
        raw_dict = page.get_text("dict")
        raw_blocks = raw_dict.get("blocks", [])
        raw_blocks = _linearize_blocks(raw_blocks, page_height)

        for block in raw_blocks:
            bbox = fitz.Rect(block["bbox"])

            # Skip header/footer zones
            if _is_header_footer(bbox, page_height):
                continue

            # Skip regions already covered by a table
            if any(bbox.intersects(tb) for tb in table_bboxes):
                continue

            # Skip regions already covered by a vector cluster image
            if any(bbox.intersects(vb) for vb in vector_bboxes):
                continue

            block_type = block.get("type", -1)

            if block_type == 0:  # text block
                self._process_text_block(block, blocks, warnings)
            elif block_type == 1:  # image block
                self._process_image_block(block, page, embedded, blocks, warnings)
            # type 2 = drawing (handled separately via get_drawings)

    # ------------------------------------------------------------------
    # Vector cluster extraction
    # ------------------------------------------------------------------

    def _extract_vector_clusters(
        self,
        page: fitz.Page,
        page_height: float,
        blocks: list[Block],
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> list[fitz.Rect]:
        """Detect vector path clusters and export each as PNG.

        Appends :class:`ImageBlock` entries to *blocks* for each cluster and
        returns the list of bounding boxes that were successfully extracted
        (so callers can skip overlapping text/image blocks).
        """
        extracted_bboxes: list[fitz.Rect] = []

        try:
            drawings = page.get_drawings()
        except Exception as exc:
            warnings.append(f"get_drawings() failed on page {page.number}: {exc}")
            return extracted_bboxes

        if not drawings:
            return extracted_bboxes

        clusters = _cluster_drawings(drawings, _CLUSTER_PROXIMITY)
        page_area = page.rect.width * page.rect.height

        for cluster_bbox in clusters:
            # Skip tiny clusters (hairlines, borders, decorative rules)
            if _bbox_area(cluster_bbox) < _MIN_VECTOR_AREA:
                continue

            # Skip clusters that cover too much of the page (backgrounds,
            # decorations, full-page borders).  These would occlude text.
            if page_area > 0 and _bbox_area(cluster_bbox) / page_area > _MAX_VECTOR_PAGE_FRACTION:
                continue

            # Skip clusters in header/footer zones
            if _is_header_footer(cluster_bbox, page_height):
                continue

            image_block = self._export_vector_cluster(
                page, cluster_bbox, embedded, warnings
            )
            if image_block is not None:
                blocks.append(image_block)
                extracted_bboxes.append(cluster_bbox)

        return extracted_bboxes

    def _export_vector_cluster(
        self,
        page: fitz.Page,
        bbox: fitz.Rect,
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> ImageBlock | None:
        """Export a vector cluster region as PNG and emit an ImageBlock.

        Uses ``page.get_pixmap(clip=bbox)`` to rasterize the cluster region
        at the configured DPI.  PyMuPDF's ``get_svg_image()`` does not support
        a ``clip`` parameter, so rasterization is the reliable path for
        extracting individual vector regions from a page.
        """
        try:
            # Scale matrix: default page resolution is 72 DPI; scale up to
            # raster_dpi for high-quality output.
            scale = self._raster_dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=mat, clip=bbox)
            png_bytes: bytes = pixmap.tobytes("png")
        except Exception as exc:
            warnings.append(
                f"get_pixmap() failed for cluster on page {page.number}: {exc}"
            )
            return None

        if not png_bytes:
            return None

        asset = EmbeddedAsset(
            data=png_bytes,
            extension=".png",
            original_name=None,
            alt_text="vector figure",
            source_vector_format=None,
        )
        idx = len(embedded)
        embedded.append(asset)
        return ImageBlock(asset_index=idx, alt=asset.alt_text)

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    def _extract_tables(
        self,
        page: fitz.Page,
        blocks: list[Block],
        warnings: list[str],
    ) -> list[fitz.Rect]:
        """Extract tables from *page* using PyMuPDF's table finder.

        Returns the bounding boxes of extracted tables so overlapping text
        blocks can be skipped.
        """
        table_bboxes: list[fitz.Rect] = []

        try:
            tabs = page.find_tables()
        except Exception as exc:
            warnings.append(f"find_tables() failed on page {page.number}: {exc}")
            return table_bboxes

        for tab in tabs:
            try:
                df = tab.to_pandas()
                if df.empty:
                    continue
                headers = [str(c) for c in df.columns.tolist()]
                rows = [
                    [str(cell) if cell is not None else "" for cell in row]
                    for row in df.values.tolist()
                ]
                blocks.append(TableBlock(headers=headers, rows=rows))
                table_bboxes.append(fitz.Rect(tab.bbox))
            except Exception as exc:
                warnings.append(
                    f"table extraction failed on page {page.number}: {exc}"
                )

        return table_bboxes

    # ------------------------------------------------------------------
    # Text block processing
    # ------------------------------------------------------------------

    def _process_text_block(
        self,
        block: dict,
        blocks: list[Block],
        warnings: list[str],
    ) -> None:
        """Convert a PyMuPDF text block dict to one or more IR blocks."""
        # Collect all text from the block, preserving line boundaries.
        lines_text: list[str] = []
        for line in block.get("lines", []):
            line_parts: list[str] = []
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    # rawdict mode: reconstruct from individual char dicts
                    text = "".join(ch.get("c", "") for ch in span.get("chars", []))
                if text:
                    line_parts.append(text)
            line_str = "".join(line_parts).strip()
            if line_str:
                lines_text.append(line_str)

        if not lines_text:
            return

        # Skip page numbers (check the joined text)
        full_text = " ".join(lines_text).strip()
        if _is_page_number(full_text):
            return

        # --- Detect bullet/numbered lists ---
        # Check if lines start with bullet characters or numbered patterns.
        bullet_items = _extract_list_items(lines_text)
        if bullet_items is not None:
            ordered, items = bullet_items
            blocks.append(ListBlock(ordered=ordered, items=items))
            return

        # --- Heading or paragraph ---
        font_size = _dominant_font_size(block)
        heading_level = self._relative_heading_level(font_size)

        if heading_level is not None:
            blocks.append(HeadingBlock(level=heading_level, text=full_text))
        else:
            blocks.append(ParagraphBlock(text=full_text))

    # ------------------------------------------------------------------
    # Raster image block processing
    # ------------------------------------------------------------------

    def _process_image_block(
        self,
        block: dict,
        page: fitz.Page,
        embedded: list[EmbeddedAsset],
        blocks: list[Block],
        warnings: list[str],
    ) -> None:
        """Extract a raster image from a PyMuPDF image block."""
        # Skip tiny images (icons, bullets, spacers, decorative elements).
        bbox = block.get("bbox", (0, 0, 0, 0))
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < _MIN_IMAGE_DIM or height < _MIN_IMAGE_DIM:
            return

        # block["image"] contains the raw image bytes in dict mode
        image_data: bytes | None = block.get("image")
        if not image_data:
            # Fallback: try to get image via xref
            xref = block.get("xref", 0)
            if xref > 0:
                image_data = self._extract_image_by_xref(page, xref, warnings)

        if not image_data:
            warnings.append(
                f"image block on page {page.number} has no extractable data"
            )
            return

        ext = _colorspace_to_ext(block)
        asset = EmbeddedAsset(
            data=image_data,
            extension=ext,
            original_name=None,
            alt_text="image",
            source_vector_format=None,
        )
        idx = len(embedded)
        embedded.append(asset)
        blocks.append(ImageBlock(asset_index=idx, alt=asset.alt_text))

    def _extract_image_by_xref(
        self,
        page: fitz.Page,
        xref: int,
        warnings: list[str],
    ) -> bytes | None:
        """Extract image bytes from the PDF by cross-reference number."""
        try:
            doc = page.parent
            img_info = doc.extract_image(xref)
            if img_info:
                return img_info.get("image")
        except Exception as exc:
            warnings.append(f"extract_image(xref={xref}) failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _colorspace_to_ext(block: dict) -> str:
    """Guess a file extension from the image block's colorspace / ext field."""
    # PyMuPDF rawdict image blocks may carry an "ext" key
    ext_hint: str = block.get("ext", "")
    if ext_hint:
        return f".{ext_hint.lstrip('.')}"

    cs: str = (block.get("colorspace", "") or "").lower()
    if "jpeg" in cs or "jpg" in cs:
        return ".jpg"
    if "png" in cs:
        return ".png"
    return ".png"  # safe default
