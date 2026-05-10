"""PDF converter — maps pymupdf4llm layout boxes to IR blocks.

Uses pymupdf4llm's neural-network-based document layout analysis:

* ``parse_document()`` classifies page content into typed LayoutBoxes
  (title, section-header, text, list-item, picture, table, caption,
  page-header, page-footer, footnote).
* ``IdentifyHeaders`` assigns heading levels based on font-size analysis
  across the entire document.

Supported mappings:

* title / section-header  → :class:`HeadingBlock`
* text / caption / footnote → :class:`ParagraphBlock`
* list-item (consecutive) → :class:`ListBlock`
* picture                 → :class:`EmbeddedAsset` + :class:`ImageBlock`
* table                   → :class:`TableBlock`
* page-header / page-footer → *(skipped)*
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

try:
    from pymupdf4llm.helpers.document_layout import parse_document
    from pymupdf4llm.helpers.pymupdf_rag import IdentifyHeaders
except ImportError as _llm_err:  # pragma: no cover
    raise ImportError(
        "pymupdf4llm is required for PDFConverter. "
        "Install it with: pip install pymupdf4llm"
    ) from _llm_err

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
)

if TYPE_CHECKING:
    from document2markdown.document_model import Block

logger = logging.getLogger(__name__)

# Pattern for detecting ordered list items: "1.", "2)", "(a)", etc.
_NUMBERED_RE = re.compile(r"^\s*(?:\d+[\.\)]\s|[\(\[]?\d+[\)\]]\s|\(?[a-z][\)\.])")


# ---------------------------------------------------------------------------
# Helper: ordered list detection
# ---------------------------------------------------------------------------

def _detect_ordered(items: list[str]) -> bool:
    """Return True if the list items appear to be an ordered (numbered) list.

    Checks whether the majority of items start with a numbered pattern
    (e.g. "1.", "2)", "(a)").
    """
    if not items:
        return False
    numbered_count = sum(1 for item in items if _NUMBERED_RE.match(item))
    return numbered_count > len(items) / 2


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

class PDFConverter(BaseConverter):
    """Convert a ``.pdf`` file to a :class:`ConversionResult`.

    Uses pymupdf4llm's ``parse_document()`` for layout classification and
    ``IdentifyHeaders`` for heading level assignment.

    Parameters
    ----------
    raster_dpi:
        DPI used when extracting embedded images from the PDF.
    """

    def __init__(self, raster_dpi: int = RASTER_DPI) -> None:
        self._raster_dpi = raster_dpi

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
            # Build heading level map from font-size analysis.
            header_map = self._build_header_map(doc, warnings)

            # Run layout analysis to get classified boxes per page.
            try:
                parsed = parse_document(
                    doc, embed_images=True, image_dpi=self._raster_dpi
                )
                # parsed is a ParsedDocument with .pages; each page has .boxes
                pages_boxes = [page.boxes for page in parsed.pages]
            except Exception as exc:
                msg = f"parse_document() failed for '{source_path}': {exc}"
                logger.error(msg)
                warnings.append(msg)
                return ConversionResult(blocks=[], embedded=[], warnings=warnings)

            # Map layout boxes to IR blocks.
            self._map_boxes_to_blocks(
                pages_boxes, header_map, blocks, embedded, warnings
            )
        finally:
            doc.close()

        return ConversionResult(blocks=blocks, embedded=embedded, warnings=warnings)

    # ------------------------------------------------------------------
    # Header map construction
    # ------------------------------------------------------------------

    def _build_header_map(
        self, doc: fitz.Document, warnings: list[str]
    ) -> dict[float, int]:
        """Use IdentifyHeaders to build a font_size → heading_level mapping.

        Returns a dict mapping font sizes (as floats) to heading levels (1–6).
        On failure, returns an empty dict and appends a warning.
        """
        try:
            hdr = IdentifyHeaders(doc)
            # hdr.header_id is dict: {font_size_int: "# " or "## " etc}
            header_map: dict[float, int] = {}
            for font_size, prefix in hdr.header_id.items():
                # Count the number of '#' characters to determine level
                level = prefix.count("#")
                if 1 <= level <= 6:
                    header_map[float(font_size)] = level
            return header_map
        except Exception as exc:
            msg = f"IdentifyHeaders failed: {exc}"
            logger.warning(msg)
            warnings.append(msg)
            return {}

    # ------------------------------------------------------------------
    # Box-to-block mapping
    # ------------------------------------------------------------------

    def _map_boxes_to_blocks(
        self,
        pages_boxes: list[list],
        header_map: dict[float, int],
        blocks: list[Block],
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> None:
        """Convert LayoutBoxes to IR blocks.

        Iterates over per-page box lists, dispatching each box to the
        appropriate handler. Consecutive list-items are accumulated into
        a single ListBlock.
        """
        list_accumulator: list[str] = []

        for page_boxes in pages_boxes:
            for box in page_boxes:
                try:
                    # Skip page headers and footers
                    if box.boxclass in ("page-header", "page-footer"):
                        continue

                    # If this is not a list-item, flush any accumulated items
                    if box.boxclass != "list-item" and list_accumulator:
                        blocks.append(
                            ListBlock(
                                ordered=_detect_ordered(list_accumulator),
                                items=list_accumulator,
                            )
                        )
                        list_accumulator = []

                    self._map_single_box(
                        box, header_map, blocks, embedded, list_accumulator, warnings
                    )
                except Exception as exc:
                    warnings.append(
                        f"failed to process box (class={getattr(box, 'boxclass', '?')}): {exc}"
                    )

            # Flush any remaining list items at end of page
            if list_accumulator:
                blocks.append(
                    ListBlock(
                        ordered=_detect_ordered(list_accumulator),
                        items=list_accumulator,
                    )
                )
                list_accumulator = []

    # ------------------------------------------------------------------
    # Single box dispatch
    # ------------------------------------------------------------------

    def _map_single_box(
        self,
        box,
        header_map: dict[float, int],
        blocks: list[Block],
        embedded: list[EmbeddedAsset],
        list_accumulator: list[str],
        warnings: list[str],
    ) -> None:
        """Map one LayoutBox to the appropriate IR block type."""
        boxclass = box.boxclass

        if boxclass in ("title", "section-header"):
            level = self._heading_level_from_box(box, header_map)
            text = self._extract_text_from_box(box)
            if text:
                blocks.append(HeadingBlock(level=level, text=text))

        elif boxclass in ("text", "caption", "footnote"):
            text = self._extract_text_from_box(box)
            if text:
                blocks.append(ParagraphBlock(text=text))

        elif boxclass == "list-item":
            text = self._extract_text_from_box(box)
            if text:
                list_accumulator.append(text)

        elif boxclass == "picture":
            image_block = self._extract_image_from_box(box, embedded, warnings)
            if image_block is not None:
                blocks.append(image_block)

        elif boxclass == "table":
            table_block = self._extract_table_from_box(box, warnings)
            if table_block is not None:
                blocks.append(table_block)

    # ------------------------------------------------------------------
    # Heading level resolution
    # ------------------------------------------------------------------

    def _heading_level_from_box(
        self, box, header_map: dict[float, int]
    ) -> int:
        """Determine heading level using IdentifyHeaders font-size map.

        Priority:
        1. If box has textlines with a font size in header_map → use that level
        2. If box.boxclass == 'title' → default level 1
        3. If box.boxclass == 'section-header' → default level 2
        """
        # Get dominant (largest) font size from box's textlines
        max_size = 0.0
        for tl in getattr(box, "textlines", []) or []:
            for span in tl.get("spans", []):
                size = span.get("size", 0.0)
                if size > max_size:
                    max_size = size

        # Look up in header_map (try exact float match first, then int match)
        if max_size > 0:
            if max_size in header_map:
                return header_map[max_size]
            # Try integer key (IdentifyHeaders uses int keys)
            int_size = int(max_size)
            if float(int_size) in header_map:
                return header_map[float(int_size)]

        # Fallback based on boxclass
        if box.boxclass == "title":
            return 1
        return 2  # section-header default

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def _extract_text_from_box(self, box) -> str:
        """Join textlines spans into a single string.

        Iterates over box.textlines, joining each line's spans' text fields.
        Lines are separated by spaces. Returns stripped result.
        """
        lines: list[str] = []
        for tl in getattr(box, "textlines", []) or []:
            parts: list[str] = []
            for span in tl.get("spans", []):
                text = span.get("text", "")
                if text:
                    parts.append(text)
            line_str = "".join(parts).strip()
            if line_str:
                lines.append(line_str)

        return " ".join(lines).strip()

    # ------------------------------------------------------------------
    # Image extraction
    # ------------------------------------------------------------------

    def _extract_image_from_box(
        self,
        box,
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> ImageBlock | None:
        """Store box.image bytes as EmbeddedAsset, return ImageBlock."""
        image_data = getattr(box, "image", None)
        if image_data is None:
            warnings.append(
                f"picture box has no image data (position: "
                f"{getattr(box, 'x0', '?')},{getattr(box, 'y0', '?')})"
            )
            return None

        asset = EmbeddedAsset(
            data=image_data,
            extension=".png",
            original_name=None,
            alt_text="figure",
            source_vector_format=None,
        )
        idx = len(embedded)
        embedded.append(asset)
        return ImageBlock(asset_index=idx, alt=asset.alt_text)

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    def _extract_table_from_box(
        self, box, warnings: list[str]
    ) -> TableBlock | None:
        """Convert box.table dict to TableBlock.

        Uses box.table["extract"] as a 2D list of cell values.
        First row becomes headers, remaining rows become data.
        None cells are converted to empty strings.
        """
        try:
            table_data = getattr(box, "table", None)
            if table_data is None:
                warnings.append("table box has no table data")
                return None

            extract = table_data.get("extract")
            if not extract:
                warnings.append("table box has empty extract field")
                return None

            # First row is headers
            headers = [str(cell) if cell is not None else "" for cell in extract[0]]
            # Remaining rows are data
            rows = [
                [str(cell) if cell is not None else "" for cell in row]
                for row in extract[1:]
            ]
            return TableBlock(headers=headers, rows=rows)
        except Exception as exc:
            warnings.append(f"table extraction failed: {exc}")
            return None
