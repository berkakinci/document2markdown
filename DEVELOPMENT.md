# Development Guide

## Environment setup

The project uses a conda environment:

```bash
conda create -n document2markdown python=3.12
conda activate document2markdown
pip install -e ".[dev]"
```

External tools (install separately):

| Tool | Purpose | Install |
|------|---------|---------|
| Tesseract | PDF OCR | `brew install tesseract` |
| Inkscape | EMF/WMF → SVG | Download from inkscape.org or `brew install --cask inkscape` |
| Ghostscript | EPS → PNG | `brew install ghostscript` |

Inkscape and Ghostscript are only exercised by the live vector tests. The rest of the suite runs without them.

## Project structure

```
document2markdown/        ← Python package
  __init__.py             ← public API surface (Converter, Document, convert_*)
  api.py                  ← OO API (Converter, Document)
  dispatcher.py           ← routes files to the correct converter by extension + magic bytes
  document_model.py       ← intermediate representation (IR) block types
  converter_base.py       ← BaseConverter
  converter_pdf.py        ← PDF via PyMuPDF + pymupdf4llm
  converter_docx.py       ← DOCX via python-docx
  converter_html.py       ← HTML via BeautifulSoup4 + markdownify
  converter_pptx.py       ← PPTX via python-pptx
  converter_xlsx.py       ← XLSX via openpyxl
  converter_txt.py        ← plain text
  converter_vector.py     ← EMF/WMF → Inkscape SVG; EPS → Pillow+Ghostscript PNG
  renderer_base.py        ← BaseRenderer + MarkdownRenderer (IR → Markdown string)
  postprocess.py          ← post-conversion cleanup (whitespace, page numbers, etc.)
  writer.py               ← writes .md + md_embedded/ to disk
  utils.py                ← batch and directory helpers
  config.py               ← constants (output dir names, tool paths, thresholds)
  errors.py               ← exception hierarchy
  document.py             ← Document result object

tests/                    ← full test suite
  test_unit_*.py          ← unit tests per module
  test_property_*.py      ← property-based tests (Hypothesis)
  test_integration.py     ← end-to-end for all 5 formats
  test_live_vector.py     ← live integration tests (require Inkscape + Ghostscript)

test_fixtures/            ← binary fixtures for vector tests (EMF, WMF, EPS)
docs/spec/                ← requirements, design, tasks specs
doc2md.py                 ← CLI entry point (thin wrapper over utils layer)
```

## Running tests

```bash
conda activate document2markdown

# Full suite (excludes live vector tests)
python -m pytest tests/

# With coverage
python -m pytest tests/ --cov=document2markdown --cov-report=term-missing

# Live vector tests (requires Inkscape + Ghostscript on PATH or configured in config.py)
python -m pytest tests/test_live_vector.py

# Single module
python -m pytest tests/test_unit_pdf.py
```

Run from the project root (`Scripts and Utilities/document2markdown/`).

## Architecture notes

**Pipeline:** `Dispatcher` → `Converter` → IR (`document_model`) → `Renderer` → `Postprocessor` → `Writer`

- Each converter produces a list of IR blocks (headings, paragraphs, tables, images, etc.) rather than Markdown directly. This decouples extraction from rendering.
- The `Renderer` is pluggable — swap in a custom `BaseRenderer` subclass to produce non-Markdown output.
- The CLI and functional API both delegate to the `utils` layer (`convert_batch`, `convert_directory`); neither touches the pipeline directly.
- File type detection uses extension + magic-byte cross-validation — both must agree before dispatch.

**PDF converter:** Uses `pymupdf4llm.parse_document()` for layout analysis (neural-network based) and `IdentifyHeaders` for heading level detection. OCR is applied automatically to image-only pages via Tesseract. This replaced ~750 lines of custom heuristics in May 2026.

**Vector image handling:**
- EMF/WMF: Inkscape → SVG (PNG fallback if SVG output is empty)
- EPS: Pillow + Ghostscript → PNG (Inkscape 1.4+ on macOS cannot open EPS from CLI)
- Binary auto-detection via `python-magic`; path resolution via `_find_inkscape()` / `_find_gs()` in `converter_vector.py`

**Output layout:**
```
source_dir/
  Exports - Conversions/
    subdir/
      file.md
      md_embedded/
        file_0001.png
        ...
```
Output always lands in `Exports - Conversions/` relative to the source. Directory structure is mirrored. Configurable via `config.py` constants (`OUTPUT_DIR_NAME`, `ASSETS_DIR_NAME`).

## Spec and design docs

Full requirements, design decisions, and task history are in `docs/spec/`:

- `requirements.md` — EARS-format requirements
- `design.md` — architecture, data flow, correctness properties
- `tasks.md` — implementation task breakdown and status
