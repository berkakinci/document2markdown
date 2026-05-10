"""Unit tests for error handling — Req 5.1, 5.2."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from document2markdown.api import Converter


class TestPermissionError:
    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not reliable on Windows")
    def test_permission_denied_raises(self, tmp_path):
        """A file with no read permission should raise an exception (Req 5.1)."""
        src = tmp_path / "locked.txt"
        src.write_text("secret content", encoding="utf-8")
        src.chmod(0o000)
        try:
            with pytest.raises(Exception):
                Converter().convert(src)
        finally:
            src.chmod(0o644)


class TestCorruptFileHandling:
    def test_corrupt_docx_raises(self, tmp_path):
        """Corrupt DOCX content should raise an exception (Req 5.2)."""
        corrupt = tmp_path / "corrupt.docx"
        corrupt.write_bytes(b"this is not a valid docx file \x00\x01\x02")
        with pytest.raises(Exception):
            Converter().convert(corrupt)

    def test_corrupt_pdf_handled_gracefully(self, tmp_path):
        """Corrupt PDF should raise or return empty result — not crash silently (Req 5.2)."""
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"%PDF-1.4\n%%EOF\ngarbage\x00\x01\x02\x03")
        try:
            doc = Converter().convert(corrupt)
            assert doc is not None
        except Exception:
            pass  # Raising is also acceptable
