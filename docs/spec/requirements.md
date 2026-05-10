# Requirements Document

## Introduction

A Python command-line script that converts documents in various formats (PDF, DOCX, HTML, PPTX, and plain text) into clean Markdown files suitable for consumption by AI assistants such as Kiro. The script preserves document structure (headings, lists, tables, code blocks, images) as faithfully as possible, handles batch conversion, and reports errors clearly so users can act on them.

## Glossary

- **Converter**: The Python script responsible for accepting input documents and producing Markdown output.
- **Source_Document**: A file in a supported input format (PDF, DOCX, HTML, PPTX, TXT) provided to the Converter.
- **Markdown_Output**: A UTF-8 encoded `.md` file produced by the Converter that represents the content of a Source_Document.
- **Supported_Format**: One of the file types the Converter is capable of processing: PDF, DOCX, HTML, PPTX, TXT.
- **Batch_Mode**: An operating mode in which the Converter processes multiple Source_Documents in a single invocation.
- **Structure**: Document elements including headings, paragraphs, ordered and unordered lists, tables, hyperlinks, and code blocks.

---

## Requirements

### Requirement 1: Format Support

**User Story:** As a developer, I want to convert PDF, DOCX, HTML, PPTX, and TXT files to Markdown, so that I can feed diverse document types into Kiro without manual reformatting.

#### Acceptance Criteria

1. WHEN a Source_Document with a `.pdf` extension is provided, THE Converter SHALL extract text and Structure and write a Markdown_Output file.
2. WHEN a Source_Document with a `.docx` extension is provided, THE Converter SHALL extract text and Structure and write a Markdown_Output file.
3. WHEN a Source_Document with a `.html` or `.htm` extension is provided, THE Converter SHALL extract text and Structure and write a Markdown_Output file.
4. WHEN a Source_Document with a `.pptx` extension is provided, THE Converter SHALL extract slide titles and body text in slide order and write a Markdown_Output file.
5. WHEN a Source_Document with a `.txt` extension is provided, THE Converter SHALL wrap the content in a fenced code block or plain paragraphs and write a Markdown_Output file.
6. IF a Source_Document has an unsupported file extension, THEN THE Converter SHALL exit with a non-zero status code and print a descriptive error message identifying the unsupported format.
7. THE Converter SHALL exit with a non-zero status code whenever any error message is printed to stderr, regardless of whether the file format is supported.

---

### Requirement 2: Structure Preservation

**User Story:** As a developer, I want the converted Markdown to preserve the original document's structure, so that headings, lists, tables, images and other elements remain navigable and readable by Kiro.

#### Acceptance Criteria

1. WHEN a Source_Document contains heading elements (e.g., H1–H6 in HTML/DOCX, slide titles in PPTX), THE Converter SHALL map them to the corresponding ATX Markdown heading levels (`#` through `######`).
2. WHEN a Source_Document contains ordered or unordered lists, THE Converter SHALL render them as Markdown ordered (`1.`) or unordered (`-`) lists respectively.
3. WHEN a Source_Document contains a table, THE Converter SHALL render it as a GitHub-Flavored Markdown pipe table.
4. WHEN a Source_Document contains hyperlinks, THE Converter SHALL render them as Markdown inline links (`[text](url)`).
5. WHEN a Source_Document contains a code block or preformatted text region, THE Converter SHALL render it as a fenced Markdown code block (triple backtick).
6. WHEN a Source_Document contains an image, THE Converter SHALL insert an inline Markdown image with the original filename or alt text (`![alt](filename)`).
7. WHEN a Source_Document contains a renderable embedded element (e.g. an image), THE Converter SHALL extract the element into a file and link or render it inline.
8. WHEN a Source_Document contains an embedded vector graphic (e.g. EMF, WMF, EPS, or native drawing objects), THE Converter SHALL attempt to convert it to SVG. If SVG conversion fails, THE Converter SHALL rasterize the graphic to PNG at a configurable DPI (default 300, set via script-level configuration) as a final fallback, and save it as an extracted embedded asset.
9. WHEN a Source_Document contains an element not supported for or not renderable, THE Converter SHALL place a brief note about the original element and reason it is not included.

---

### Requirement 3: Output Handling

