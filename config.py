"""Script-level configuration constants for document2markdown."""

import shutil

# Path to the Inkscape binary.  Searches PATH first; falls back to the
# standard macOS .app bundle location so the module works out of the box
# without requiring any system PATH changes.
INKSCAPE_PATH: str = shutil.which("inkscape") or "/Applications/Inkscape.app/Contents/MacOS/inkscape"

# DPI used when rasterizing vector graphics as a final fallback.
# Can be overridden at runtime by passing raster_dpi to Converter().
RASTER_DPI: int = 300

# Subdirectory name used for extracted embedded assets (relative to the
# output .md file).
EMBEDDED_DIR: str = "md_embedded"

# Maximum consecutive blank lines allowed in Markdown output.
MAX_CONSECUTIVE_BLANK_LINES: int = 2
