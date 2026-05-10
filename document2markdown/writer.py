"""Output writer — serialises a ConversionResult to disk.

Responsibilities:
- Accepts a BaseRenderer instance; calls renderer.render(result) for the output string.
- Writes the output string to ``{output_dir}/{base_name}.md``.
- Writes embedded assets to ``md_embedded/{base_name}_{serial:04d}{ext}``.
- Generates URL-encoded relative paths for all image/link references (via the renderer).
- Overwrites existing output files with a stderr warning.
- Creates output directories as needed.

Requirements: 3.1–3.8, 2.6, 2.7
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote as url_quote

from document2markdown.config import EMBEDDED_DIR
from document2markdown.document_model import ConversionResult
from document2markdown.renderer_base import BaseRenderer, MarkdownRenderer


class OutputWriter:
    """Write a rendered document and its embedded assets to disk.

    Parameters
    ----------
    renderer:
        The renderer used to convert a ``ConversionResult`` to a string.
        Defaults to ``MarkdownRenderer`` if not provided.
    """

    def __init__(self, renderer: BaseRenderer | None = None) -> None:
        self._renderer = renderer  # may be None; resolved per write() call

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(
        self,
        result: ConversionResult,
        source_path: Path,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> tuple[Path, bool]:
        """Write *result* to disk and return the path and skip status.

        Parameters
        ----------
        result:
            The ``ConversionResult`` to serialise.
        source_path:
            Path to the original source document.  Used to derive the base
            name for the output file and embedded assets.
        output_dir:
            Directory where the ``.md`` file (and ``md_embedded/`` sub-dir)
            will be written.  Defaults to the same directory as *source_path*.
        force:
            When *True*, bypass skip-if-newer logic and always write.

        Returns
        -------
        tuple[Path, bool]
            ``(md_path, skipped)`` — the path to the ``.md`` file and whether
            the write was skipped because the target is already up-to-date.
        """
        base_name = source_path.stem  # e.g. "Report Q1"
        if output_dir is None:
            output_dir = source_path.parent

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        md_path = output_dir / f"{base_name}.md"

        # Skip-if-newer check (only when not forcing)
        if not force and md_path.exists():
            target_mtime = md_path.stat().st_mtime
            source_mtime = source_path.stat().st_mtime
            if target_mtime > source_mtime:
                # Target is newer than source — skip
                print(
                    f"INFO: {md_path}: up-to-date, skipping",
                    file=sys.stderr,
                )
                return (md_path, True)

        # Write embedded assets first so the renderer can reference them
        self._write_assets(result, base_name, output_dir)

        # Resolve renderer — use a MarkdownRenderer with the correct base_name
        renderer = self._resolve_renderer(base_name)

        # Render to string
        markdown = renderer.render(result)

        # Write .md file
        if md_path.exists():
            print(
                f"WARNING: {md_path}: output file already exists; overwriting",
                file=sys.stderr,
            )
        md_path.write_text(markdown, encoding="utf-8")

        return (md_path, False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_renderer(self, base_name: str) -> BaseRenderer:
        """Return the renderer to use, injecting *base_name* when possible."""
        if self._renderer is not None:
            # If the caller supplied a MarkdownRenderer, update its base_name
            if isinstance(self._renderer, MarkdownRenderer):
                self._renderer._base_name = base_name  # noqa: SLF001
            return self._renderer
        # Default: fresh MarkdownRenderer with the correct base_name
        return MarkdownRenderer(base_name=base_name)

    def _write_assets(
        self,
        result: ConversionResult,
        base_name: str,
        output_dir: Path,
    ) -> None:
        """Write all embedded assets to ``md_embedded/`` under *output_dir*."""
        if not result.embedded:
            return

        embedded_dir = output_dir / EMBEDDED_DIR
        embedded_dir.mkdir(parents=True, exist_ok=True)

        for serial, asset in enumerate(result.embedded, start=1):
            filename = f"{base_name}_{serial:04d}{asset.extension}"
            asset_path = embedded_dir / filename
            if asset_path.exists():
                print(
                    f"WARNING: {asset_path}: embedded asset already exists; overwriting",
                    file=sys.stderr,
                )
            asset_path.write_bytes(asset.data)

    @staticmethod
    def asset_url_path(base_name: str, serial: int, extension: str) -> str:
        """Return the URL-encoded relative path for an embedded asset.

        This is a convenience static method for callers that need to build
        asset paths without going through the full write pipeline.

        Parameters
        ----------
        base_name:
            Stem of the source document (e.g. ``"Report Q1"``).
        serial:
            1-based serial number of the asset.
        extension:
            File extension including the leading dot (e.g. ``".png"``).

        Returns
        -------
        str
            URL-encoded relative path, e.g.
            ``"md_embedded/Report%20Q1_0001.png"``.
        """
        filename = f"{base_name}_{serial:04d}{extension}"
        encoded = url_quote(filename, safe="")
        return f"{EMBEDDED_DIR}/{encoded}"
