# Implementation Plan: document-to-markdown

## Overview

Implement `doc2md.py`, a Python CLI script that converts PDF, DOCX, HTML, PPTX, and TXT documents into clean Markdown. The implementation follows a modular pipeline: CLI → dispatcher → per-format converter → post-processor → output writer.

## Tasks

- [x] 1. Set up project structure, dependencies, and core interfaces
  - Create `document2markdown/` package with `__init__.py`
  - Create `document2markdown/document_model.py` with all IR dataclasses (`ConversionResult`, `EmbeddedAsset`, and all `Block` types)
  - Create `document2markdown/config.py` with `RASTER_DPI = 300` and any other script-level constants
  - Create `document2markdown/converter_base.py` with `BaseConverter` abstract class
  - Create `document2markdown/errors.py` with `UnsupportedFormatError`, `MimeExtensionMismatchError`, and `ParseError`
  - Create `requirements.txt` with all dependencies: `PyMuPDF`, `python-docx`, `beautifulsoup4`, `markdownify`, `python-pptx`, `python-magic`, `hypothesis`
  - _Requirements: 1.1–1.6, 7.1–7.3_

- [x] 1.5 Checkpoint — Verify project structure and interfaces
  - Confirm package layout, IR dataclasses, base class, and error types are correct before proceeding
  - _No implementation yet — review only_

- [x] 2. Implement the Format Dispatcher
  - [x] 2.1 Implement `document2markdown/dispatcher.py` with `EXTENSION_TO_MIME`, `CONVERTERS` maps, and `resolve_converter(path)`
    - Cross-validate extension MIME vs magic-byte MIME; raise `MimeExtensionMismatchError` on disagreement
    - Raise `UnsupportedFormatError` when type is undetectable by both methods
    - _Requirements: 1.6, 7.1, 7.2, 7.3_

  - [x]* 2.2 Write property test for dispatcher — Property 2: Unsupported or mismatched format exits non-zero
    - **Property 2: Unsupported or mismatched format exits non-zero**
    - **Validates: Requirements 1.6, 7.2, 7.3**

  - [x]* 2.3 Write property test for dispatcher — Property 10: Extension–MIME cross-validation rejects mismatches
    - **Property 10: Extension–MIME cross-validation rejects mismatches**
    - **Validates: Requirements 7.2**

  - [x]* 2.4 Write unit tests for dispatcher
    - Correct converter selected when extension and MIME agree
    - `MimeExtensionMismatchError` raised with both type strings when they disagree
    - `UnsupportedFormatError` raised for unknown extension + unknown MIME
    - _Requirements: 1.6, 7.1, 7.2, 7.3_

- [x] 3. Implement TXT and HTML converters
  - [x] 3.1 Implement `document2markdown/converter_txt.py` (`TXTConverter`)
    - Wrap content in fenced code block or plain paragraphs
    - Return `ConversionResult` with appropriate blocks
    - _Requirements: 1.5_

  - [x] 3.2 Implement `document2markdown/converter_html.py` (`HTMLConverter`)
    - Use `BeautifulSoup4` + `markdownify` to parse DOM
    - Map `<h1>`–`<h6>` → `HeadingBlock`, lists → `ListBlock`, tables → `TableBlock`, `<a>` → `LinkBlock`, `<code>`/`<pre>` → `CodeBlock`, `<img>` → `ImageBlock`
    - Emit `UnsupportedBlock` for unrenderable elements
    - _Requirements: 1.3, 2.1–2.6, 2.9_

  - [x]* 3.3 Write property test for HTML converter — Property 5: Heading round-trip level preservation
    - **Property 5: Heading round-trip level preservation**
    - **Validates: Requirements 2.1**

  - [x]* 3.4 Write unit tests for TXT and HTML converters
    - TXT: non-empty result, fenced code block present
    - HTML: headings, lists, tables, links, code blocks mapped correctly; `UnsupportedBlock` for unknown elements
    - _Requirements: 1.3, 1.5, 2.1–2.6, 2.9_

