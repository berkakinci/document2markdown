# Conversation State — document2markdown

## Session Info
- Date: May 9, 2026

## Status
- Implementation complete — all 14 required tasks done, all optional test tasks done
- 203 tests passing, 0 skipped
- Overall source coverage: 85%
- `converter_vector.py` at 100% coverage

## Key Decisions
- Module name: `document2markdown`
- Project layout: `document2markdown/document2markdown/` (project dir / package dir — standard Python pattern)
- Specs in `docs/spec/` with symlinks from `.kiro/specs/` for Kiro UI compatibility
- PDF library: PyMuPDF (for vector extraction via `page.get_drawings()`)
- Vector conversion chain:
  - EMF/WMF: Inkscape SVG → SVG (or PNG fallback) at configurable DPI
  - EPS: Pillow + Ghostscript (`gs`) → PNG (Inkscape 1.4+ on macOS cannot open EPS from CLI)
- Inkscape path: auto-detected via `INKSCAPE_PATH` in `document2markdown/config.py` — checks PATH first, falls back to `/Applications/Inkscape.app/Contents/MacOS/inkscape`
- Ghostscript (`gs`) must be on PATH for EPS support (install via `brew install ghostscript`)
- File type detection: extension + magic-byte cross-validation (must agree)
- OO API (`Converter`, `Document`) is the preferred interface; functional API delegates to it
- Core API converts one file per call; `document2markdown.utils` provides batch/directory helpers
- Pluggable renderer (`BaseRenderer` / `MarkdownRenderer`) decouples output format from pipeline
- CLI (`doc2md.py`) uses `utils` layer — never touches pipeline directly
- File naming: `converter_*.py`, `renderer_base.py`, `document_model.py`
- cairosvg removed — only handled SVG→SVG/PNG; cannot consume EMF/WMF/EPS which are the actual formats in DOCX/PPTX
- Future: extract as standalone repo via `git filter-repo --path "Scripts and Utilities/document2markdown/"`; may become a submodule here

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

## Session Handoff (2026-05-09) — TEMPORARY, clean up on resume

### What we accomplished this session

**1. Inkscape path resolution (config.py)**
- Added `INKSCAPE_PATH` to `document2markdown/config.py`
- Uses `shutil.which("inkscape")` first; falls back to `/Applications/Inkscape.app/Contents/MacOS/inkscape`
- `converter_vector.py` updated throughout to use `INKSCAPE_PATH` instead of bare `"inkscape"` string
- `_inkscape_available()` now checks `Path(INKSCAPE_PATH).is_file()` so the .app bundle is found without any PATH change

**2. Live vector testing investigation**
- Created `test_fixtures/` directory with:
  - `test.emf`, `test.wmf`, `test.eps` — minimal programmatically-generated fixtures
  - `art-nouveau-P3.emf`, `art-nouveau-P3.wmf`, `art-nouveau-P3.eps` — real-world fixtures exported from Inkscape's bundled examples (user-provided)
- Discovered Inkscape 1.4.3 macOS CLI limitations:
  - EMF: works perfectly via CLI ✓
  - WMF: works with real files; our minimal test fixture was malformed (placeable header checksum issue)
  - EPS: Inkscape CLI cannot open EPS on macOS regardless of version — pops a GUI dialog or fails silently
- Installed Ghostscript 10.07.0 via `brew install ghostscript`
- Confirmed Pillow 12.2.0 can open EPS via `Image.open()` which shells out to `gs` automatically

**3. VectorConverter refactor (converter_vector.py)**
- EPS now routed through `_try_pillow_eps_png()` → Pillow + gs → PNG
- EMF/WMF stay on Inkscape → SVG (with PNG fallback)
- Added `_ghostscript_available()` helper (checks `shutil.which("gs")`)
- Added `_try_pillow_eps_png()` function
- Updated module docstring to reflect new routing
- Updated error message to mention both Inkscape (EMF/WMF) and gs+Pillow (EPS)
- Added `Pillow` to `requirements.txt`

**4. Test suite updates**
- `tests/test_unit_vector.py` — appended new test classes:
  - `TestTryPillowEpsPng` — unit tests for the new Pillow EPS helper
  - `TestVectorConverterEPSRouting` — verifies EPS goes to Pillow, EMF/WMF go to Inkscape, never cross
- `tests/test_live_vector.py` — fully rewritten:
  - `TestLiveVectorEMF` — 3 tests using real Inkscape binary (skipped if absent)
  - `TestLiveVectorWMF` — 2 tests using real Inkscape binary + art-nouveau-P3.wmf fixture
  - `TestLiveVectorEPS` — 3 tests using Pillow+gs (skipped if gs absent); includes real fixture test
  - `TestLiveVectorGarbageInput` — 1 test confirming garbage EMF raises VectorConversionError
  - All xfail markers removed — everything passes cleanly now

**5. Final test count: 203 passing, 0 failures**

### Immediate TODO on resume

1. **Review `test_unit_vector.py` — `TestTryPillowEpsPng.test_returns_png_bytes_on_success`**
   - This test is a bit convoluted (mock layering got messy); it passes but should be simplified
   - Consider replacing with a cleaner approach that directly patches `PIL.Image` at import time

2. **Coverage check** — run `pytest --cov` to see if the new Pillow EPS path is covered
   - `_try_pillow_eps_png` lines for the `Image.open()` success path may not be hit by unit tests
   - The live test covers it but live tests don't count toward coverage by default

3. **Update `test_property_vector.py`** — Property 9 currently only mocks Inkscape SVG output
   - Should add a property for EPS→PNG via mocked Pillow path

4. **Consider adding `gs` path config** — similar to `INKSCAPE_PATH`, add `GS_PATH` to `document2markdown/config.py`
   - Currently `_ghostscript_available()` only checks `shutil.which("gs")` — no fallback for non-PATH installs
   - Homebrew installs to `/opt/homebrew/bin/gs` which should be on PATH, but worth making explicit

5. **Clean up `test_fixtures/`** — decide whether to keep in repo or add to `.gitignore`
   - Binary fixtures (EMF, WMF) are small (40-60KB) and useful for live tests
   - Could add a `conftest.py` fixture that skips live tests if `test_fixtures/` is absent

6. **Remaining coverage gaps** (pre-existing, not introduced this session):
   - `converter_pdf.py` (79%), `converter_docx.py` (75%), `converter_pptx.py` (81%)
   - `renderer_base.py` (89%), `postprocess.py` (87%), `writer.py` (84%), `errors.py` (85%)

### Environment notes
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
