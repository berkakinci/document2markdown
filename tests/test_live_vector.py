"""Live integration tests for VectorConverter using real binaries.

- EMF / WMF: tested via the real Inkscape binary.
- EPS: tested via Pillow + Ghostscript (gs).

All tests are skipped automatically when the required binary is absent.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from document2markdown.converter_vector import (
    VectorConverter,
    VectorConversionError,
    _inkscape_available,
    _ghostscript_available,
)


# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

inkscape_required = pytest.mark.skipif(
    not _inkscape_available(),
    reason="Inkscape binary not found — skipping live EMF/WMF tests",
)

ghostscript_required = pytest.mark.skipif(
    not _ghostscript_available(),
    reason="Ghostscript (gs) not found — skipping live EPS tests",
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_emf() -> bytes:
    """Minimal valid EMF containing a single rectangle."""
    import struct

    def emf_header() -> bytes:
        bounds = struct.pack("<iiii", 0, 0, 100, 100)
        frame  = struct.pack("<iiii", 0, 0, 2540, 2540)
        sig    = struct.pack("<I", 0x464D4520)
        ver    = struct.pack("<I", 0x00010000)
        nBytes   = struct.pack("<I", 0)
        nRecords = struct.pack("<I", 0)
        nHandles = struct.pack("<H", 0)
        reserved = struct.pack("<H", 0)
        nDesc    = struct.pack("<I", 0)
        offDesc  = struct.pack("<I", 0)
        nPalEntries    = struct.pack("<I", 0)
        szlDevice      = struct.pack("<ii", 1024, 768)
        szlMillimeters = struct.pack("<ii", 270, 203)
        return (
            struct.pack("<II", 1, 88)
            + bounds + frame + sig + ver
            + nBytes + nRecords + nHandles + reserved
            + nDesc + offDesc + nPalEntries
            + szlDevice + szlMillimeters
        )

    header  = emf_header()
    rect    = struct.pack("<II iiii", 27, 24, 10, 10, 90, 90)
    eof_rec = struct.pack("<II III", 14, 20, 0, 20, 20)
    total   = len(header) + len(rect) + len(eof_rec)
    header  = header[:52] + struct.pack("<I", total) + struct.pack("<I", 3) + header[60:]
    return header + rect + eof_rec


def _real_emf() -> bytes:
    """Return the real-world art-nouveau EMF fixture if present, else minimal."""
    f = Path(__file__).parent.parent / "test_fixtures" / "art-nouveau-P3.emf"
    return f.read_bytes() if f.exists() else _make_emf()


def _real_wmf() -> bytes:
    """Return the real-world art-nouveau WMF fixture (required — no valid minimal fallback)."""
    f = Path(__file__).parent.parent / "test_fixtures" / "art-nouveau-P3.wmf"
    if not f.exists():
        pytest.skip("art-nouveau-P3.wmf fixture not found")
    return f.read_bytes()


def _make_eps() -> bytes:
    """Minimal valid EPS containing a filled rectangle."""
    return (
        b"%!PS-Adobe-3.0 EPSF-3.0\n"
        b"%%BoundingBox: 0 0 100 100\n"
        b"%%EndComments\n"
        b"newpath 10 10 moveto 90 0 rlineto 0 80 rlineto -90 0 rlineto closepath\n"
        b"0.5 setgray fill\n"
        b"%%EOF\n"
    )


# ---------------------------------------------------------------------------
# EMF tests (Inkscape)
# ---------------------------------------------------------------------------

class TestLiveVectorEMF:
    @inkscape_required
    def test_emf_converts_to_svg(self):
        vc = VectorConverter()
        data, ext = vc.convert(_real_emf(), "emf")
        assert ext == ".svg"
        assert len(data) > 0
        assert b"<svg" in data

    @inkscape_required
    def test_emf_svg_is_valid_xml(self):
        import xml.etree.ElementTree as ET
        vc = VectorConverter()
        data, ext = vc.convert(_real_emf(), "emf")
        assert ext == ".svg"
        ET.fromstring(data)  # must not raise

    @inkscape_required
    def test_emf_svg_has_child_elements(self):
        import xml.etree.ElementTree as ET
        vc = VectorConverter()
        data, _ = vc.convert(_real_emf(), "emf")
        root = ET.fromstring(data)
        assert len(list(root.iter())) > 1


# ---------------------------------------------------------------------------
# WMF tests (Inkscape)
# ---------------------------------------------------------------------------

class TestLiveVectorWMF:
    @inkscape_required
    def test_wmf_converts_to_svg(self):
        vc = VectorConverter()
        data, ext = vc.convert(_real_wmf(), "wmf")
        assert ext == ".svg"
        assert len(data) > 0
        assert b"<svg" in data

    @inkscape_required
    def test_wmf_svg_is_valid_xml(self):
        import xml.etree.ElementTree as ET
        vc = VectorConverter()
        data, ext = vc.convert(_real_wmf(), "wmf")
        assert ext == ".svg"
        ET.fromstring(data)  # must not raise


# ---------------------------------------------------------------------------
# EPS tests (Pillow + Ghostscript)
# ---------------------------------------------------------------------------

class TestLiveVectorEPS:
    @ghostscript_required
    def test_eps_converts_to_png(self):
        vc = VectorConverter()
        data, ext = vc.convert(_make_eps(), "eps")
        assert ext == ".png"
        assert len(data) > 0

    @ghostscript_required
    def test_eps_png_has_valid_header(self):
        vc = VectorConverter()
        data, ext = vc.convert(_make_eps(), "eps")
        assert ext == ".png"
        assert data[:8] == b"\x89PNG\r\n\x1a\n"

    @ghostscript_required
    def test_eps_real_fixture(self):
        """Real-world EPS fixture from Inkscape examples."""
        f = Path(__file__).parent.parent / "test_fixtures" / "art-nouveau-P3.eps"
        if not f.exists():
            pytest.skip("art-nouveau-P3.eps fixture not found")
        vc = VectorConverter()
        data, ext = vc.convert(f.read_bytes(), "eps")
        assert ext == ".png"
        assert len(data) > 0


# ---------------------------------------------------------------------------
# Garbage input (with Inkscape present)
# ---------------------------------------------------------------------------

class TestLiveVectorGarbageInput:
    @inkscape_required
    def test_garbage_emf_raises(self):
        """Garbage bytes must raise VectorConversionError even with Inkscape present."""
        vc = VectorConverter()
        with pytest.raises(VectorConversionError):
            vc.convert(b"\x00\x01\x02\x03not_a_vector_file", "emf")
