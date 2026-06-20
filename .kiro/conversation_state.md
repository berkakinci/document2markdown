# Conversation State — document2markdown

## Session Info
- Date: June 20, 2026 (latest session)

## Status
- Published to GitHub as `berkakinci/document2markdown` (public repo, git submodule in long_covid_research)
- CI passing: 200/200 tests on GitHub Actions (Ubuntu 24.04, Python 3.12)
- `test_real/` on disk locally, gitignored

## Key Decisions
- Module name: `document2markdown`
- Project layout: `document2markdown/document2markdown/` (project dir / package dir — standard Python pattern)
- Specs in `docs/spec/` with symlinks from `.kiro/specs/` for Kiro UI compatibility
- PDF library: PyMuPDF via pymupdf4llm (layout analysis via `parse_document()`, heading levels via `IdentifyHeaders`, OCR auto-applied to scanned pages)
- PDF converter: ~200 lines mapping LayoutBoxes to IR blocks (replaced ~750 lines of custom heuristics)
- Vector conversion chain:
  - EMF/WMF: Inkscape SVG → SVG (or PNG fallback) at configurable DPI
  - EPS: Pillow + Ghostscript (`gs`) → PNG (Inkscape 1.4+ on macOS cannot open EPS from CLI)
- Inkscape path: auto-detected via `_find_inkscape()` in `converter_vector.py` — checks PATH first, falls back to `INKSCAPE_FALLBACK` from `config.py`
- Ghostscript path: auto-detected via `_find_gs()` in `converter_vector.py` — checks PATH first, falls back to `GS_FALLBACKS` from `config.py`
- File type detection: extension + magic-byte cross-validation (must agree)
- OO API (`Converter`, `Document`) is the preferred interface; functional API delegates to it
- Core API converts one file per call; `document2markdown.utils` provides batch/directory helpers
- Pluggable renderer (`BaseRenderer` / `MarkdownRenderer`) decouples output format from pipeline
- CLI (`doc2md.py`) uses `utils` layer — never touches pipeline directly
- File naming: `converter_*.py`, `renderer_base.py`, `document_model.py`
- cairosvg removed — only handled SVG→SVG/PNG; cannot consume EMF/WMF/EPS which are the actual formats in DOCX/PPTX

## Pending Work
- Req 9.7 (pip installable) — manual verification only, not automatable
- Remaining coverage gaps (diminishing returns — require real binary fixtures or live tools):
  - `converter_pdf.py` (79%) — table extraction internals needing real tabular PDFs; raster image xref paths (lines 420-449, 475-487)
  - `converter_docx.py` (75%) — DrawingML/VML image extraction needing real DOCX with embedded images (lines 328-348, 417-429, 487-517)
  - `converter_pptx.py` (81%) — vector asset conversion paths (lines 290-340)
  - `renderer_base.py` (89%) — table/image/heading render variants (lines 109-114, 132, 158-165)
  - `postprocess.py` (87%) — whitespace normalization edge cases (lines 177-187, 200)
  - `writer.py` (84%) — write failure/permission error paths (lines 101-103, 124, 152-154)
  - `errors.py` (85%) — one error subclass not exercised (lines 76-78)
  - `doc2md.py` (not in module coverage) — CLI arg edge cases

## Known Limitations
- DOCX interrupted ordered lists: when a numbered list is split by a non-list paragraph (e.g. a note mid-procedure), the accumulator flushes and restarts numbering from 1. Fix requires threading `numId` from `numPr` through `_ListItem` to the accumulator so continuation can be detected and the count preserved. Common in technical documents.
- Vector conversion: EMF/WMF require Inkscape on PATH (or macOS .app bundle); EPS requires Ghostscript (`gs`) on PATH + Pillow. Missing tools produce `UnsupportedBlock`.
- PPTX title detection: only recognizes placeholder types 1/13/15 (TITLE/CENTER_TITLE/VERTICAL_TITLE). Real-world presentations often use free-form text boxes for titles — these come through as ParagraphBlock instead of HeadingBlock.
- PDF OCR: pymupdf4llm runs Tesseract on image-only pages, but sometimes doesn't populate textlines on `picture` LayoutBoxes. Mitigated by page-level `get_text()` fallback, but some pages (where the layout classifier splits content into multiple picture boxes with partial text) may still have incomplete extraction.
- PDF layout classification: pymupdf4llm may misclassify text regions as `page-footer` or absorb them into `picture` boxes. The page-text fallback compensates when extracted text is substantially less than available text.

## PDF Converter (refactored 2026-05-10)

Replaced custom heuristics with pymupdf4llm:
- Layout analysis: neural-network-based `parse_document()` classifies page regions
- Heading levels: `IdentifyHeaders` maps font sizes to H1-H6
- Images: extracted as PNG bytes from "picture" LayoutBoxes
- Tables: extracted from `box.table["extract"]` (no pandas dependency needed)
- Headers/footers: classified and skipped by the layout module
- Reading order: handled by the layout module (no custom linearization)
- OCR: auto-applied to scanned pages (Tesseract)
- Tradeoff: ~2-3x slower per document (neural network + OCR) but more accurate

