"""Property-based tests for VectorConverter.

# Feature: document-to-markdown, Property 9: Vector graphics are extracted as SVG
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import patch, MagicMock
from pathlib import Path

from document2markdown.converter_vector import VectorConverter, VectorConversionError

# ---------------------------------------------------------------------------
# SVG generation strategy
# ---------------------------------------------------------------------------

_svg_width = st.integers(min_value=1, max_value=1000)
_svg_height = st.integers(min_value=1, max_value=1000)
_rect_count = st.integers(min_value=0, max_value=5)


def _build_svg(width: int, height: int, rects: int) -> bytes:
    rects_xml = "".join(
        f'<rect x="{i * 2}" y="{i * 2}" '
        f'width="{max(1, width // (rects + 1))}" '
        f'height="{max(1, height // (rects + 1))}" fill="blue"/>'
        for i in range(rects)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}">'
        f"{rects_xml}"
        f"</svg>"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Property 9: Vector graphics are extracted as SVG
#
# Since Inkscape may not be installed in all environments, we mock the
# subprocess layer so the property exercises the full VectorConverter
# logic (format lowercasing, fallback chain, return type contract) without
# requiring a system dependency.
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 9: Vector graphics are extracted as SVG
@given(width=_svg_width, height=_svg_height, rects=_rect_count)
@settings(max_examples=100)
def test_property9_vector_converter_returns_svg(
    width: int, height: int, rects: int
) -> None:
    """VectorConverter returns (.svg, bytes) where bytes is valid XML with an SVG root.

    The Inkscape subprocess is mocked to echo the input back as SVG, isolating
    the property from system dependencies while still exercising the full
    converter logic.
    """
    data = _build_svg(width, height, rects)
    vc = VectorConverter()

    mock_result = MagicMock()
    mock_result.returncode = 0

    def fake_inkscape(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("--export-filename=") and arg.endswith(".svg"):
                Path(arg.split("=", 1)[1]).write_bytes(data)
        return mock_result

    with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"), \
         patch("subprocess.run", side_effect=fake_inkscape):
        output_bytes, ext = vc.convert(data, "emf")

    assert ext == ".svg", f"Expected .svg, got {ext!r}"
    assert len(output_bytes) > 0

    try:
        root = ET.fromstring(output_bytes.decode("utf-8", errors="replace"))
    except ET.ParseError as exc:
        pytest.fail(f"Output is not valid XML: {exc}")

    assert "svg" in root.tag.lower(), f"Root tag is not SVG: {root.tag!r}"


# ---------------------------------------------------------------------------
# Property 9b: EPS vector graphics are extracted as PNG via Pillow+Ghostscript
#
# The Pillow/Ghostscript path is mocked so the property exercises the full
# VectorConverter EPS routing logic without requiring gs on PATH.
# ---------------------------------------------------------------------------

_eps_body = st.binary(min_size=0, max_size=200)
_dpi = st.integers(min_value=72, max_value=600)

# Minimal valid PNG: 8-byte signature + IHDR + IEND
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _fake_png_bytes(width: int = 1, height: int = 1) -> bytes:
    """Return a minimal PNG-like byte sequence (signature + filler)."""
    return _PNG_SIG + b"\x00" * 16


# Feature: document-to-markdown, Property 9b: EPS vector graphics are extracted as PNG
@given(body=_eps_body, dpi=_dpi)
@settings(max_examples=100)
def test_property9b_eps_converter_returns_png(body: bytes, dpi: int) -> None:
    """VectorConverter returns (.png, bytes) for EPS input when Pillow succeeds.

    The Pillow Image.open path is mocked to return fake PNG bytes, isolating
    the property from Ghostscript while exercising the EPS routing, format
    detection, and return-type contract.
    """
    fake_png = _fake_png_bytes()
    vc = VectorConverter(raster_dpi=dpi)

    mock_img = MagicMock()
    mock_img.load.return_value = None

    def fake_save(buf, format=None):
        buf.write(fake_png)

    mock_img.save.side_effect = fake_save

    mock_image_mod = MagicMock()
    mock_image_mod.open.return_value = mock_img

    import sys
    with patch("document2markdown.converter_vector._ghostscript_available", return_value=True), \
         patch.dict(sys.modules, {"PIL": MagicMock(Image=mock_image_mod), "PIL.Image": mock_image_mod}):
        output_bytes, ext = vc.convert(body, "eps")

    assert ext == ".png", f"Expected .png, got {ext!r}"
    assert output_bytes.startswith(_PNG_SIG), "Output does not start with PNG signature"
    assert len(output_bytes) > len(_PNG_SIG), "Output is just the PNG signature with no data"


# Feature: document-to-markdown, Property 9b: EPS raises VectorConversionError when Pillow fails
@given(body=_eps_body)
@settings(max_examples=100)
def test_property9b_eps_converter_raises_on_failure(body: bytes) -> None:
    """VectorConverter raises VectorConversionError for EPS when Pillow is unavailable."""
    vc = VectorConverter()

    with patch("document2markdown.converter_vector._try_pillow_eps_png", return_value=None):
        with pytest.raises(VectorConversionError):
            vc.convert(body, "eps")
