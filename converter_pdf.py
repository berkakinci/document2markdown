"""PDF converter — maps PyMuPDF page content to IR blocks.

Supported mappings:

* Text blocks (sorted for reading order)  → :class:`HeadingBlock` / :class:`ParagraphBlock`
* Tables (via PyMuPDF table finder)        → :class:`TableBlock`
* Raster images                            → :class:`EmbeddedAsset` + :class:`ImageBlock`
* Vector path clusters (get_drawings)      → SVG via get_svg_image → :class:`VectorConverter`
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
from document2markdown.converter_vector import VectorConverter, VectorConversionError
from document2markdown.document_model import (
    ConversionResult,
    EmbeddedAsset,
    HeadingBlock,
    ImageBlock,
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

# Proximity threshold (points) for merging adjacent drawing bounding boxes
# into a single vector cluster.
_CLUSTER_PROXIMITY: float = 8.0


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
        self._vector = VectorConverter(raster_dpi=raster_dpi)

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
            for page_num in range(len(doc)):
                page = doc[page_num]
                self._process_page(page, blocks, embedded, warnings)
        finally:
            doc.close()

        return ConversionResult(blocks=blocks, embedded=embedded, warnings=warnings)

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
        raw_dict = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
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
        """Detect vector path clusters and export each as SVG.

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

        for cluster_bbox in clusters:
            # Skip tiny clusters (hairlines, borders, decorative rules)
            if _bbox_area(cluster_bbox) < _MIN_VECTOR_AREA:
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
        """Export a vector cluster region as SVG and emit an ImageBlock."""
        try:
            svg_bytes: bytes = page.get_svg_image(clip=bbox).encode("utf-8")
        except Exception as exc:
            warnings.append(
                f"get_svg_image() failed for cluster on page {page.number}: {exc}"
            )
            return None

        if not svg_bytes:
            return None

        # Pass through VectorConverter for normalization.
        # The SVG from PyMuPDF is already valid SVG, but VectorConverter may
        # apply additional cleanup.  We treat it as source_format="svg" so
        # cairosvg's svg2svg path is tried first.
        try:
            out_bytes, ext = self._vector.convert(svg_bytes, "svg")  # type: ignore[arg-type]
        except VectorConversionError:
            # VectorConverter already logged a warning; use raw SVG directly.
            out_bytes = svg_bytes
            ext = ".svg"
        except Exception as exc:
            warnings.append(
                f"VectorConverter failed for cluster on page {page.number}: {exc}"
            )
            out_bytes = svg_bytes
            ext = ".svg"

        asset = EmbeddedAsset(
            data=out_bytes,
            extension=ext,
            original_name=None,
            alt_text="vector figure",
            source_vector_format="svg",
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
        # Collect all text from the block.
        # In rawdict mode PyMuPDF stores characters in the "chars" list and
        # leaves span["text"] empty.  Fall back to joining chars when needed.
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

        full_text = " ".join(lines_text).strip()
        if not full_text:
            return

        # Skip page numbers
        if _is_page_number(full_text):
            return

        # Determine if this block looks like a heading
        font_size = _dominant_font_size(block)
        heading_level = _font_size_to_heading_level(font_size)

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
        # block["image"] contains the raw image bytes in rawdict mode
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
