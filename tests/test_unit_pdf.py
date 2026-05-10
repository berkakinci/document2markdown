"""Unit tests for PDFConverter — Task 7.2."""
from __future__ import annotations

from pathlib import Path

import pytest
import fitz

from document2markdown.converter_pdf import PDFConverter
from document2markdown.document_model import (
    ConversionResult,
    HeadingBlock,
    ParagraphBlock,
)


def _make_pdf(tmp_path: Path, texts: list[tuple[tuple, str, float]] | None = None) -> Path:
    """Create a minimal PDF with optional text insertions.

    texts: list of ((x, y), text, fontsize)
    """
    doc = fitz.open()
    page = doc.new_page()
    if texts:
        for (x, y), text, size in texts:
            page.insert_text((x, y), text, fontsize=size)
    else:
        page.insert_text((72, 200), "Hello from PDF.", fontsize=12)
    p = tmp_path / "sample.pdf"
    doc.save(str(p))
    doc.close()
    return p


class TestNonEmptyResult:
    def test_valid_pdf_returns_nonempty_result(self, tmp_path):
        p = _make_pdf(tmp_path)
        result = PDFConverter().convert(p)
        assert isinstance(result, ConversionResult)
        assert len(result.blocks) > 0


class TestTextExtraction:
    def test_text_extracted_as_paragraph_or_heading(self, tmp_path):
        p = _make_pdf(tmp_path, [((72, 200), "Some body text.", 12)])
        result = PDFConverter().convert(p)
        text_blocks = [
            b for b in result.blocks
            if isinstance(b, (ParagraphBlock, HeadingBlock))
        ]
        assert text_blocks, "Expected at least one ParagraphBlock or HeadingBlock"

    def test_large_font_produces_heading(self, tmp_path):
        # Include body text so relative heading detection has a baseline.
        p = _make_pdf(tmp_path, [
            ((72, 200), "Big Title", 28),
            ((72, 300), "This is body text at normal size for comparison.", 12),
        ])
        result = PDFConverter().convert(p)
        headings = [b for b in result.blocks if isinstance(b, HeadingBlock)]
        assert headings, "Large font text should produce a HeadingBlock"


class TestPageNumberExclusion:
    def test_page_number_text_excluded(self, tmp_path):
        """Text that looks like a page number should not appear in output."""
        # Place "Page 1" near the bottom margin (footer zone)
        doc = fitz.open()
        page = doc.new_page()
        page_height = page.rect.height
        # Insert real content in the middle
        page.insert_text((72, 300), "Real content paragraph.", fontsize=12)
        # Insert page number near the bottom (footer zone)
        page.insert_text((72, page_height - 20), "Page 1", fontsize=10)
        p = tmp_path / "with_pagenum.pdf"
        doc.save(str(p))
        doc.close()

        result = PDFConverter().convert(p)
        all_texts = []
        for b in result.blocks:
            if isinstance(b, ParagraphBlock):
                all_texts.append(b.text)
            elif isinstance(b, HeadingBlock):
                all_texts.append(b.text)

        # "Page 1" should not appear (it's in the footer zone)
        assert not any("Page 1" in t for t in all_texts), (
            f"Page number should be excluded, but found in: {all_texts}"
        )


class TestMultiColumnPDFLinearization:
    def test_two_column_pdf_text_extracted_in_order(self, tmp_path):
        """Text from a two-column PDF should be extracted (Req 6.3)."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 100), "Left column line 1", fontsize=12)
        page.insert_text((50, 120), "Left column line 2", fontsize=12)
        page.insert_text((320, 100), "Right column line 1", fontsize=12)
        page.insert_text((320, 120), "Right column line 2", fontsize=12)
        src = tmp_path / "twocol.pdf"
        doc.save(str(src))
        doc.close()

        result = PDFConverter().convert(src)
        all_text = " ".join(b.text for b in result.blocks if isinstance(b, ParagraphBlock))
        assert "Left column" in all_text
        assert "Right column" in all_text


class TestHeaderExclusion:
    def test_header_text_excluded_from_pdf_output(self, tmp_path):
        """Text in the top margin zone should be excluded (Req 6.4)."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        # Main content well below the top margin zone (7% of 842 ≈ 59pt)
        page.insert_text((72, 400), "Main document content here.", fontsize=12)
        # Running header in the top margin zone
        page.insert_text((72, 20), "Running Header Text", fontsize=10)
        src = tmp_path / "withheader.pdf"
        doc.save(str(src))
        doc.close()

        result = PDFConverter().convert(src)
        all_text = " ".join(b.text for b in result.blocks if isinstance(b, ParagraphBlock))
        assert "Main document content" in all_text
        assert "Running Header Text" not in all_text


