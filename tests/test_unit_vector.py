"""Unit tests for VectorConverter — Req 2.8 / Property 9."""
from __future__ import annotations

import subprocess

import pytest

from document2markdown.converter_vector import VectorConverter, VectorConversionError


class TestVectorConverter:
    def test_raises_on_garbage_input(self):
        """Garbage bytes with no Inkscape should raise VectorConversionError."""
        vc = VectorConverter()
        with pytest.raises(VectorConversionError):
            vc.convert(b"\x00\x01\x02\x03garbage", "emf")


# ---------------------------------------------------------------------------
# _try_inkscape_svg
# ---------------------------------------------------------------------------

class TestTryInkscapeSvg:
    def test_returns_none_when_inkscape_not_available(self):
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_inkscape_svg
        with patch("document2markdown.converter_vector._find_inkscape", return_value=None):
            assert _try_inkscape_svg(b"data", "emf") is None

    def test_returns_none_on_nonzero_returncode(self):
        from unittest.mock import patch, MagicMock
        from document2markdown.converter_vector import _try_inkscape_svg
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"error"
        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", return_value=mock_result):
                assert _try_inkscape_svg(b"data", "emf") is None

    def test_returns_none_on_timeout(self):
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_inkscape_svg
        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("inkscape", 60)):
                assert _try_inkscape_svg(b"data", "emf") is None

    def test_returns_svg_bytes_on_success(self):
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from document2markdown.converter_vector import _try_inkscape_svg
        fake_svg = b"<svg/>"
        mock_result = MagicMock()
        mock_result.returncode = 0

        def fake_run(cmd, **kwargs):
            for arg in cmd:
                if arg.startswith("--export-filename="):
                    Path(arg.split("=", 1)[1]).write_bytes(fake_svg)
            return mock_result

        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", side_effect=fake_run):
                result = _try_inkscape_svg(b"data", "emf")
        assert result == fake_svg


# ---------------------------------------------------------------------------
# _try_inkscape_png
# ---------------------------------------------------------------------------

class TestTryInkscapePng:
    def test_returns_none_when_inkscape_not_available(self):
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_inkscape_png
        with patch("document2markdown.converter_vector._find_inkscape", return_value=None):
            assert _try_inkscape_png(b"data", "emf", 150) is None

    def test_returns_none_on_oserror(self):
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_inkscape_png
        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", side_effect=OSError("no inkscape")):
                assert _try_inkscape_png(b"data", "emf", 150) is None

    def test_returns_none_on_nonzero_returncode(self):
        from unittest.mock import patch, MagicMock
        from document2markdown.converter_vector import _try_inkscape_png
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"error"
        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", return_value=mock_result):
                assert _try_inkscape_png(b"data", "emf", 150) is None

    def test_returns_none_on_timeout(self):
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_inkscape_png
        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("inkscape", 60)):
                assert _try_inkscape_png(b"data", "emf", 150) is None

    def test_returns_png_bytes_on_success(self):
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from document2markdown.converter_vector import _try_inkscape_png
        fake_png = b"\x89PNG\r\n\x1a\n"
        mock_result = MagicMock()
        mock_result.returncode = 0

        def fake_run(cmd, **kwargs):
            for arg in cmd:
                if arg.startswith("--export-filename="):
                    Path(arg.split("=", 1)[1]).write_bytes(fake_png)
            return mock_result

        with patch("document2markdown.converter_vector._find_inkscape", return_value="/usr/bin/inkscape"):
            with patch("subprocess.run", side_effect=fake_run):
                result = _try_inkscape_png(b"data", "emf", 150)
        assert result == fake_png


# ---------------------------------------------------------------------------
# VectorConverter fallback chain
# ---------------------------------------------------------------------------

class TestVectorConverterFallbackChain:
    def test_all_methods_fail_raises(self):
        from unittest.mock import patch
        vc = VectorConverter()
        with patch("document2markdown.converter_vector._try_inkscape_svg", return_value=None), \
             patch("document2markdown.converter_vector._try_inkscape_png", return_value=None):
            with pytest.raises(VectorConversionError):
                vc.convert(b"data", "emf")

    def test_inkscape_svg_success(self):
        from unittest.mock import patch
        vc = VectorConverter()
        fake_svg = b"<svg/>"
        with patch("document2markdown.converter_vector._try_inkscape_svg", return_value=fake_svg):
            data, ext = vc.convert(b"data", "emf")
        assert ext == ".svg"
        assert data == fake_svg

    def test_inkscape_png_fallback(self):
        from unittest.mock import patch
        vc = VectorConverter()
        fake_png = b"\x89PNG"
        with patch("document2markdown.converter_vector._try_inkscape_svg", return_value=None), \
             patch("document2markdown.converter_vector._try_inkscape_png", return_value=fake_png):
            data, ext = vc.convert(b"data", "emf")
        assert ext == ".png"
        assert data == fake_png


