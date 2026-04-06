"""Script-level configuration constants for document2markdown."""

# DPI used when rasterizing vector graphics as a final fallback.
# Can be overridden at runtime by passing raster_dpi to Converter().
RASTER_DPI: int = 300

# Subdirectory name used for extracted embedded assets (relative to the
# output .md file).
EMBEDDED_DIR: str = "md_embedded"

# Maximum consecutive blank lines allowed in Markdown output.
MAX_CONSECUTIVE_BLANK_LINES: int = 2