class TestHeaderFooterExclusion:
    def test_footer_text_excluded_from_pdf_output(self, tmp_path):
        """Text in the bottom margin zone should be excluded (Req 6.4)."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 400), "Main document content here.", fontsize=12)
        page.insert_text((72, 820), "Page 1", fontsize=10)
        src = tmp_path / "withfooter.pdf"
        doc.save(str(src))
        doc.close()

        result = PDFConverter().convert(src)
        all_text = " ".join(b.text for b in result.blocks if isinstance(b, ParagraphBlock))
        assert "Main document content" in all_text
        assert "Page 1" not in all_text


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

class TestHeuristicHelpers:
    def test_is_page_number_matches_digits(self):
        from document2markdown.converter_pdf import _is_page_number
        assert _is_page_number("1") is True
        assert _is_page_number("42") is True
        assert _is_page_number("Page 3") is True
        assert _is_page_number("3 of 10") is True
        assert _is_page_number("Page 9999 of 99999") is True  # 18 chars — within limit

    def test_is_page_number_rejects_long_text(self):
        from document2markdown.converter_pdf import _is_page_number
        assert _is_page_number("This is a real paragraph") is False
        # 21 chars — exceeds _PAGE_NUMBER_MAX_LEN of 20
        assert _is_page_number("Page 99999 of 9999999") is False

    def test_dominant_font_size_returns_max(self):
        from document2markdown.converter_pdf import _dominant_font_size
        block = {
            "lines": [
                {"spans": [{"size": 12.0}, {"size": 18.0}]},
                {"spans": [{"size": 10.0}]},
            ]
        }
        assert _dominant_font_size(block) == 18.0

    def test_dominant_font_size_empty_block(self):
        from document2markdown.converter_pdf import _dominant_font_size
        assert _dominant_font_size({"lines": []}) == 0.0

    def test_font_size_to_heading_level(self):
        from document2markdown.converter_pdf import _font_size_to_heading_level
        assert _font_size_to_heading_level(30.0) == 1
        assert _font_size_to_heading_level(22.0) == 2
        assert _font_size_to_heading_level(12.0) is None

    def test_bbox_area(self):
        from document2markdown.converter_pdf import _bbox_area
        import fitz
        assert _bbox_area(fitz.Rect(0, 0, 10, 20)) == 200.0
        assert _bbox_area(fitz.Rect(0, 0, 0, 0)) == 0.0

    def test_bboxes_close_true(self):
        from document2markdown.converter_pdf import _bboxes_close
        import fitz
        a = fitz.Rect(0, 0, 10, 10)
        b = fitz.Rect(15, 0, 25, 10)  # 5pt gap horizontally
        assert _bboxes_close(a, b, threshold=8.0) is True

    def test_bboxes_close_false(self):
        from document2markdown.converter_pdf import _bboxes_close
        import fitz
        a = fitz.Rect(0, 0, 10, 10)
        b = fitz.Rect(50, 0, 60, 10)  # 40pt gap
        assert _bboxes_close(a, b, threshold=8.0) is False


# ---------------------------------------------------------------------------
# _cluster_drawings
# ---------------------------------------------------------------------------

class TestClusterDrawings:
    def test_empty_drawings_returns_empty(self):
        from document2markdown.converter_pdf import _cluster_drawings
        assert _cluster_drawings([], 8.0) == []

    def test_drawing_without_rect_skipped(self):
        from document2markdown.converter_pdf import _cluster_drawings
        result = _cluster_drawings([{"no_rect": True}], 8.0)
        assert result == []

    def test_nearby_drawings_merged(self):
        from document2markdown.converter_pdf import _cluster_drawings
        import fitz
        drawings = [
            {"rect": fitz.Rect(0, 0, 10, 10)},
            {"rect": fitz.Rect(12, 0, 22, 10)},  # 2pt gap — within threshold
        ]
        clusters = _cluster_drawings(drawings, proximity=8.0)
        assert len(clusters) == 1

    def test_distant_drawings_separate_clusters(self):
        from document2markdown.converter_pdf import _cluster_drawings
        import fitz
        drawings = [
            {"rect": fitz.Rect(0, 0, 10, 10)},
            {"rect": fitz.Rect(100, 0, 110, 10)},  # far apart
        ]
        clusters = _cluster_drawings(drawings, proximity=8.0)
        assert len(clusters) == 2


# ---------------------------------------------------------------------------
# convert() failure path — bad file
# ---------------------------------------------------------------------------

class TestConvertFailurePath:
    def test_corrupt_pdf_returns_empty_result_with_warning(self, tmp_path):
        """A file that can't be opened should return empty blocks with a warning."""
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        result = PDFConverter().convert(bad)
        assert result.blocks == []
        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# _extract_vector_clusters failure paths
