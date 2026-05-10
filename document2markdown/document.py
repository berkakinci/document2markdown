"""Document — wraps a source path and ConversionResult.

Provides a high-level interface for accessing conversion output and writing
results to disk.

Requirements: 8.1–8.3
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from document2markdown.config import OUTPUT_DIR_NAME
from document2markdown.document_model import ConversionResult
from document2markdown.renderer_base import BaseRenderer, MarkdownRenderer
from document2markdown.writer import OutputWriter

if TYPE_CHECKING:
    pass


class Document:
    """The result of converting a single source document.

    Returned by :class:`~document2markdown.api.Converter`.  Provides access
    to the raw :class:`~document2markdown.document_model.ConversionResult`,
    any non-fatal warnings, and convenience methods for rendering and saving.

    Parameters
    ----------
    source_path:
        Path to the original source document.
    result:
        The post-processed intermediate representation.
    renderer:
        The renderer to use for :meth:`to_markdown`.  Defaults to a fresh
        :class:`~document2markdown.renderer_base.MarkdownRenderer` if *None*.
    output_dir:
        Default output directory used by :meth:`save` when no *output*
        argument is supplied.  If *None*, :meth:`save` writes to
        ``{source_parent}/{OUTPUT_DIR_NAME}/``.
    force:
        When *True*, bypass skip-if-newer logic and always write output.
        Passed through to :meth:`OutputWriter.write`.
    """

    def __init__(
        self,
        source_path: Path,
        result: ConversionResult,
        renderer: BaseRenderer | None = None,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> None:
        self._source_path = source_path
        self._result = result
        self._renderer = renderer
        self._output_dir = output_dir
        self._force = force
        self._skipped: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def result(self) -> ConversionResult:
        """The raw :class:`~document2markdown.document_model.ConversionResult`."""
        return self._result

    @property
    def warnings(self) -> list[str]:
        """Non-fatal warnings collected during conversion."""
        return list(self._result.warnings)

    @property
    def skipped(self) -> bool:
        """True if skip-if-newer logic determined the output is up-to-date."""
        return self._skipped

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def to_markdown(self, renderer: BaseRenderer | None = None) -> str:
        """Render the document to a Markdown string (no disk I/O).

        Parameters
        ----------
        renderer:
            Override the renderer for this call.  Falls back to the renderer
            supplied at construction time, then to a default
            :class:`~document2markdown.renderer_base.MarkdownRenderer`.

        Returns
        -------
        str
            The rendered Markdown string.
        """
        effective_renderer = renderer or self._renderer
        if effective_renderer is None:
            effective_renderer = MarkdownRenderer(base_name=self._source_path.stem)
        elif isinstance(effective_renderer, MarkdownRenderer) and effective_renderer._base_name is None:
            effective_renderer._base_name = self._source_path.stem  # noqa: SLF001
        return effective_renderer.render(self._result)

    def save(self, output: Path | None = None) -> Path:
        """Write the ``.md`` file and ``md_embedded/`` assets to disk.

        Parameters
        ----------
        output:
            Destination directory (or file path).  When *None*, falls back to
            the *output_dir* supplied at construction time; if that is also
            *None*, the file is written to
            ``{source_parent}/{OUTPUT_DIR_NAME}/``.

        Returns
        -------
        Path
            Absolute path to the written ``.md`` file.
        """
        out_dir = output or self._output_dir
        if out_dir is None:
            out_dir = self._source_path.parent / OUTPUT_DIR_NAME
        writer = OutputWriter(renderer=self._renderer)
        md_path, skipped = writer.write(
            self._result, self._source_path, out_dir, force=self._force
        )
        self._skipped = skipped
        return md_path
