# Implementation Plan: PDF Converter Refactor — pymupdf4llm

## Overview

Rewrite `converter_pdf.py` to use `pymupdf4llm`'s `parse_document()` and `IdentifyHeaders` instead of custom heuristics. The public API is unchanged; only internal extraction logic is replaced. Existing tests must continue to pass.

## Tasks

- [x] 1. Update dependencies
  - Add `pymupdf4llm` to `requirements.txt`
  - Add `pymupdf4llm` to `pyproject.toml` `[project.dependencies]`
  - Verify install with `pip install -e .`
  - _Requirements: 1.1, 1.3_

- [x] 2. Rewrite converter_pdf.py
  - [x] 2.1 Replace module-level imports and remove dead heuristic code
    - Remove all heuristic constants (`_MARGIN_FRACTION`, `_PAGE_NUMBER_RE`, `_HEADING_LEVELS`, `_YBAND_TOLERANCE`, `_MIN_VECTOR_AREA`, etc.)
    - Remove helper functions (`_is_header_footer`, `_is_page_number`, `_dominant_font_size`, `_is_bold`, `_font_size_to_heading_level`, `_extract_list_items`, `_linearize_blocks`, `_cluster_drawings`, `_bboxes_close`, `_bbox_expand`, `_bbox_area`, `_colorspace_to_ext`)
    - Add imports for `pymupdf4llm.helpers.document_layout.parse_document` and `pymupdf4llm.helpers.pymupdf_rag.IdentifyHeaders`
    - Keep `fitz` import for `fitz.open()`
    - Keep `BaseConverter`, `ConversionResult`, and all IR block imports unchanged
    - _Requirements: 1.2, 10.1, 10.2, 10.3, 10.4_

  - [x] 2.2 Implement `_build_header_map()` method
    - Call `IdentifyHeaders(doc)` and convert its output to `dict[float, int]` mapping font_size → heading level (1–6)
    - Wrap in try/except: on failure, return empty dict and append warning
    - _Requirements: 3.1, 3.5_

  - [x] 2.3 Implement `convert()` method body
    - Open PDF with `fitz.open()`, wrapped in try/except returning empty ConversionResult on failure
    - Call `_build_header_map(doc)` for heading levels
    - Call `parse_document(doc, embed_images=True, image_dpi=self._raster_dpi)`, wrapped in try/except
    - Call `_map_boxes_to_blocks()` with the results
    - Close doc in finally block
    - Return `ConversionResult(blocks, embedded, warnings)`
    - _Requirements: 2.1, 2.2, 2.3, 9.1, 9.2, 9.4_

  - [x] 2.4 Implement `_map_boxes_to_blocks()` method
    - Iterate over per-page LayoutBox lists
    - Maintain `list_accumulator: list[str]` for consecutive list-items
    - For each box: skip page-header/page-footer, dispatch to `_map_single_box()`
    - Flush list_accumulator at end of each page and at end of all pages
    - Wrap individual box processing in try/except to skip failures with warning
    - _Requirements: 4.1–4.8, 5.1, 5.2, 8.1, 8.2, 9.3_

  - [x] 2.5 Implement `_map_single_box()` method
    - Switch on `box.boxclass`:
      - "title" / "section-header" → `_heading_level_from_box()` → HeadingBlock
      - "text" / "caption" / "footnote" → `_extract_text_from_box()` → ParagraphBlock
      - "list-item" → `_extract_text_from_box()` → append to list_accumulator
      - "picture" → `_extract_image_from_box()`
      - "table" → `_extract_table_from_box()`
    - _Requirements: 4.1–4.8_

  - [x] 2.6 Implement `_heading_level_from_box()` method
    - Get dominant font size from `box.textlines` spans
    - Look up in header_map; if found, return mapped level
    - Fallback: title → 1, section-header → 2
    - _Requirements: 3.2, 3.3, 3.4_

  - [x] 2.7 Implement `_extract_text_from_box()` method
    - Iterate `box.textlines`, join spans' "text" fields
    - Join lines with space separator
    - Strip leading/trailing whitespace
    - Return empty string if no text found
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 2.8 Implement `_extract_image_from_box()` method
    - If `box.image` is None: append warning, return None
    - Create EmbeddedAsset with data=box.image, extension=".png", alt_text="figure"
    - Append to embedded list, return ImageBlock with correct asset_index
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 2.9 Implement `_extract_table_from_box()` method
    - If `box.table` is None or `box.table.get("extract")` is empty: append warning, return None
    - Extract first row as headers (convert None → "")
    - Extract remaining rows as data (convert None → "")
    - Return TableBlock(headers=headers, rows=rows)
    - Wrap in try/except for malformed data
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 2.10 Implement `_detect_ordered()` helper
    - Check if list items start with numbered patterns (1., 2., etc.)
    - Return True for ordered, False for unordered
    - _Requirements: 5.4_

