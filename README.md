# document2markdown

Convert PDF, DOCX, HTML, PPTX, XLSX, and TXT documents to clean Markdown.

## Requirements

- Python 3.12+
- [Tesseract](https://github.com/tesseract-ocr/tesseract) — required for OCR on scanned PDF pages
- [Inkscape](https://inkscape.org/) — required for EMF/WMF vector image extraction (DOCX/PPTX)
- [Ghostscript](https://www.ghostscript.com/) — required for EPS vector image extraction (DOCX/PPTX)

Inkscape and Ghostscript are only needed if your documents contain embedded vector images. Plain text and raster images work without them.

## Install

```bash
pip install -e .
```

## CLI

The fastest way to get started. Run `doc2md.py` from the project root:

```bash
# Single file → outputs to Exports - Conversions/ next to the source file
python doc2md.py path/to/file.pdf

# Multiple files
python doc2md.py a.pdf b.docx c.pptx

# Entire directory (recursive, mirrors source structure)
python doc2md.py path/to/dir/

# Explicit output directory, force reconversion, verbose progress
python doc2md.py --output out_dir --force --verbose path/to/file.pdf
```

Each `.md` output is placed in an `Exports - Conversions/` folder next to the source. Extracted images go into an `md_embedded/` subfolder alongside the `.md` file. Subsequent runs skip files whose output is already newer than the source — use `--force` to override.

## Python API

### Object-oriented

```python
from pathlib import Path
from document2markdown import Converter

converter = Converter(force=False, verbose=True)
doc = converter.convert(Path("report.pdf"))

md = doc.to_markdown()               # return Markdown string
doc.save()                           # write to default dir (Exports - Conversions/)
doc.save(Path("out/"))               # write to explicit dir
```

Batch and directory helpers:

```python
from document2markdown import Converter
from document2markdown.utils import convert_batch, convert_directory

converter = Converter()
results = convert_batch([Path("a.pdf"), Path("b.docx")], converter)
results = convert_directory(Path("docs/"), converter)
# results: list[tuple[Path, Document | Exception]]
```

### Functional

```python
from pathlib import Path
from document2markdown import convert_to_markdown, convert_file

md = convert_to_markdown(Path("report.pdf"))          # string, no disk I/O
result = convert_file(Path("report.pdf"), output=Path("out/"))  # writes to disk
```

## Supported formats

| Extension | Library | Notes |
|-----------|---------|-------|
| `.pdf` | PyMuPDF + pymupdf4llm | OCR via Tesseract for scanned pages |
| `.docx` | python-docx | EMF/WMF vector images via Inkscape |
| `.html`, `.htm` | BeautifulSoup4 + markdownify | |
| `.pptx` | python-pptx | EMF/WMF vector images via Inkscape |
| `.xlsx` | openpyxl | Markdown index + CSV per sheet; images extracted |
| `.txt` | stdlib | |

EPS images in DOCX/PPTX are converted to PNG via Ghostscript + Pillow.

## Known limitations

- **Interrupted ordered lists** — a numbered list split by a non-list paragraph (e.g. a note mid-procedure) restarts numbering from 1. Common in technical documents.
- **PPTX title detection** — only recognizes standard title placeholder types. Presentations that use free-form text boxes for titles produce paragraph blocks instead of headings.
- **PDF OCR** — Tesseract is applied automatically to image-only pages, but pages where the layout classifier splits content into multiple image regions may have incomplete text extraction.
- **`.xls`** — legacy binary Excel is not supported; only `.xlsx` (Open XML).
- **XLSX charts** — stored as XML definitions with no rendered image; cannot be exported without a rendering engine.
- **Large XLSX files** — openpyxl loads all cells into memory; files >50MB or >100K rows may be slow.
- **`.xml` / XHTML** — files with an `.htm`/`.html` extension that are actually XHTML (e.g. IHE XDM health record exports) fail with a mime-type mismatch.

See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture, environment setup, and how to run the tests.