## Test Files
All under `tests/`:
- `test_integration.py` — end-to-end for all 5 formats
- `test_unit_txt.py`, `test_unit_html.py`, `test_unit_docx.py`, `test_unit_pptx.py`, `test_unit_pdf.py`
- `test_unit_dispatcher.py`, `test_unit_postprocess.py`, `test_unit_renderer_writer.py`
- `test_unit_api.py`, `test_unit_cli.py`, `test_unit_errors.py`, `test_unit_vector.py`
- `test_property_batch.py`, `test_property_dispatcher.py`, `test_property_docx.py`
- `test_property_formats.py` — Properties 1 and 3 (all 5 formats)
- `test_property_headings.py` — Property 5 combined HTML+DOCX
- `test_property_html.py`, `test_property_postprocess.py`, `test_property_writer.py`
- `test_property_vector.py` — Property 9 (mocked Inkscape SVG output)
- `test_live_vector.py` — Live integration tests for EMF (Inkscape), WMF (Inkscape), EPS (Pillow+gs)

## Remaining TODO

1. **Progress message timing** — verify that the "Converting: <filename>" message is emitted *before* conversion starts (not after). A 500-page PDF was first alphabetically in a directory run and produced no output for a long time, making it look hung.

2. **Coverage check** — run `pytest --cov` to see if the new Pillow EPS path is covered
   - `_try_pillow_eps_png` lines for the `Image.open()` success path may not be hit by unit tests
   - The live test covers it but live tests don't count toward coverage by default

## Environment notes
- Must activate `conda activate document2markdown` before running tests
- Run tests from project root: `python -m pytest tests/`
- Inkscape: `/Applications/Inkscape.app/Contents/MacOS/inkscape` (v1.4.3)
- Ghostscript: `/opt/homebrew/bin/gs` (v10.07.0, installed via brew)
- Pillow: 12.2.0 (already in document2markdown conda env)

