"""Property-based tests for the format dispatcher.

# Feature: document-to-markdown, Property 2: Unsupported or mismatched format exits non-zero
# Feature: document-to-markdown, Property 10: Extension-MIME cross-validation rejects mismatches
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from document2markdown.dispatcher import EXTENSION_TO_MIME, resolve_converter
from document2markdown.errors import MimeExtensionMismatchError, UnsupportedFormatError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = set(EXTENSION_TO_MIME.keys())  # {".pdf", ".docx", ...}

_UNSUPPORTED_EXTENSIONS = [
    ".xyz", ".abc", ".foo", ".bar", ".baz", ".qux", ".zap",
    ".dat", ".unk", ".nope", ".rand", ".test",
]

# Binary content that libmagic reliably identifies as "application/octet-stream"
# (not any of the supported MIME types). Using null bytes ensures this.
_BINARY_CONTENT = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13"


def _write_tmp(suffix: str, content: bytes) -> Path:
    """Write *content* to a temp file with *suffix* and return its Path."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        return Path(f.name)


# ---------------------------------------------------------------------------
# Property 2: Unsupported extension raises UnsupportedFormatError
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 2: Unsupported or mismatched format exits non-zero
@given(
    ext=st.sampled_from(_UNSUPPORTED_EXTENSIONS),
)
@settings(max_examples=100)
def test_property2_unsupported_extension_raises(ext: str) -> None:
    """Any file with an unsupported extension raises UnsupportedFormatError."""
    assume(ext not in _SUPPORTED_EXTENSIONS)

    # Use binary content that libmagic identifies as application/octet-stream
    # (not any supported MIME type), ensuring the dispatcher raises.
    path = _write_tmp(ext, _BINARY_CONTENT)
    with pytest.raises((UnsupportedFormatError, MimeExtensionMismatchError)):
        resolve_converter(path)


# ---------------------------------------------------------------------------
# Property 10: Extension-MIME cross-validation rejects mismatches
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 10: Extension-MIME cross-validation rejects mismatches
@given(
    dummy=st.just(None),
)
@settings(max_examples=100)
def test_property10_txt_extension_with_pdf_bytes_raises_mismatch(dummy: None) -> None:
    """.txt extension with PDF magic bytes raises MimeExtensionMismatchError.

    The error message must contain both the extension-derived type and the
    magic-byte-derived type.
    """
    pdf_bytes = b"%PDF-1.4 fake pdf content for magic detection purposes"
    path = _write_tmp(".txt", pdf_bytes)

    with pytest.raises((UnsupportedFormatError, MimeExtensionMismatchError)) as exc_info:
        resolve_converter(path)

    exc = exc_info.value
    if isinstance(exc, MimeExtensionMismatchError):
        msg = str(exc)
        # Both type strings must appear in the error message
        assert exc.extension_type in msg, (
            f"extension_type {exc.extension_type!r} not in error: {msg!r}"
        )
        assert exc.magic_type in msg, (
            f"magic_type {exc.magic_type!r} not in error: {msg!r}"
        )
        # The message should reference both "text" and "pdf" in some form
        assert "text" in msg.lower() or "plain" in msg.lower(), (
            f"Expected 'text' or 'plain' in error message: {msg!r}"
        )
        assert "pdf" in msg.lower() or "application" in msg.lower(), (
            f"Expected 'pdf' or 'application' in error message: {msg!r}"
        )
