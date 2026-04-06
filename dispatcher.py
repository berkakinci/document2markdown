"""Format dispatcher for document2markdown.

Determines the appropriate converter for a given file by cross-validating
the file extension MIME type against the magic-byte MIME type.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import magic

from document2markdown.errors import MimeExtensionMismatchError, UnsupportedFormatError

if TYPE_CHECKING:
    from document2markdown.converter_base import BaseConverter

# ---------------------------------------------------------------------------
# Extension → MIME mapping
# ---------------------------------------------------------------------------

EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm":  "text/html",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt":  "text/plain",
}

# Set of all known MIME values (for reverse lookup)
_KNOWN_MIMES: frozenset[str] = frozenset(EXTENSION_TO_MIME.values())


def _get_converters() -> dict[str, type[BaseConverter]]:
    """Lazily import converter classes to avoid circular imports."""
    from document2markdown.converter_pdf import PDFConverter
    from document2markdown.converter_docx import DOCXConverter
    from document2markdown.converter_html import HTMLConverter
    from document2markdown.converter_pptx import PPTXConverter
    from document2markdown.converter_txt import TXTConverter

    return {
        ".pdf":  PDFConverter,
        ".docx": DOCXConverter,
        ".html": HTMLConverter,
        ".htm":  HTMLConverter,
        ".pptx": PPTXConverter,
        ".txt":  TXTConverter,
    }


# Public alias — populated lazily via resolve_converter; exposed for testing.
CONVERTERS: dict[str, type[BaseConverter]] = {}  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

def resolve_converter(path: Path) -> type[BaseConverter]:
    """Return the converter class appropriate for *path*.

    The file extension and magic-byte MIME type are cross-validated:

    * If both are unknown → :class:`~document2markdown.errors.UnsupportedFormatError`
    * If the extension MIME is known but disagrees with the magic MIME →
      :class:`~document2markdown.errors.MimeExtensionMismatchError`
    * Otherwise the converter mapped to the extension is returned.

    Parameters
    ----------
    path:
        Path to the source document (must exist on disk for magic inspection).

    Returns
    -------
    type[BaseConverter]
        The converter class (not an instance) for the detected format.

    Raises
    ------
    UnsupportedFormatError
        When the file type cannot be determined by either method.
    MimeExtensionMismatchError
        When the extension and magic-byte MIME types disagree.
    """
    ext = path.suffix.lower()
    ext_mime: str | None = EXTENSION_TO_MIME.get(ext)

    magic_mime: str = magic.from_file(str(path), mime=True)

    # Normalise magic MIME: strip parameters (e.g. "text/html; charset=utf-8")
    magic_mime_base = magic_mime.split(";")[0].strip()

    # Case 1: both methods unknown → unsupported
    if ext_mime is None and magic_mime_base not in _KNOWN_MIMES:
        raise UnsupportedFormatError(path, magic_mime_base or None)

    # Case 2: extension known but disagrees with magic bytes
    if ext_mime is not None and not magic_mime_base.startswith(ext_mime.split(";")[0]):
        raise MimeExtensionMismatchError(path, ext_mime, magic_mime_base)

    # Case 3: agreement (or extension unknown but magic is known) → route
    # If the extension is unknown but magic is known, find the matching ext.
    if ext_mime is None:
        # magic_mime_base is in _KNOWN_MIMES; find the canonical extension
        for candidate_ext, candidate_mime in EXTENSION_TO_MIME.items():
            if candidate_mime == magic_mime_base:
                ext = candidate_ext
                break

    converters = _get_converters()
    return converters[ext]