- [x] 4. Implement VectorConverter
  - [x] 4.1 Implement `document2markdown/converter_vector.py` (`VectorConverter`)
    - Accept raw bytes + source format hint (EMF, WMF, EPS)
    - Attempt conversion: Inkscape SVG → Inkscape PNG raster at `RASTER_DPI`
    - Return `(bytes, extension)` tuple; log warning and raise on total failure (no partial SVG written)
    - _Requirements: 2.8_

  - [x]* 4.2 Write property test for VectorConverter — Property 9: Vector graphics are extracted as SVG
    - **Property 9: Vector graphics are extracted as SVG**
    - **Validates: Requirements 2.8**
    - _No test_property_vector.py exists; property not yet implemented_

  - [x] 4.3 Write unit tests for VectorConverter
    - Returns valid SVG bytes for fixture EMF/WMF/EPS input
    - Logs warning and raises on conversion failure; no partial SVG written
    - _Requirements: 2.8_

- [x] 5. Implement DOCX converter
  - [x] 5.1 Implement `document2markdown/converter_docx.py` (`DOCXConverter`)
    - Walk document XML with `python-docx`; map paragraph styles to `HeadingBlock` levels
    - Extract embedded images → `EmbeddedAsset`; pass EMF/WMF drawing objects through `VectorConverter`
    - Map ordered/unordered lists → `ListBlock`, tables → `TableBlock`, hyperlinks → `LinkBlock`, code runs → `CodeBlock`
    - Emit `UnsupportedBlock` for unrenderable elements
    - _Requirements: 1.2, 2.1–2.9_

  - [x]* 5.2 Write property test for DOCX converter — Property 5: Heading round-trip level preservation
    - **Property 5: Heading round-trip level preservation (DOCX)**
    - **Validates: Requirements 2.1**

  - [x]* 5.3 Write unit tests for DOCX converter
    - Headings, lists, tables, links, images, code blocks mapped correctly
    - EMF/WMF objects routed through `VectorConverter`
    - `UnsupportedBlock` emitted for unrenderable elements
    - _Requirements: 1.2, 2.1–2.9_

- [x] 6. Implement PPTX converter
  - [x] 6.1 Implement `document2markdown/converter_pptx.py` (`PPTXConverter`)
    - Iterate slides in order with `python-pptx`; slide title → `HeadingBlock(level=2)`, body text → `ParagraphBlock`
    - Extract images → `EmbeddedAsset`; pass EMF/WMF/EPS shapes through `VectorConverter`
    - Emit `UnsupportedBlock` for unrenderable elements
    - _Requirements: 1.4, 2.1, 2.6–2.9_

  - [x]* 6.2 Write unit tests for PPTX converter
    - Slides processed in order; title → H2; images extracted; vector shapes routed through `VectorConverter`
    - _Requirements: 1.4, 2.1, 2.6–2.9_

- [x] 7. Implement PDF converter
  - [x] 7.1 Implement `document2markdown/converter_pdf.py` (`PDFConverter`)
    - Use `PyMuPDF`; extract text blocks, tables, and raster images into IR blocks
    - Call `page.get_drawings()` to detect vector path clusters; group by bounding-box proximity
    - Export each cluster via `page.get_svg_image(clip=bbox)` → pass to `VectorConverter`
    - Apply heuristics to skip page numbers, headers, and footers
    - Attempt to linearize multi-column text into single reading order
    - _Requirements: 1.1, 2.1–2.9, 6.3, 6.4_

  - [x]* 7.2 Write unit tests for PDF converter
    - Non-empty `ConversionResult` for a valid sample PDF
    - Page numbers/headers/footers excluded from output
    - Vector clusters extracted as `ImageBlock` referencing SVG assets
    - _Requirements: 1.1, 2.8, 6.3, 6.4_

