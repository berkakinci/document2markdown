"""Script-level configuration constants for document2markdown."""

# Fallback path for Inkscape when not found on PATH.
# Standard macOS .app bundle location.
INKSCAPE_FALLBACK: str = "/Applications/Inkscape.app/Contents/MacOS/inkscape"

# Fallback paths for Ghostscript when not found on PATH.
# Apple Silicon Homebrew, then Intel Homebrew / manual install.
GS_FALLBACKS: tuple[str, ...] = ("/opt/homebrew/bin/gs", "/usr/local/bin/gs")

# DPI used when rasterizing vector graphics as a final fallback.
# Can be overridden at runtime by passing raster_dpi to Converter().
RASTER_DPI: int = 300

# Default output directory name (relative to the source file's parent).
# Used by Document.save() and convert_directory() when no explicit output path is given.
OUTPUT_DIR_NAME: str = "Exports - Conversions"

# Subdirectory name used for extracted embedded assets (relative to the
# output .md file).
EMBEDDED_DIR: str = "md_embedded"

# Maximum consecutive blank lines allowed in Markdown output.
MAX_CONSECUTIVE_BLANK_LINES: int = 2