- [x] 3. Checkpoint — verify basic conversion works
  - Run `python -c "from document2markdown.converter_pdf import PDFConverter; print('import OK')"` to verify module loads
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update unit tests (test_unit_pdf.py)
  - [x] 4.1 Remove tests for deleted heuristic helpers
    - Remove `TestHeuristicHelpers` class (tests `_is_page_number`, `_dominant_font_size`, `_font_size_to_heading_level`, `_bbox_area`, `_bboxes_close`)
    - Remove `TestClusterDrawings` class
    - Remove `TestExtractVectorClustersFailures` class
    - Remove `TestExtractTablesFailure` class (old `find_tables` mock)
    - Remove `TestProcessImageBlock` class (old xref-based extraction)
    - _Requirements: 10.5_

  - [x] 4.2 Add unit tests for new internal methods with mocked pymupdf4llm
    - Test `_build_header_map()` with mocked IdentifyHeaders (success and failure paths)
    - Test `_map_boxes_to_blocks()` with mock LayoutBox sequences covering all boxclass types
    - Test `_extract_text_from_box()` with various textline structures
    - Test `_extract_table_from_box()` with valid and malformed table dicts
    - Test `_extract_image_from_box()` with non-None and None image data
    - Test header/footer exclusion (page-header/page-footer boxes produce no blocks)
    - Test list-item accumulation (consecutive items → single ListBlock)
    - _Requirements: 4.1–4.8, 5.1–5.3, 6.1–6.3, 7.1–7.4, 8.1, 8.2, 11.1–11.2_

  - [x] 4.3 Update integration-style tests that create real PDFs
    - Keep `TestNonEmptyResult`, `TestTextExtraction`, `TestConvertFailurePath`
    - Update `TestPageNumberExclusion`, `TestHeaderExclusion`, `TestHeaderFooterExclusion` — these now rely on pymupdf4llm's layout classification rather than margin-zone heuristics; adjust expectations if needed
    - Keep `TestMultiColumnPDFLinearization` — verify parse_document handles multi-column
    - _Requirements: 9.1, 10.5_

  - [ ]* 4.4 Write property tests for box-to-block mapping
    - **Property 1: Box-to-block type mapping consistency**
    - **Validates: Requirements 4.1–4.8**

  - [ ]* 4.5 Write property test for list item accumulation
    - **Property 3: List item accumulation preserves items**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 4.6 Write property test for image asset indexing
    - **Property 4: Image asset indexing integrity**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 4.7 Write property test for table dimension preservation
    - **Property 5: Table extraction preserves dimensions**
    - **Validates: Requirements 7.1, 7.2, 7.4**

  - [ ]* 4.8 Write property test for text extraction completeness
    - **Property 6: Text extraction completeness**
    - **Validates: Requirements 11.1, 11.2**

- [x] 5. Checkpoint — run full test suite
  - Run `pytest tests/test_unit_pdf.py tests/test_property_formats.py tests/test_integration.py`
  - Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 10.5_

- [x] 6. Real-file validation
  - [x] 6.1 Test with a real research PDF
    - Run converter on a multi-page research paper PDF
    - Verify headings, paragraphs, tables, and images are extracted
    - Compare output quality to previous heuristic-based extraction
    - _Requirements: 2.1, 4.1–4.8_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The project uses Python 3.12+ with hypothesis for property-based testing
- All existing tests in `test_property_formats.py` and `test_integration.py` must pass unchanged
- The refactor is contained to `converter_pdf.py` and `test_unit_pdf.py` — no other source files change
- Property tests validate universal correctness properties from the design document