- [x] 8. Checkpoint — Ensure all converter unit tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Post-Processor and Output Writer
  - [x] 9.1 Implement `document2markdown/postprocess.py`
    - Collapse runs of more than two consecutive blank lines
    - Strip non-printable control characters (except `\n`, `\t`)
    - Strip page numbers, headers, and footers via heuristic patterns
    - Normalize heading levels
    - _Requirements: 6.2, 6.4_

  - [x]* 9.2 Write property test for post-processor — Property 4: No excessive blank lines in output
    - **Property 4: No excessive blank lines in output**
    - **Validates: Requirements 6.2**

  - [x]* 9.3 Write unit tests for post-processor
    - Control characters stripped; blank lines collapsed; page numbers/headers/footers removed
    - _Requirements: 6.2, 6.4_

  - [x] 9.4 Implement `document2markdown/renderer_base.py` (`BaseRenderer`, `MarkdownRenderer`)
    - `BaseRenderer` abstract class with `render(result: ConversionResult) -> str`
    - `MarkdownRenderer` default implementation producing GFM Markdown
    - _Requirements: 10.1, 10.2_

  - [x] 9.5 Implement `document2markdown/writer.py` (`OutputWriter`)
    - Accepts a `BaseRenderer` instance; calls `renderer.render(result)` for output string
    - Write embedded assets to `md_embedded/{base_name}_{serial:04d}{ext}`
    - Generate URL-encoded relative paths for all image/link references
    - Overwrite existing output files with a stderr warning
    - Create output directories as needed
    - _Requirements: 3.1–3.8, 2.6, 2.7, 10.6_

  - [x]* 9.6 Write property test for output writer — Property 6: Embedded asset paths are URL-encoded relative paths
    - **Property 6: Embedded asset paths are URL-encoded relative paths**
    - **Validates: Requirements 3.7**

  - [x]* 9.7 Write property test for output writer — Property 8: Output path derivation
    - **Property 8: Output path derivation**
    - **Validates: Requirements 3.2, 3.8**

  - [x]* 9.8 Write unit tests for renderer and output writer
    - `MarkdownRenderer` produces non-empty string for a valid `ConversionResult`
    - Custom `BaseRenderer` subclass can be passed and its output is used
    - Correct `md_embedded/` paths with URL encoding
    - Output directory created when missing
    - Existing output file triggers stderr warning
    - _Requirements: 3.1–3.8, 10.1–10.2, 10.6_

- [x] 10. Implement CLI entry point and batch loop
  - [x] 10.1 Implement `doc2md.py` CLI entry point
    - Parse `file [file ...]`, `--output`, `--verbose` with `argparse`
    - Use `document2markdown.utils` for multi-file processing
    - Catch and report errors per file; continue on failure
    - Print per-file progress when `--verbose` is set
    - Print batch summary to stdout: total, succeeded, failed counts
    - Exit with non-zero status if any file failed
    - _Requirements: 3.1–3.5, 4.1–4.5, 5.1–5.4_

  - [x]* 10.2 Write property test for batch mode — Property 7: Batch mode processes all files independently
    - **Property 7: Batch mode processes all files independently**
    - **Validates: Requirements 4.2, 4.3, 4.4, 5.3**

  - [x]* 10.3 Write unit tests for CLI and batch loop
    - Batch summary counts accurate for mixed success/failure runs
    - Non-existent file logged and counted as failure; remaining files processed
    - `--verbose` flag triggers per-file progress output
    - _Requirements: 4.1–4.4, 5.1–5.4_