# ---------------------------------------------------------------------------
# _try_pillow_eps_png
# ---------------------------------------------------------------------------

class TestTryPillowEpsPng:
    def test_returns_none_when_ghostscript_not_available(self):
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_pillow_eps_png
        with patch("document2markdown.converter_vector._ghostscript_available", return_value=False):
            assert _try_pillow_eps_png(b"data", 300) is None

    def test_returns_none_when_pillow_not_installed(self):
        import sys
        from unittest.mock import patch
        from document2markdown.converter_vector import _try_pillow_eps_png

        # Remove PIL from sys.modules so the lazy import inside the function
        # triggers a fresh ImportError via our fake finder.
        with patch("document2markdown.converter_vector._ghostscript_available", return_value=True):
            with patch.dict(sys.modules, {"PIL": None, "PIL.Image": None}):
                assert _try_pillow_eps_png(b"data", 300) is None

    def test_returns_none_on_pillow_exception(self):
        import sys
        from unittest.mock import patch, MagicMock
        from document2markdown.converter_vector import _try_pillow_eps_png

        # PIL.Image.open raises — function should catch and return None
        mock_image = MagicMock()
        mock_image.open.side_effect = Exception("gs failed")

        with patch("document2markdown.converter_vector._ghostscript_available", return_value=True):
            with patch.dict(sys.modules, {"PIL": MagicMock(Image=mock_image), "PIL.Image": mock_image}):
                assert _try_pillow_eps_png(b"data", 300) is None

    def test_returns_png_bytes_on_success(self):
        import sys
        from unittest.mock import patch, MagicMock
        from document2markdown.converter_vector import _try_pillow_eps_png

        fake_png = b"\x89PNG\r\n\x1a\nfakedata"

        mock_img = MagicMock()
        def fake_save(buf, format=None):
            buf.write(fake_png)
        mock_img.save.side_effect = fake_save
        mock_img.load.return_value = None

        mock_image = MagicMock()
        mock_image.open.return_value = mock_img

        with patch("document2markdown.converter_vector._ghostscript_available", return_value=True):
            with patch.dict(sys.modules, {"PIL": MagicMock(Image=mock_image), "PIL.Image": mock_image}):
                result = _try_pillow_eps_png(b"eps data", 300)

        assert result == fake_png


# ---------------------------------------------------------------------------
# VectorConverter EPS routing
# ---------------------------------------------------------------------------

class TestVectorConverterEPSRouting:
    def test_eps_uses_pillow_not_inkscape(self):
        """EPS must go through _try_pillow_eps_png, never Inkscape."""
        from unittest.mock import patch, MagicMock
        vc = VectorConverter()
        fake_png = b"\x89PNG\r\n\x1a\n"

        with patch("document2markdown.converter_vector._try_pillow_eps_png", return_value=fake_png) as mock_pillow, \
             patch("document2markdown.converter_vector._try_inkscape_svg") as mock_svg, \
             patch("document2markdown.converter_vector._try_inkscape_png") as mock_png:
            data, ext = vc.convert(b"eps data", "eps")

        assert ext == ".png"
        assert data == fake_png
        mock_pillow.assert_called_once()
        mock_svg.assert_not_called()
        mock_png.assert_not_called()

    def test_eps_raises_when_pillow_fails(self):
        """If Pillow/gs fails for EPS, VectorConversionError must be raised."""
        from unittest.mock import patch
        vc = VectorConverter()
        with patch("document2markdown.converter_vector._try_pillow_eps_png", return_value=None):
            with pytest.raises(VectorConversionError):
                vc.convert(b"eps data", "eps")

    def test_emf_does_not_use_pillow(self):
        """EMF must go through Inkscape, never Pillow."""
        from unittest.mock import patch
        vc = VectorConverter()
        fake_svg = b"<svg/>"

        with patch("document2markdown.converter_vector._try_inkscape_svg", return_value=fake_svg) as mock_svg, \
             patch("document2markdown.converter_vector._try_pillow_eps_png") as mock_pillow:
            data, ext = vc.convert(b"emf data", "emf")

        assert ext == ".svg"
        mock_pillow.assert_not_called()

    def test_wmf_does_not_use_pillow(self):
        """WMF must go through Inkscape, never Pillow."""
        from unittest.mock import patch
        vc = VectorConverter()
        fake_svg = b"<svg/>"

        with patch("document2markdown.converter_vector._try_inkscape_svg", return_value=fake_svg) as mock_svg, \
             patch("document2markdown.converter_vector._try_pillow_eps_png") as mock_pillow:
            data, ext = vc.convert(b"wmf data", "wmf")

        assert ext == ".svg"
        mock_pillow.assert_not_called()