## History
- 2026-04-05: Spec started for document-to-markdown (requirements-first workflow)
- 2026-04-05: Requirements, design, and tasks finalized (10 requirements, 14 tasks)
- 2026-04-05: Refactored: core API one-file-per-call; batch/directory moved to utils layer
- 2026-04-05: Implementation complete: all converters, post-processor, renderer, writer, OO/functional API, CLI, integration tests
- 2026-04-05: Full unit test suite added (80 tests), property-based tests added (12 tests)
- 2026-04-05: Coverage gap analysis done; critical gaps addressed with new tests in proper locations
- 2026-04-05: Fixed OSError handling in converter_vector.py for missing libcairo
- 2026-04-05: Added TestHeaderExclusion to test_unit_pdf.py (101 tests)
- 2026-04-05: Coverage gap work — pptx, html, docx (146 tests); fixed pptx placeholder_format ValueError and docx list type-change flush bug
- 2026-04-05: Coverage gap work — pdf heuristics/failure paths, vector all fallback chains, docx image/vector rel paths (188 tests, 84% coverage)
- 2026-04-05: Fixed _PAGE_NUMBER_MAX_LEN from 6 → 20 to correctly match "Page N of M" patterns up to "Page 9999 of 99999"
- 2026-04-05: Documented interrupted ordered list limitation for later handling
- 2026-04-06: Task 4.3 complete — VectorConverter unit tests expanded; converter_vector.py at 100% coverage
- 2026-04-06: Tasks 13.2 and 13.3 confirmed complete — Properties 1 and 3 in test_property_formats.py; tasks.md updated
- 2026-04-06: Task 4.2 complete — Property 9 test added (test_property_vector.py, mocked Inkscape)
- 2026-04-06: Removed cairosvg — cannot consume EMF/WMF/EPS; Inkscape is the only real backend
- 2026-04-06: Committed full test suite; cleaned cairosvg from all source, spec, and config files
- 2026-05-09: Added INKSCAPE_PATH to config.py — auto-detects macOS .app bundle, no PATH change needed
- 2026-05-09: Investigated Inkscape 1.4/1.4.3 macOS CLI limitations: EPS unsupported, WMF minimal fixture was malformed
- 2026-05-09: Installed Ghostscript 10.07.0 via brew; confirmed Pillow 12.2.0 can open EPS via gs
- 2026-05-09: Updated VectorConverter — EPS now routed through Pillow+gs→PNG; EMF/WMF stay on Inkscape→SVG
- 2026-05-09: Added test_fixtures/ with minimal and real-world (art-nouveau-P3) EMF/WMF/EPS fixtures
- 2026-05-09: Added test_live_vector.py — 9 live tests covering EMF, WMF, EPS with real binaries; all pass
- 2026-05-09: Added Pillow to requirements.txt; 203 tests passing, 0 failures
- 2026-05-09: Reorganized into self-contained project directory; moved specs to `docs/spec/` with symlinks from `.kiro/specs/`
- 2026-05-09: Simplified TestTryPillowEpsPng tests — replaced convoluted mock layering with clean sys.modules patching
- 2026-05-09: Added Property 9b tests (EPS→PNG success + failure) to test_property_vector.py
- 2026-05-09: Refactored config.py to be purely declarative (INKSCAPE_FALLBACK, GS_FALLBACKS); moved binary resolution logic to _find_inkscape()/_find_gs() in converter_vector.py
- 2026-05-09: 205 tests passing (196 unit/property + 9 live), 0 failures
- 2026-05-09: Removed orphan test fixtures (test.emf/wmf/eps); tests generate minimal fixtures on the fly; test_live_vector.py auto-discovers all files in test_fixtures/ by extension
- 2026-05-09: Audit — updated design.md (VectorConverter EPS→Pillow+gs, Property 9 SVG/PNG split), pyproject.toml (added Pillow, moved hypothesis to dev), tasks.md note, test counts
- 2026-05-10: Fixed PDF vector extraction — replaced broken `get_svg_image(clip=bbox)` with `get_pixmap(clip=bbox)` for PNG rasterization (PyMuPDF 1.27 doesn't support clip param on get_svg_image)
- 2026-05-10: Fixed PDF text extraction — switched from `get_text("rawdict", flags=TEXT_PRESERVE_WHITESPACE)` to `get_text("dict")` (rawdict returns empty text in PyMuPDF 1.27)
- 2026-05-10: Removed VectorConverter dependency from converter_pdf.py (no longer needed; vector clusters rasterized directly via get_pixmap)
- 2026-05-10: Real-file testing on presentation PDF, DDS tutorial, FDA guidance, HP app note — text extraction working, identified 6 quality issues for future work
- 2026-05-10: Tier 1 PDF quality fixes — bullet list detection (`_extract_list_items`), relative heading sizing (`_relative_heading_level` + `_compute_body_font_size`), image dimension filter (`_MIN_IMAGE_DIM=50`)
- 2026-05-10: Added .gitignore for test_real/, __pycache__, .coverage, .hypothesis, .pytest_cache
- 2026-05-10: Real-file testing: 12+ files across PDF/DOCX/PPTX — all succeed, no crashes
- 2026-05-10: Refactored converter_pdf.py to use pymupdf4llm (parse_document + IdentifyHeaders) — replaced ~750 lines of custom heuristics with ~200 lines of mapping code
- 2026-05-10: pymupdf4llm added as hard dependency; layout module handles reading order, header/footer detection, image extraction, table extraction
- 2026-05-10: 177 tests passing after refactor (removed 20 obsolete heuristic tests, updated integration tests for layout module)
- 2026-05-10: Real-file validation: DDS tutorial (228K chars, 122 headings, 83 images), HP app note (46K chars, 41 headings, 26 images)
- 2026-05-10: Updated document-to-markdown spec (requirements.md + design.md) — Requirement 3 Output Handling changes: default output dir, directory mirroring, skip-if-newer, --force, configurable dir names
- 2026-05-10: Output handling implementation complete (tasks 15–23): default dir, mirroring, skip-if-newer, --force, configurable via config.py constants
- 2026-05-10: Removed toml config overhead — simplified to direct constant reads from config.py
- 2026-05-10: Spec audit: fixed 9 deviations
- 2026-05-10: Real-file test on test_real/ (103 documents converted successfully across PDF/DOCX/PPTX)
- 2026-05-10: Fixes from real-file run: line-buffered stdout, filter unsupported extensions in directory mode, deduplicated ERROR prefix in exceptions
- 2026-05-10: Investigated nested `Exports - Conversions/Exports - Conversions/` — could not reproduce; current implementation confirmed correct
- 2026-05-10: Created `test_real_subset/` (20 files) + pristine backups for fast iterative testing; expanded with deeper directory structure
- 2026-05-10: **document2markdown deemed ready for real conversions** — all testing complete, no blocking issues
- 2026-05-10: Added top-level README.md
- 2026-05-25: PDF OCR improvements — handle `table-fallback` boxclass; `picture` boxes emit text when textlines present; page-level fallback added
- 2026-05-25: Skip-if-newer performance fix — timestamp check moved to pre-conversion; no-op runs ~2s instead of 2+ minutes
- 2026-05-25: Added openpyxl to conda env; implemented XLSXConverter (markdown index + CSV per sheet + images); 208 tests passing
- 2026-06-20: Extracted to `berkakinci/document2markdown` via git filter-repo; wired as submodule in long_covid_research; split README/DEVELOPMENT.md; MIT license; GitHub Actions CI; fixed vector test mocks (_inkscape_available → _find_inkscape); CI passing 200/200; updated .gitignore (OS junk, backup files, venv)
