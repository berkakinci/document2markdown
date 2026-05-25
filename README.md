# document2markdown

Convert PDF, DOCX, HTML, PPTX, XLSX, and TXT documents to clean Markdown.

## Install

```bash
pip install -e .
```

Requires: Python 3.12+, Inkscape (for EMF/WMF), Ghostscript (for EPS).

## Object Oriented API

```python
from pathlib import Path
from document2markdown import Converter

converter = Converter(force=False, verbose=True)
doc = converter.convert(Path("report.pdf"))

md = doc.to_markdown()               # string
saved_path = doc.save()              # default dir (Exports - Conversions/)
saved_path = doc.save(Path("out/"))  # explicit dir
```

### Batch and directory helpers

```python
from pathlib import Path
from document2markdown import Converter
from document2markdown.utils import convert_batch, convert_directory

converter = Converter()
results = convert_batch([Path("a.pdf"), Path("b.docx")], converter)
results = convert_directory(Path("docs/"), converter, pattern="**/*")
# results: list[tuple[Path, Document | Exception]]
```

### Custom renderer

```python
from document2markdown import Converter, BaseRenderer

class MyRenderer(BaseRenderer):
    def render(self, result):
        return "...custom output..."

converter = Converter(renderer=MyRenderer())
```

## Functional API

```python
from pathlib import Path
from document2markdown import convert_to_markdown, convert_file, to_markdown

# Convert and return Markdown string (no disk I/O)
md = convert_to_markdown(Path("report.pdf"))

# Convert and write to disk
result = convert_file(Path("report.pdf"), output=Path("out/"))

# Render an existing ConversionResult
md = to_markdown(result)
```

## CLI

```bash
# Single file → default output dir (Exports - Conversions/ next to source)
python doc2md.py path/to/file.pdf

# Multiple files
python doc2md.py a.pdf b.docx c.pptx

# Directory (recursive, mirrors source structure)
python doc2md.py path/to/dir

# Explicit output, force reconversion, verbose progress
python doc2md.py --output out_dir --force --verbose path/to/file.pdf
```

Outputs `.md` files plus an `md_embedded/` folder for extracted images. Skips files whose output is newer than the source unless `--force` is set.

## Supported formats

| Extension | Library | Output |
|-----------|---------|--------|
| `.pdf` | PyMuPDF + pymupdf4llm | Markdown (OCR via Tesseract for scanned pages) |
| `.docx` | python-docx | Markdown |
| `.html`, `.htm` | BeautifulSoup4 + markdownify | Markdown |
| `.pptx` | python-pptx | Markdown |
| `.xlsx` | openpyxl | Markdown index + CSV per sheet |
| `.txt` | stdlib | Markdown |

Vector images (EMF/WMF → SVG via Inkscape; EPS → PNG via Ghostscript+Pillow) are extracted automatically from DOCX/PPTX.

## Known gaps / future work

- **`.xml` (C-CDA / XHTML)** — `INDEX.HTM` files that are actually XHTML fail with a mime-type mismatch. Low priority since these are typically navigation boilerplate in IHE XDM exports.
- **`.xls`** (legacy binary Excel) — not supported. Only `.xlsx` (Open XML) is handled.
- **XLSX charts** — stored as XML definitions, not rendered images. Cannot be exported without a rendering engine (e.g., LibreOffice headless).
- **Large XLSX files** (>50MB / >100K rows) — standard openpyxl mode loads all cells into memory. Could be optimized with `read_only=True` for data-only sheets.
