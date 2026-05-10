# Requirements: document-to-markdown

Python CLI + library that converts PDF, DOCX, HTML, PPTX, and TXT into clean Markdown for AI consumption. Preserves structure, handles batch conversion, reports errors clearly.

## Glossary

- **Converter** — the script/library performing conversion
- **Source_Document** — input file in a supported format
- **Markdown_Output** — resulting UTF-8 `.md` file
- **Supported_Format** — PDF, DOCX, HTML, PPTX, TXT
- **Batch_Mode** — multiple files processed in one invocation
- **Structure** — headings, paragraphs, lists, tables, hyperlinks, code blocks

---

## Requirements

### 1. Format Support

**Story:** Convert PDF, DOCX, HTML, PPTX, and TXT to Markdown without manual reformatting.

#### Criteria

1. `.pdf` → extract text + structure → `.md`
2. `.docx` → extract text + structure → `.md`
3. `.html`/`.htm` → extract text + structure → `.md`
4. `.pptx` → extract slide titles + body in slide order → `.md`
5. `.txt` → wrap in fenced code block or plain paragraphs → `.md`
6. Unsupported extension → non-zero exit + descriptive stderr message identifying the format
7. Any stderr error message → non-zero exit code

---

### 2. Structure Preservation

**Story:** Preserve headings, lists, tables, images, and other elements so output is navigable and readable.

#### Criteria

1. Headings (H1–H6, slide titles) → ATX Markdown (`#`–`######`)
2. Ordered/unordered lists → Markdown `1.` / `-` lists
3. Tables → GFM pipe tables
4. Hyperlinks → `[text](url)`
5. Code blocks / preformatted text → fenced code blocks (triple backtick)
6. Images → `![alt](filename)` with extracted file
7. Renderable embedded elements → extract to file + inline link/image
8. Vector graphics (EMF, WMF, EPS, native drawings) → SVG preferred; PNG rasterization at configurable DPI (default 300) as fallback
9. Unsupported/unrenderable elements → brief inline note explaining what was omitted and why

---

### 3. Output Handling

**Story:** Control where output is written; integrate into existing workflows and directory structures.

#### Criteria

1. `--output` CLI arg accepts a target file path or directory.
2. `--output` is a directory → write `{basename}.md` into it.
3. No `--output` → write into `{output_dir_name}/` (default: `Exports - Conversions`), always relative to the source tree root (directory mode) or source file's parent (single-file mode). Never relative to CWD. All output goes into one output directory (not one per source file).
4. Directory conversion mirrors source subdirectory structure inside the output directory. Example: `docs/deeper/file.pdf` → `docs/Exports - Conversions/deeper/file.md`.
5. Skip-if-newer: if target `.md` exists with mtime > source mtime → skip + informational stderr message. Decision based solely on timestamps (no content validation).
6. `--force` flag → reconvert all files regardless of timestamps.
7. Target exists with mtime ≤ source mtime (and no `--force`) → overwrite + stderr warning.
8. Missing output directories (including mirrored subdirectories) → create automatically.
9. Embedded assets → extracted into `{assets_dir_name}/` (default: `md_embedded`) alongside each `.md` at its depth — not a single shared directory at the output root. Files named `{basename}_{0001..NNNN}.{ext}`.
10. `output_dir_name` and `assets_dir_name` are configurable via `pyproject.toml [tool.document2markdown]`. Explicit `output_dir` Path passed to `save()` always wins over the configured default.
11. Links to embedded assets use relative, URL-encoded paths.
12. File names, base names, and path prefixes are never modified. Spaces and special characters handled via proper quoting.

---

### 4. Batch and Directory Conversion

**Story:** Convert multiple documents or entire directories in a single command.

#### Criteria

1. `document2markdown.utils` provides batch/directory helpers on top of the core single-file API.
2. Batch function: converts a list of paths, continues on failure.
3. Directory function: converts all supported files in a directory tree.
4. Returns per-file results/errors and a summary.
5. CLI (`doc2md.py`) uses the utilities layer for multi-file and directory support.

---

### 5. Error Handling and Reporting

**Story:** Clear error messages when conversion fails, so problems can be diagnosed quickly.

#### Criteria

1. Permission error → descriptive stderr message (file + reason) + non-zero exit.
2. Corrupt/unparseable file → descriptive stderr message + non-zero exit. If message itself can't be printed, still exit non-zero.
3. Batch mode error → continue processing remaining files; include failure in final summary.
4. `--verbose` flag → print per-file progress.

---

### 6. Output Quality

**Story:** Clean, well-formed Markdown that AI can parse without noise or formatting artifacts.

#### Criteria

1. Output encoded as UTF-8.
2. Strip extraneous whitespace, >2 consecutive blank lines, and non-printable control characters. Semantic spacing between major sections is allowed.
3. Linearize all layouts (including multi-column) into single reading-order column.
4. Exclude page numbers, headers, and footers from PDF/DOCX output.

---

### 7. File Type Detection

**Story:** Reliably identify file types even when extensions are missing or incorrect.

#### Criteria

1. Detect via: (a) file extension, (b) magic-byte MIME inspection (`python-magic` / `libmagic`).
2. Extension known → verify both methods agree. Mismatch → treat as unsupported + stderr error identifying both detected types.
3. Type undetectable by any method → unsupported format error (per Requirement 1.6).

---

### 8. Object-Oriented API

**Story:** Class-based interface as the primary library entry point — share config, convert one file at a time.

#### Criteria

1. Core API converts one file per call; `document2markdown.utils` provides batch/directory helpers.
2. Class accepts configuration at instantiation, converts a single file.
3. Results expose intermediate representation, rendered string, and disk-write capability.

---

### 9. Functional API

**Story:** Convenience functions for simple one-off conversions without instantiating a class.

#### Criteria

1. Package importable and usable without the CLI.
2. Functions return both intermediate representation and rendered string.
3. No output path → no disk I/O (returns in-memory results only).
4. With output path → writes `.md` + assets per Requirement 3 rules; only writes on successful conversion.
5. Delegates to OO API internally (no duplicated logic).
6. CLI delegates to OO API internally (no duplicated logic).
7. Installable via `pip install` using `pyproject.toml`.

---

### 10. Pluggable Output Renderer

**Story:** Swap in different renderers for alternative Markdown flavors or entirely different output formats.

#### Criteria

1. Rendering abstracted behind an interface third-party code can implement.
2. Default Markdown renderer provided.
3. API accepts a custom renderer in place of the default.
