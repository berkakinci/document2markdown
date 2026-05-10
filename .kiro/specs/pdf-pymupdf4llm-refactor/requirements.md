# Requirements: PDF Converter Refactor → pymupdf4llm

Replace ~750 lines of custom heuristics in `converter_pdf.py` with `pymupdf4llm`'s `parse_document()` and `IdentifyHeaders`. Public API unchanged.

## Requirements

### 1. Dependency
- `pymupdf4llm` is a hard dependency in `requirements.txt` and `pyproject.toml` (unpinned)
- Missing install → `ImportError` with install instructions

### 2. Layout analysis
- Use `parse_document(doc, embed_images=True, image_dpi=raster_dpi)` for page classification
- If it fails → empty ConversionResult + warning

### 3. Heading levels
- Use `IdentifyHeaders(doc)` for font-size → heading level mapping
- Fallback: title → H1, section-header → H2
- If IdentifyHeaders fails → use fallbacks + warning

### 4. Box-to-block mapping
| boxclass | IR Block |
|----------|----------|
| title | HeadingBlock (level from IdentifyHeaders) |
| section-header | HeadingBlock (level from IdentifyHeaders) |
| text | ParagraphBlock |
| caption | ParagraphBlock |
| footnote | ParagraphBlock |
| list-item | ListBlock (accumulated) |
| picture | ImageBlock + EmbeddedAsset |
| table | TableBlock |
| page-header | skip |
| page-footer | skip |

### 5. List accumulation
- Consecutive list-item boxes → single ListBlock
- Flush on non-list-item or page boundary
- Detect ordered vs unordered from text patterns

### 6. Images
- `box.image` bytes → EmbeddedAsset (extension=".png")
- ImageBlock references correct asset_index
- None image → skip + warning

### 7. Tables
- `box.table["extract"]` → first row = headers, rest = data rows
- None cells → empty strings
- Malformed/missing → skip + warning

### 8. Error handling
- `convert()` never raises — always returns ConversionResult
- Individual box failures → skip + warning, continue processing
- fitz.open() failure → empty result + warning
- parse_document() failure → empty result + warning

### 9. Backward compatibility
- PDFConverter remains a BaseConverter subclass
- Same constructor signature (`raster_dpi` param)
- Same return type (ConversionResult with same Block types)
- Existing integration and property tests pass unchanged
