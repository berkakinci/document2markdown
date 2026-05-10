"""Live integration tests for VectorConverter using real binaries.

- EMF / WMF: tested via the real Inkscape binary.
- EPS: tested via Pillow + Ghostscript (gs).

All tests are skipped automatically when the required binary is absent.

Fixture discovery is automatic: drop any .emf, .wmf, or .eps file into
``test_fixtures/`` and it will be picked up by the parametrized tests
without any code changes.
"""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from document2markdown.converter_vector import (
    VectorConverter,
    VectorConversionError,
    _inkscape_available,
    _ghostscript_available,
)


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent.parent / "test_fixtures"

def _discover(ext: str) -> list[Path]:
    """Return all files with the given extension in test_fixtures/."""
    if not _FIXTURES_DIR.is_dir():
        return []
    return sorted(_FIXTURES_DIR.glob(f"*.{ext}"))


_emf_files = _discover("emf")
_wmf_files = _discover("wmf")
_eps_files = _discover("eps")


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
# Minimal programmatic fixtures (fallback when no files on disk)
# ---------------------------------------------------------------------------

def _make_emf() -> bytes:
    """Minimal valid EMF containing a single rectangle."""
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
# EMF tests (Inkscape) — parametrized over all .emf fixtures
# ---------------------------------------------------------------------------

@inkscape_required
class TestLiveVectorEMF:
    @pytest.mark.parametrize(
        "emf_path",
        _emf_files if _emf_files else [None],
        ids=[f.name for f in _emf_files] if _emf_files else ["minimal"],
    )
    def test_emf_converts_to_svg(self, emf_path: Path | None):
        data = emf_path.read_bytes() if emf_path else _make_emf()
        vc = VectorConverter()
        output, ext = vc.convert(data, "emf")
        assert ext == ".svg"
        assert len(output) > 0
        assert b"<svg" in output

    @pytest.mark.parametrize(
        "emf_path",
        _emf_files if _emf_files else [None],
        ids=[f.name for f in _emf_files] if _emf_files else ["minimal"],
    )
    def test_emf_svg_is_valid_xml(self, emf_path: Path | None):
        data = emf_path.read_bytes() if emf_path else _make_emf()
        vc = VectorConverter()
        output, ext = vc.convert(data, "emf")
        assert ext == ".svg"
        ET.fromstring(output)  # must not raise

    @pytest.mark.parametrize(
        "emf_path",
        _emf_files if _emf_files else [None],
        ids=[f.name for f in _emf_files] if _emf_files else ["minimal"],
    )
    def test_emf_svg_has_child_elements(self, emf_path: Path | None):
        data = emf_path.read_bytes() if emf_path else _make_emf()
        vc = VectorConverter()
        output, _ = vc.convert(data, "emf")
        root = ET.fromstring(output)
        assert len(list(root.iter())) > 1


# ---------------------------------------------------------------------------
# WMF tests (Inkscape) — parametrized over all .wmf fixtures
# ---------------------------------------------------------------------------

@inkscape_required
class TestLiveVectorWMF:
    @pytest.mark.skipif(not _wmf_files, reason="No .wmf fixtures in test_fixtures/")
    @pytest.mark.parametrize(
        "wmf_path",
        _wmf_files,
        ids=[f.name for f in _wmf_files],
    )
    def test_wmf_converts_to_svg(self, wmf_path: Path):
        vc = VectorConverter()
        output, ext = vc.convert(wmf_path.read_bytes(), "wmf")
        assert ext == ".svg"
        assert len(output) > 0
        assert b"<svg" in output

    @pytest.mark.skipif(not _wmf_files, reason="No .wmf fixtures in test_fixtures/")
    @pytest.mark.parametrize(
        "wmf_path",
        _wmf_files,
        ids=[f.name for f in _wmf_files],
    )
    def test_wmf_svg_is_valid_xml(self, wmf_path: Path):
        vc = VectorConverter()
        output, ext = vc.convert(wmf_path.read_bytes(), "wmf")
        assert ext == ".svg"
        ET.fromstring(output)  # must not raise


# ---------------------------------------------------------------------------
# EPS tests (Pillow + Ghostscript) — parametrized over all .eps fixtures
# ---------------------------------------------------------------------------

@ghostscript_required
class TestLiveVectorEPS:
    @pytest.mark.parametrize(
        "eps_path",
        _eps_files if _eps_files else [None],
        ids=[f.name for f in _eps_files] if _eps_files else ["minimal"],
    )
    def test_eps_converts_to_png(self, eps_path: Path | None):
        data = eps_path.read_bytes() if eps_path else _make_eps()
        vc = VectorConverter()
        output, ext = vc.convert(data, "eps")
        assert ext == ".png"
        assert len(output) > 0

    @pytest.mark.parametrize(
        "eps_path",
        _eps_files if _eps_files else [None],
        ids=[f.name for f in _eps_files] if _eps_files else ["minimal"],
    )
    def test_eps_png_has_valid_header(self, eps_path: Path | None):
        data = eps_path.read_bytes() if eps_path else _make_eps()
        vc = VectorConverter()
        output, ext = vc.convert(data, "eps")
        assert ext == ".png"
        assert output[:8] == b"\x89PNG\r\n\x1a\n"


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