**User Story:** As a developer, I want control over where the Markdown output is written, so that I can integrate the script into existing workflows and directory structures.

#### Acceptance Criteria

1. THE Converter SHALL accept a `--output` CLI argument specifying a target file path or directory for the Markdown_Output.
2. WHEN `--output` specifies a directory, THE Converter SHALL write each Markdown_Output file into that directory using the Source_Document's base name with a `.md` extension.
3. WHEN `--output` is not provided, THE Converter SHALL write all Markdown_Output files into a directory named `Exports - Conversions/` that is always relative to the source — specifically at the root of the traversed directory tree (for directory conversion) or as a sibling of the Source_Document (for single-file conversion).  The default output directory SHALL NOT be relative to the current working directory.  This directory SHALL be created once per invocation — not per source file.
4. WHEN converting a directory tree, THE Converter SHALL mirror the subdirectory structure of the source tree within the output directory.  Source_Documents in subdirectories of the traversed root SHALL produce Markdown_Output files in corresponding subdirectories within `Exports - Conversions/`.  For example, converting `docs/` containing `docs/deeper/pdftoo.pdf` SHALL produce `docs/Exports - Conversions/deeper/pdftoo.md`.
5. IF the target output file already exists and has a filesystem modification timestamp newer than the Source_Document's modification timestamp, THEN THE Converter SHALL skip conversion for that file and print an informational message to stderr indicating the file was skipped.  THE Converter SHALL base the skip decision solely on timestamps without validating the content or format of the existing target file.
6. THE Converter SHALL accept a `--force` CLI flag that, WHEN enabled, causes THE Converter to reconvert all files regardless of modification timestamps.
7. WHEN `--force` is not set and the target output file exists with a modification timestamp older than or equal to the Source_Document's modification timestamp, THE Converter SHALL overwrite the file and print a warning message to stderr.
8. IF the target output directory does not exist, THEN THE Converter SHALL create it (including any necessary subdirectories) before writing the Markdown_Output file.
9. WHEN the Source_Document contains embedded elements, THE Converter SHALL extract the embedded elements into a subdirectory named according to the configured assets directory name (default: `md_embedded`) located alongside the corresponding Markdown_Output file at whatever depth it appears in the mirrored directory structure.  The assets subdirectory SHALL NOT be a single shared directory at the output root.  The extracted files SHALL have the Source_Document's base name as a prefix with an incrementing 4-digit serial number and appropriate extensions.  For example, converting `docs/deeper/pdftoo.pdf` SHALL produce assets at `docs/Exports - Conversions/deeper/md_embedded/pdftoo_0001.png`.
10. THE Converter SHALL support configuration of the default output directory name (default: `Exports - Conversions`) and the assets subdirectory name (default: `md_embedded`) via a configuration file and/or constructor parameters passed to the OO API.
11. WHEN both a configuration file and constructor parameters specify directory names, THE constructor parameters SHALL take precedence over configuration file values.
12. IF the Markdown_Output has links and inline references to the extracted elements, THE Converter SHALL use relative paths in the links.  The links SHALL be URL Encoded.
13. THE Converter SHALL not modify file names, base names, or prefixes used in paths.  THE Converter SHALL use proper quoting to handle any spaces or special characters that may occur on the filesystem.

---

### Requirement 4: Batch and Directory Conversion

**User Story:** As a developer, I want to convert multiple documents or entire directories in a single command, so that I can process large sets of files without running the script repeatedly.

#### Acceptance Criteria

1. A utilities layer (`document2markdown.utils`) SHALL provide helper functions for batch and directory conversion, built on top of the core single-file API.
2. THE utilities layer SHALL provide a function to convert a list of file paths, processing each independently and continuing on failure.
3. THE utilities layer SHALL provide a function to convert all supported files in a directory.
4. WHEN processing multiple files, THE utilities layer SHALL collect results and errors per file and return a summary.
5. THE CLI (`doc2md.py`) SHALL use the utilities layer for multi-file and directory support.

---

### Requirement 5: Error Handling and Reporting

**User Story:** As a developer, I want clear error messages when conversion fails, so that I can diagnose and fix problems quickly.

#### Acceptance Criteria

