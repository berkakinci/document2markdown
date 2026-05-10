"""VectorConverter — converts EMF, WMF, or EPS bytes to SVG or PNG.

Conversion strategy by format:

  EMF / WMF
    1. Inkscape → SVG  via ``inkscape --export-type=svg``
    2. Inkscape → PNG  via ``inkscape --export-type=png --export-dpi=<dpi>``

  EPS
    1. Pillow (via Ghostscript) → PNG
       Inkscape 1.4+ on macOS cannot open EPS from the CLI; Ghostscript
       (``gs``) must be installed and Pillow uses it automatically.

Returns a ``(bytes, extension)`` tuple where *extension* is ``".svg"`` or
``".png"``.  If every method fails a warning is logged to stderr and a
:class:`VectorConversionError` is raised — no partial output is ever written.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from document2markdown.config import INKSCAPE_PATH, RASTER_DPI

logger = logging.getLogger(__name__)

# Supported source format hints
SourceFormat = Literal["emf", "wmf", "eps"]


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class VectorConversionError(Exception):
    """Raised when all conversion methods fail for a vector graphic."""


# ---------------------------------------------------------------------------
# Internal helpers — Inkscape (EMF / WMF)
# ---------------------------------------------------------------------------


def _inkscape_available() -> bool:
    return Path(INKSCAPE_PATH).is_file() or shutil.which(INKSCAPE_PATH) is not None


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
                    INKSCAPE_PATH,
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
                    INKSCAPE_PATH,
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
# Internal helpers — Pillow / Ghostscript (EPS)
# ---------------------------------------------------------------------------


def _ghostscript_available() -> bool:
    """Return True if ``gs`` is on PATH (required by Pillow for EPS)."""
    return shutil.which("gs") is not None


def _try_pillow_eps_png(data: bytes, dpi: int) -> bytes | None:
    """Rasterize EPS to PNG via Pillow (which shells out to Ghostscript).

    Returns PNG bytes, or None if Pillow or Ghostscript is unavailable or
    the conversion fails.
    """
    if not _ghostscript_available():
        logger.debug("Ghostscript (gs) not found — skipping Pillow EPS conversion")
        return None

    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        logger.debug("Pillow not installed — skipping EPS conversion")
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            in_file = Path(tmp) / "input.eps"
            in_file.write_bytes(data)

            img = Image.open(in_file)
            img.load()  # triggers gs subprocess

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    except Exception as exc:
        logger.debug("Pillow EPS→PNG conversion failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


class VectorConverter:
    """Convert raw vector graphic bytes to SVG (preferred) or PNG (fallback).

    - EMF / WMF: converted via Inkscape (must be installed).
    - EPS: rasterized to PNG via Pillow + Ghostscript (``gs`` must be on PATH).

    Parameters
    ----------
    raster_dpi:
        DPI used when rasterizing.  Defaults to
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
            If all conversion methods fail.  No partial output is written
            before raising.
        """
        fmt = source_format.lower()

        if fmt == "eps":
            # ------------------------------------------------------------------
            # EPS: Pillow + Ghostscript → PNG
            # Inkscape 1.4+ on macOS cannot open EPS from the CLI.
            # ------------------------------------------------------------------
            png_bytes = _try_pillow_eps_png(data, self.raster_dpi)
            if png_bytes is not None:
                return png_bytes, ".png"

        else:
            # ------------------------------------------------------------------
            # EMF / WMF: Inkscape → SVG (preferred), then PNG fallback
            # ------------------------------------------------------------------
            svg_bytes = _try_inkscape_svg(data, fmt)
            if svg_bytes is not None:
                return svg_bytes, ".svg"

            png_bytes = _try_inkscape_png(data, fmt, self.raster_dpi)
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
            "EMF/WMF require Inkscape on PATH; "
            "EPS requires Ghostscript (gs) and Pillow."
        )