- [x] 11. Implement public module API
  - [x] 11.1 Implement `Document` class (`document2markdown/document.py`)
    - Wraps source path and `ConversionResult`
    - `.result` property, `.warnings` property, `.to_markdown() -> str`, `.save(output=None)`
    - _Requirements: 8.1–8.3_

  - [x] 11.2 Implement `Converter` class (`document2markdown/api.py`) — preferred interface
    - Accepts `output_dir`, `raster_dpi`, `verbose`, `renderer` (default `MarkdownRenderer`) at init
    - `.convert(path) -> Document` — one file per call; use `utils` for batch convenience
    - _Requirements: 8.1–8.3, 10.3_

  - [x] 11.3 Implement utilities layer (`document2markdown/utils.py`)
    - `convert_batch(paths, converter) -> list[tuple[Path, Document | Exception]]`
    - `convert_directory(directory, converter, pattern="*") -> list[tuple[Path, Document | Exception]]`
    - _Requirements: 4.1–4.5_

  - [x] 11.4 Implement functional API in `document2markdown/__init__.py`
    - `convert_file`, `to_markdown`, `convert_to_markdown` — all accept optional `renderer` arg, default `MarkdownRenderer`
    - Delegate to `Converter`/`Document` internally
    - Refactor `doc2md.py` to use `Converter` and `utils` internally
    - _Requirements: 9.1–9.7, 10.3_

  - [x] 11.5 Add `pyproject.toml` for pip-installable packaging
    - Define package name, version, dependencies, and entry point (`doc2md = document2markdown.cli:main`)
    - _Requirements: 9.7_

  - [x]* 11.6 Write unit tests for OO API, utilities, and functional API
    - `Converter.convert` returns a `Document` with non-empty result
    - `convert_batch` continues on failure and returns one entry per input
    - `convert_directory` returns entries for all matching files
    - `Document.to_markdown()` returns non-empty string
    - `Document.save()` writes `.md` and `md_embedded/` correctly
    - `convert_file` with no output writes no files; with output writes correctly
    - _Requirements: 8.1–8.3, 9.1–9.5, 4.1–4.5_

- [x] 12. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. End-to-end integration and output quality validation
  - [x] 13.1 Write integration tests for all five formats
    - Convert a real sample PDF, DOCX, HTML, PPTX, and TXT file end-to-end
    - Assert output `.md` files exist, are non-empty, and decode as UTF-8
    - Assert embedded assets are in `md_embedded/` with correct `{base_name}_{serial:04d}{ext}` naming
    - Assert a DOCX/PPTX with an EMF/WMF graphic produces a `.svg` asset
    - Assert batch summary format on stdout
    - Assert a `.docx` file with PDF magic bytes is rejected with a mismatch error on stderr
    - _Requirements: 1.1–1.5, 2.6–2.8, 3.6, 4.3, 6.1, 7.2_

  - [x]* 13.2 Write property test — Property 1: Supported format produces output file
    - **Property 1: Supported format produces output file**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    - _Implemented in tests/test_property_formats.py_

  - [x]* 13.3 Write property test — Property 3: Output is valid UTF-8
    - **Property 3: Output is valid UTF-8**
    - **Validates: Requirements 6.1**
    - _Implemented in tests/test_property_formats.py_

- [x] 14. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis` with a minimum of 100 iterations per property
- Each property test is tagged with a comment: `# Feature: document-to-markdown, Property N: <title>`
- `VectorConverter` is shared by `DOCXConverter`, `PPTXConverter`, and `PDFConverter`
- `RASTER_DPI` default (300) is set in `document2markdown/config.py` and used as the fallback rasterization resolution
- Property 5 (heading round-trip) is implemented in three files: `test_property_html.py`, `test_property_docx.py`, and `test_property_headings.py` (combined)
- Properties 1 and 3 are both implemented in `test_property_formats.py`
- Property 9 (vector → SVG/PNG) is implemented in `test_property_vector.py` (EMF→SVG and EPS→PNG paths)

---

## Output Handling Enhancements (Requirement 3 update, 2026-05-10)

Implement default output directory, directory mirroring, skip-if-newer, `--force`, and configurable directory names. Surgical approach: path resolution stays in the orchestration layer (utils/CLI); the writer's interface changes minimally.