1. IF a Source_Document cannot be read due to a permissions error, THEN THE Converter SHALL print a descriptive error message to stderr identifying the file and the reason, and SHALL exit with a non-zero status code.
2. IF a Source_Document is corrupt or cannot be parsed, THEN THE Converter SHALL print a descriptive error message to stderr identifying the file and exit with a non-zero status code for that file.  IF the error message itself cannot be printed, THE Converter SHALL still exit with a non-zero status code.
3. WHEN an error occurs for one file in Batch_Mode, THE Converter SHALL continue processing remaining files and include the failed file in the final summary.
4. THE Converter SHALL support a `--verbose` CLI flag that, WHEN enabled, causes THE Converter to print progress information for each file being processed.

---

### Requirement 6: Output Quality

**User Story:** As a developer, I want the Markdown output to be clean and well-formed, so that Kiro can parse and reason over it without noise or formatting artifacts.

#### Acceptance Criteria

1. THE Converter SHALL produce Markdown_Output files encoded in UTF-8.
2. THE Converter SHALL strip extraneous whitespace, repeated blank lines (more than two consecutive), and non-printable control characters from the Markdown_Output.  Exceptions MAY be made for semantic spacing between major document sections where additional blank lines improve readability.
3. WHEN processing any Source_Document, THE Converter SHALL linearize text into a consistent single reading-order column, regardless of whether the original layout is single-column or multi-column.
4. THE Converter SHALL NOT include page numbers, headers, or footers extracted from PDF or DOCX files in the Markdown_Output.

---

### Requirement 7: File Type Detection

**User Story:** As a developer, I want the Converter to reliably identify file types even when extensions are missing or incorrect, so that files are routed to the correct converter without manual intervention.

#### Acceptance Criteria

1. THE Converter SHALL determine the file type using the following detection methods:
   a. File extension (e.g. `.pdf`, `.docx`).
   b. MIME type via magic byte inspection (using `python-magic` / `libmagic`).
2. IF file extension is known, THE Converter SHALL verify the type determined by all detection methods match.  IF the types do not match, THE Converter SHALL treat the file as unsupported and log an error to stderr identifying the file and the detected mismatching types.
3. IF the file type cannot be determined by any method, THE Converter SHALL treat the file as unsupported and follow the unsupported format error behavior (Requirement 1.6).

---

### Requirement 8: Object-Oriented API

**User Story:** As a developer, I want an object-oriented interface to the converter as the primary way to use the library, so that I can share configuration and convert one document at a time in a fluent way.

#### Acceptance Criteria

1. THE core library API converts one file per call. `document2markdown.utils` provides convenience helpers for batch and directory use cases.
2. THE public API SHALL provide a class-based interface that accepts configuration at instantiation and converts a single file.
3. Conversion results SHALL be accessible as objects that expose the intermediate representation, the rendered string, and the ability to write output to disk.

---

### Requirement 9: Functional API

**User Story:** As a developer, I want a functional interface to the converter for simple one-off conversions, so that I can convert a document without instantiating a class.

#### Acceptance Criteria

1. THE `document2markdown` package SHALL be importable and usable without invoking the CLI.
2. THE functional API SHALL expose the full conversion pipeline as convenience functions, returning both the intermediate representation and the final rendered string.
3. WHEN called without an output path, THE API SHALL NOT write any files to disk.  The API SHALL still return the intermediate representation and rendered string in memory.
4. WHEN called with an output path, THE API SHALL write the Markdown output and embedded assets to disk following the same rules as the CLI (Requirement 3), but SHALL only write files when conversion succeeds and produces meaningful output.
5. THE functional API SHALL delegate to the OO API internally rather than duplicating pipeline logic.
6. THE `doc2md.py` CLI SHALL use the OO API internally rather than duplicating pipeline logic.
7. THE package SHALL be installable as a standalone library via `pip install` using a `pyproject.toml`.

---

### Requirement 10: Pluggable Output Renderer

**User Story:** As a developer, I want to plug in different output renderers so that I can produce different flavors of Markdown or entirely different output formats from the same conversion pipeline.

#### Acceptance Criteria

1. THE output rendering step SHALL be abstracted behind an interface that third-party code can implement.
2. THE package SHALL provide a default Markdown renderer.
3. THE API SHALL accept a custom renderer in place of the default.