# ---------------------------------------------------------------------------

class TestExtractVectorClustersFailures:
    def test_get_drawings_exception_adds_warning(self, tmp_path):
        """If get_drawings() raises, a warning is added and empty list returned."""
        from unittest.mock import MagicMock, patch
        converter = PDFConverter()
        page = MagicMock()
        page.get_drawings.side_effect = RuntimeError("draw fail")
        page.number = 0
        warnings = []
        result = converter._extract_vector_clusters(page, 842.0, [], [], warnings)
        assert result == []
        assert any("get_drawings" in w for w in warnings)

    def test_get_pixmap_exception_adds_warning(self, tmp_path):
        """If get_pixmap() raises, a warning is added and None returned."""
        from unittest.mock import MagicMock
        converter = PDFConverter()
        page = MagicMock()
        page.get_pixmap.side_effect = RuntimeError("pixmap fail")
        page.number = 0
        warnings = []
        import fitz
        result = converter._export_vector_cluster(
            page, fitz.Rect(0, 0, 100, 100), [], warnings
        )
        assert result is None
        assert any("get_pixmap" in w for w in warnings)

    def test_tiny_cluster_skipped(self, tmp_path):
        """Clusters below _MIN_VECTOR_AREA should not produce image blocks."""
        from unittest.mock import MagicMock
        import fitz
        from document2markdown.converter_pdf import _MIN_VECTOR_AREA
        converter = PDFConverter()
        page = MagicMock()
        # Tiny rect: area = 5*5 = 25, well below 400
        page.get_drawings.return_value = [{"rect": fitz.Rect(0, 0, 5, 5)}]
        blocks = []
        warnings = []
        result = converter._extract_vector_clusters(page, 842.0, blocks, [], warnings)
        assert blocks == []
        assert result == []


# ---------------------------------------------------------------------------
# _extract_tables failure path
# ---------------------------------------------------------------------------

class TestExtractTablesFailure:
    def test_find_tables_exception_adds_warning(self):
        """If find_tables() raises, a warning is added and empty list returned."""
        from unittest.mock import MagicMock
        converter = PDFConverter()
        page = MagicMock()
        page.find_tables.side_effect = RuntimeError("table fail")
        page.number = 0
        warnings = []
        result = converter._extract_tables(page, [], warnings)
        assert result == []
        assert any("find_tables" in w for w in warnings)


# ---------------------------------------------------------------------------
# _process_image_block paths
# ---------------------------------------------------------------------------

class TestProcessImageBlock:
    def test_image_block_with_no_data_adds_warning(self):
        """Image block with no data and no xref should add a warning."""
        from unittest.mock import MagicMock
        converter = PDFConverter()
        page = MagicMock()
        page.number = 0
        block = {"type": 1, "bbox": (0, 0, 100, 100)}  # no "image" key, xref=0
        warnings = []
        converter._process_image_block(block, page, [], [], warnings)
        assert any("no extractable data" in w for w in warnings)

    def test_extract_image_by_xref_failure_adds_warning(self):
        """If extract_image() raises, a warning is added and None returned."""
        from unittest.mock import MagicMock
        converter = PDFConverter()
        page = MagicMock()
        page.number = 0
        page.parent.extract_image.side_effect = RuntimeError("xref fail")
        warnings = []
        result = converter._extract_image_by_xref(page, 5, warnings)
        assert result is None
        assert any("xref=5" in w for w in warnings)

    def test_colorspace_to_ext_jpeg(self):
        from document2markdown.converter_pdf import _colorspace_to_ext
        assert _colorspace_to_ext({"ext": "jpg"}) == ".jpg"
        assert _colorspace_to_ext({"colorspace": "jpeg"}) == ".jpg"
        assert _colorspace_to_ext({}) == ".png"