**Design principle:** The writer already receives a resolved `output_dir: Path`. That pattern stays. New logic (default dir name, mirroring, skip-if-newer) lives in `utils.py` and `doc2md.py` — the layers that already decide *where* to write. The writer gains only `force` and timestamp checking. `EMBEDDED_DIR` in config.py keeps its current role.

- [x] 15. Config constants and `force` on Converter
  - [x] 15.1 Update `document2markdown/config.py`
    - Add `OUTPUT_DIR_NAME: str = "Exports - Conversions"`
    - Keep `EMBEDDED_DIR` as-is (no rename — avoids churn in existing tests)
    - _Requirements: 3.3, 3.9_

  - [x] 15.2 Add `force: bool = False` param to `Converter.__init__` in `api.py`
    - Store as `self._force`; pass to `Document` construction
    - No other new params on Converter — dir name resolution stays in utils/CLI
    - _Requirements: 3.6_

  - [x] 15.3 Add `force` and `skipped` to `Document` in `document.py`
    - Accept `force: bool` in constructor (from Converter)
    - Add `self._skipped: bool = False` with a `@property skipped`
    - `Document.save()` passes `force` to `OutputWriter.write()`; sets `self._skipped` from return value
    - _Requirements: 3.5, 3.6_

- [x] 16. Skip-if-newer logic in the writer
  - [x] 16.1 Add timestamp check to `OutputWriter.write()` in `writer.py`
    - New param: `force: bool = False`
    - Before writing `.md`: if target exists, compare `target.stat().st_mtime` vs `source_path.stat().st_mtime`
      - target newer and not force → skip, print `INFO: {path}: up-to-date, skipping` to stderr, return `(md_path, skipped=True)`
      - target older/equal and not force → overwrite with existing warning (already implemented)
      - force → skip timestamp check entirely
    - Change return type to `tuple[Path, bool]` (path, skipped) — or add a `skipped` field to a small result dataclass
    - No changes to `_write_assets` or `asset_url_path` — `EMBEDDED_DIR` usage unchanged
    - _Requirements: 3.5, 3.6, 3.7_

  - [ ]* 16.2 Write property test — Property 11: Skip-if-newer timestamp logic
    - **Validates: Requirements 3.5, 3.6**

  - [ ]* 16.3 Write unit tests for skip-if-newer
    - Target newer → skip + informational stderr
    - Target older → overwrite + warning stderr
    - Target equal mtime → overwrite + warning stderr
    - `force=True` → always overwrite
    - _Requirements: 3.5, 3.6, 3.7_

- [x] 17. Default output directory (orchestration layer)
  - [x] 17.1 Update `Document.save()` default path logic
    - Current: `output_dir` defaults to `source_path.parent`
    - New: when `output_dir is None`, compute `source_path.parent / OUTPUT_DIR_NAME`
    - Import `OUTPUT_DIR_NAME` from config (same pattern as `EMBEDDED_DIR`)
    - Pass resolved path to `writer.write(output_dir=...)`
    - _Requirements: 3.3, 3.8, 3.12_

  - [ ]* 17.2 Write unit tests for default output directory
    - No explicit output → `.md` written to `{source_parent}/Exports - Conversions/`
    - Directory auto-created
    - Relative to source, not CWD (test by running from a different cwd)
    - _Requirements: 3.3, 3.8, 3.12_

- [x] 18. Checkpoint — Ensure existing tests still pass + new tests pass

