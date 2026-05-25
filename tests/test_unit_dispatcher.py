"""Unit tests for the format dispatcher."""
import tempfile
from pathlib import Path

import pytest

from document2markdown.dispatcher import resolve_converter, EXTENSION_TO_MIME
from document2markdown.errors import UnsupportedFormatError, MimeExtensionMismatchError
from document2markdown.converter_txt import TXTConverter
from document2markdown.converter_html import HTMLConverter


def _write(suffix: str, content: bytes) -> Path:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        return Path(f.name)


def test_txt_extension_resolves_txt_converter():
    path = _write(".txt", b"hello world")
    assert resolve_converter(path) is TXTConverter


def test_html_extension_resolves_html_converter():
    path = _write(".html", b"<html><body>hi</body></html>")
    assert resolve_converter(path) is HTMLConverter


def test_htm_extension_resolves_html_converter():
    path = _write(".htm", b"<html><body>hi</body></html>")
    assert resolve_converter(path) is HTMLConverter


def test_unsupported_extension_raises():
    # Use binary content that libmagic won't classify as any known MIME type.
    # A sequence of null bytes is detected as "application/octet-stream" which
    # is not in _KNOWN_MIMES, so both extension and magic are unknown → raises.
    path = _write(".xyz", b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f")
    with pytest.raises(UnsupportedFormatError):
        resolve_converter(path)


def test_mismatch_raises_with_both_types():
    # Write PDF bytes but give it a .txt extension
    pdf_header = b"%PDF-1.4 fake pdf content"
    path = _write(".txt", pdf_header)
    with pytest.raises((MimeExtensionMismatchError, UnsupportedFormatError)):
        resolve_converter(path)


def test_extension_to_mime_has_all_formats():
    expected = {".pdf", ".docx", ".html", ".htm", ".pptx", ".txt", ".xlsx"}
    assert expected == set(EXTENSION_TO_MIME.keys())
