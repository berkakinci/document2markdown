"""VectorConverter — converts EMF, WMF, or EPS bytes to SVG (or PNG fallback).

Conversion is attempted in order:
  1. cairosvg  — preferred; pure-Python, returns SVG bytes directly.
  2. Inkscape  — shell fallback via ``inkscape --export-type=svg``.
  3. Rasterize — final fallback; renders to PNG at RASTER_DPI using Inkscape
                 (``--export-type=png --export-dpi=<dpi>``) or cairosvg.

Returns a ``(bytes, extension)`` tuple where *extension* is ``".svg"`` or
``".png"``.  If every method fails a warning is logged to stderr and a
:class:`VectorConversionError` is raised — no partial SVG is ever written.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from document2markdown.config import RASTER_DPI

logger = logging.getLogger(__name__)

# Supported source format hints
SourceFormat = Literal["emf", "wmf", "eps"]

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class VectorConversionError(Exception):
    """Raised when all conversion methods fail for a vector graphic."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_cairosvg(data: bytes, src_fmt: str) -> bytes | None:
    """Attempt SVG conversion via cairosvg.  Returns SVG bytes or None."""
    try:
        import cairosvg  # type: ignore[import]
    except ImportError:
        return None

    try:
        # cairosvg exposes format-specific entry points.
        converter_fn = {
            "eps": getattr(cairosvg, "eps2svg", None),
            "svg": getattr(cairosvg, "svg2svg", None),
        }.get(src_fmt)

        if converter_fn is None:
            # cairosvg does not natively handle EMF/WMF; skip.
            return None

        svg_bytes: bytes = converter_fn(bytestring=data)
        return svg_bytes
    except Exception as exc:  # noqa: BLE001
        logger.debug("cairosvg conversion failed: %s", exc)
        return None


def _try_cairosvg_raster(data: bytes, src_fmt: str, dpi: int) -> bytes | None:
    """Attempt PNG rasterization via cairosvg.  Returns PNG bytes or None."""
    try:
        import cairosvg  # type: ignore[import]
    except ImportError:
        return None

    try:
        raster_fn = {
            "eps": getattr(cairosvg, "eps2png", None),
            "svg": getattr(cairosvg, "svg2png", None),
        }.get(src_fmt)

        if raster_fn is None:
            return None

        png_bytes: bytes = raster_fn(bytestring=data, dpi=dpi)
        return png_bytes
    except Exception as exc:  # noqa: BLE001
        logger.debug("cairosvg raster conversion failed: %s", exc)
        return None


def _inkscape_available() -> bool:
    return shutil.which("inkscape") is not None


def _try_inkscape_svg(data: bytes, src_fmt: str) -> bytes | None:
    """Attempt SVG conversion via Inkscape shell call.  Returns SVG bytes or None."""
    if not _inkscape_available():
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        in_file = tmp_path / f"input.{src_fmt}"
        out_file = tmp_path / "output.svg"
        in_file.write_bytes(data)

        try:
            result = subprocess.run(
                [
                    "inkscape",
                    str(in_file),
                    "--export-type=svg",
                    f"--export-filename={out_file}",
                ],
                capture_output=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("Inkscape SVG conversion failed: %s", exc)
            return None

        if result.returncode != 0 or not out_file.exists():
            logger.debug(
                "Inkscape SVG conversion failed (rc=%d): %s",
                result.returncode,
                result.stderr.decode(errors="replace"),
            )
            return None

        return out_file.read_bytes()


def _try_inkscape_png(data: bytes, src_fmt: str, dpi: int) -> bytes | None:
    """Attempt PNG rasterization via Inkscape shell call.  Returns PNG bytes or None."""
    if not _inkscape_available():
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        in_file = tmp_path / f"input.{src_fmt}"
        out_file = tmp_path / "output.png"
        in_file.write_bytes(data)

        try:
            result = subprocess.run(
                [
                    "inkscape",
                    str(in_file),
                    "--export-type=png",
                    f"--export-dpi={dpi}",
                    f"--export-filename={out_file}",
                ],
                capture_output=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("Inkscape PNG rasterization failed: %s", exc)
            return None

        if result.returncode != 0 or not out_file.exists():
            logger.debug(
                "Inkscape PNG rasterization failed (rc=%d): %s",
                result.returncode,
                result.stderr.decode(errors="replace"),
            )
            return None

        return out_file.read_bytes()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


class VectorConverter:
    """Convert raw vector graphic bytes to SVG (preferred) or PNG (fallback).

    Parameters
    ----------
    raster_dpi:
        DPI used when rasterizing as a last resort.  Defaults to
        :data:`~document2markdown.config.RASTER_DPI`.
    """

    def __init__(self, raster_dpi: int = RASTER_DPI) -> None:
        self.raster_dpi = raster_dpi

    def convert(self, data: bytes, source_format: SourceFormat) -> tuple[bytes, str]:
        """Convert *data* to SVG or PNG.

        Parameters
        ----------
        data:
            Raw bytes of the source vector graphic.
        source_format:
            One of ``"emf"``, ``"wmf"``, or ``"eps"``.

        Returns
        -------
        tuple[bytes, str]
            ``(output_bytes, extension)`` where *extension* is ``".svg"`` or
            ``".png"``.

        Raises
        ------
        VectorConversionError
            If all three conversion methods fail.  No partial output is
            written before raising.
        """
        fmt = source_format.lower()

        # ------------------------------------------------------------------
        # Step 1: cairosvg → SVG
        # ------------------------------------------------------------------
        svg_bytes = _try_cairosvg(data, fmt)
        if svg_bytes is not None:
            return svg_bytes, ".svg"

        # ------------------------------------------------------------------
        # Step 2: Inkscape → SVG
        # ------------------------------------------------------------------
        svg_bytes = _try_inkscape_svg(data, fmt)
        if svg_bytes is not None:
            return svg_bytes, ".svg"

        # ------------------------------------------------------------------
        # Step 3a: Inkscape → PNG  (rasterization)
        # ------------------------------------------------------------------
        png_bytes = _try_inkscape_png(data, fmt, self.raster_dpi)
        if png_bytes is not None:
            return png_bytes, ".png"

        # ------------------------------------------------------------------
        # Step 3b: cairosvg → PNG  (rasterization, if Inkscape unavailable)
        # ------------------------------------------------------------------
        png_bytes = _try_cairosvg_raster(data, fmt, self.raster_dpi)
        if png_bytes is not None:
            return png_bytes, ".png"

        # ------------------------------------------------------------------
        # All methods failed
        # ------------------------------------------------------------------
        msg = (
            f"WARNING: VectorConverter: all conversion methods failed for "
            f"source format '{source_format}'"
        )
        print(msg, file=sys.stderr)
        logger.warning(
            "VectorConverter: all conversion methods failed for source format '%s'",
            source_format,
        )
        raise VectorConversionError(
            f"Could not convert vector graphic (format='{source_format}'): "
            "cairosvg, Inkscape SVG, Inkscape PNG, and cairosvg raster all failed."
        )