- [x] 19. Directory structure mirroring (utils layer)
  - [x] 19.1 Update `convert_directory` in `document2markdown/utils.py`
    - Compute `relative = source_path.relative_to(traversed_root)`
    - Resolve output dir: `traversed_root / OUTPUT_DIR_NAME / relative.parent`
    - Pass resolved `output_dir` to `Document.save(output=resolved_dir)` — writer sees a concrete Path, no new params needed
    - Each file gets its own `EMBEDDED_DIR/` alongside its `.md` (already the writer's behavior when given a per-file output_dir)
    - _Requirements: 3.4, 3.8, 3.9_

  - [ ]* 19.2 Write unit tests for directory mirroring
    - `docs/deeper/file.pdf` → `docs/Exports - Conversions/deeper/file.md`
    - `md_embedded/` alongside each `.md` at its depth
    - Missing intermediate dirs created (writer already does `mkdir(parents=True)`)
    - _Requirements: 3.4, 3.8, 3.9_

  - [ ]* 19.3 Write property test — Property 8: Output path derivation with directory mirroring
    - **Validates: Requirements 3.3, 3.4, 3.8, 3.9, 3.12**

- [x] 20. CLI: `--force` flag and `BatchSummary.skipped`
  - [x] 20.1 Add `--force` to argparse in `doc2md.py`
    - Pass `force=True` to `Converter` constructor
    - _Requirements: 3.6_

  - [x] 20.2 Add `skipped` count to batch summary in `doc2md.py`
    - After each conversion, check `doc.skipped`; increment skipped counter
    - Print in summary line: `N converted, M skipped, K failed`
    - _Requirements: 3.5, 3.6_

  - [x] 20.3 Wire default output dir into CLI (no `--output` case)
    - When `--output` not provided and input is a directory → use `convert_directory` with mirroring
    - When `--output` not provided and input is file(s) → `Document.save()` uses its new default (task 17.1)
    - When `--output` provided → pass as explicit `output_dir` (existing behavior)
    - _Requirements: 3.3, 3.4_

  - [ ]* 20.4 Write unit tests for CLI changes
    - `--force` parsed and passed
    - Skipped count in summary
    - No `--output` → default dir used
    - _Requirements: 3.5, 3.6_

- [x] 21. Config file support for directory names
  - [x] 21.1 Add `load_config()` to `document2markdown/config.py`
    - Read `[tool.document2markdown]` from `pyproject.toml` (if present in CWD or parents)
    - Return dict with `output_dir_name` and `assets_dir_name` (falling back to module constants)
    - _Requirements: 3.10_

  - [x] 21.2 Wire config into `Document.save()` and `convert_directory`
    - On first call, load config once; use `output_dir_name` from config when computing default paths
    - Constructor/explicit params still override (Converter stores explicit values; if set, they win)
    - `EMBEDDED_DIR` in writer stays as-is for now — config override for assets dir is a stretch goal
    - _Requirements: 3.10_

  - [ ]* 21.3 Write property test — Property 12: Configurable directory names with precedence
    - **Validates: Requirements 3.10**

  - [ ]* 21.4 Write unit tests for config loading and precedence
    - Config values used when no explicit override
    - Explicit override wins
    - Missing config → built-in defaults
    - _Requirements: 3.10_

- [ ] 22. Integration tests and regression verification
  - [ ]* 22.1 Write integration tests for full output handling flow
    - Single file no `--output` → `Exports - Conversions/` relative to source
    - Directory → mirrored structure
    - Skip-if-newer → newer output skipped
    - `--force` → reconverts
    - All existing 200+ tests still pass
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 3.8, 3.9, 3.10_

- [x] 23. Final checkpoint — All tests pass (existing + new)

## Task Dependency Graph (Tasks 15–23)

```json
{
  "waves": [
    { "id": 0, "tasks": ["15.1"] },
    { "id": 1, "tasks": ["15.2", "15.3"] },
    { "id": 2, "tasks": ["16.1"] },
    { "id": 3, "tasks": ["16.2", "16.3", "17.1"] },
    { "id": 4, "tasks": ["17.2", "18"] },
    { "id": 5, "tasks": ["19.1", "20.1", "20.2", "20.3"] },
    { "id": 6, "tasks": ["19.2", "19.3", "20.4", "21.1"] },
    { "id": 7, "tasks": ["21.2", "21.3", "21.4"] },
    { "id": 8, "tasks": ["22.1", "23"] }
  ]
}
```
