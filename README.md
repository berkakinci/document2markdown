# document2markdown

Convert PDF, DOCX, HTML, PPTX, and TXT documents to clean Markdown.

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

| Extension | Library |
|-----------|---------|
| `.pdf` | PyMuPDF + pymupdf4llm |
| `.docx` | python-docx |
| `.html`, `.htm` | BeautifulSoup4 + markdownify |
| `.pptx` | python-pptx |
| `.txt` | stdlib |

Vector images (EMF/WMF → SVG via Inkscape; EPS → PNG via Ghostscript+Pillow) are extracted automatically from DOCX/PPTX.
