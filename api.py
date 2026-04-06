"""Converter — preferred OO interface for document2markdown.

Requirements: 8.1–8.3, 10.3
"""

from __future__ import annotations

from pathlib import Path

from document2markdown.config import RASTER_DPI
from document2markdown.dispatcher import resolve_converter
from document2markdown.document import Document
from document2markdown.postprocess import postprocess
from document2markdown.renderer_base import BaseRenderer


class Converter:
    """Convert a single source document to a :class:`~document2markdown.document.Document`.

    This is the preferred entry point for library users.  For batch and
    directory convenience, use :mod:`document2markdown.utils`.

    Parameters
    ----------
    output_dir:
        Default output directory passed to :meth:`Document.save`.  When
        *None*, :meth:`Document.save` writes alongside the source file.
    raster_dpi:
        DPI used when rasterizing vector graphics as a final fallback.
        Defaults to :data:`~document2markdown.config.RASTER_DPI` (300).
    verbose:
        When *True*, print per-file progress to stdout.
    renderer:
        Renderer used by :meth:`Document.to_markdown` and
        :meth:`Document.save`.  Defaults to
        :class:`~document2markdown.renderer_base.MarkdownRenderer`.
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        raster_dpi: int = RASTER_DPI,
        verbose: bool = False,
        renderer: BaseRenderer | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._raster_dpi = raster_dpi
        self._verbose = verbose
        self._renderer = renderer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, source_path: Path) -> Document:
        """Convert *source_path* and return a :class:`~document2markdown.document.Document`.

        Runs the full pipeline:
        dispatcher → per-format converter → post-processor.

        Parameters
        ----------
        source_path:
            Path to the source document.  Must exist on disk.

        Returns
        -------
        Document
            The conversion result wrapped in a :class:`~document2markdown.document.Document`.

        Raises
        ------
        UnsupportedFormatError
            When the file type cannot be determined.
        MimeExtensionMismatchError
            When the extension and magic-byte MIME types disagree.
        Any exception raised by the underlying converter.
        """
        source_path = Path(source_path)

        if self._verbose:
            print(f"Converting: {source_path}")

        # 1. Dispatch to the correct converter class
        converter_cls = resolve_converter(source_path)
        converter_instance = converter_cls()

        # 2. Run the per-format converter
        raw_result = converter_instance.convert(source_path)

        # 3. Post-process
        processed = postprocess(raw_result)

        # 4. Wrap in Document
        return Document(
            source_path=source_path,
            result=processed,
            renderer=self._renderer,
            output_dir=self._output_dir,
        )
