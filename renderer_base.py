"""Output renderer abstraction and default GFM Markdown renderer.

Requirements: 10.1, 10.2
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from urllib.parse import quote as url_quote

from document2markdown.config import EMBEDDED_DIR, MAX_CONSECUTIVE_BLANK_LINES
from document2markdown.document_model import (
    CodeBlock,
    ConversionResult,
    HeadingBlock,
    ImageBlock,
    LinkBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
    UnsupportedBlock,
)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseRenderer(ABC):
    """Interface that all output renderers must implement.

    Third-party code can subclass this and pass an instance to ``Converter``
    or the functional API to produce alternative output formats.
    """

    @abstractmethod
    def render(self, result: ConversionResult) -> str:
        """Serialize *result* to an output string.

        Parameters
        ----------
        result:
            The intermediate representation produced by a converter.

        Returns
        -------
        str
            The rendered document as a string (e.g. Markdown, HTML, plain text).
        """


# ---------------------------------------------------------------------------
# GFM Markdown renderer
# ---------------------------------------------------------------------------

class MarkdownRenderer(BaseRenderer):
    """Default renderer — produces GitHub-Flavored Markdown (GFM).

    Image references use URL-encoded relative paths pointing into the
    ``md_embedded/`` asset directory.  The caller (``OutputWriter``) is
    responsible for supplying the ``base_name`` used to build those paths.

    Parameters
    ----------
    base_name:
        The stem of the output ``.md`` file (e.g. ``"Report Q1"``).
        Used to construct ``md_embedded/{base_name}_{serial:04d}{ext}`` paths.
        If *None*, asset references fall back to a generic placeholder.
    """

    def __init__(self, base_name: str | None = None) -> None:
        self._base_name = base_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, result: ConversionResult) -> str:
        """Render *result* to a GFM Markdown string."""
        parts: list[str] = []

        for block in result.blocks:
            rendered = self._render_block(block, result)
            if rendered is not None:
                parts.append(rendered)

        raw = "\n\n".join(parts)
        return self._collapse_blank_lines(raw)

    # ------------------------------------------------------------------
    # Block renderers
    # ------------------------------------------------------------------

    def _render_block(self, block: object, result: ConversionResult) -> str | None:
        """Dispatch to the appropriate per-block renderer."""
        if isinstance(block, HeadingBlock):
            return self._render_heading(block)
        if isinstance(block, ParagraphBlock):
            return self._render_paragraph(block)
        if isinstance(block, ListBlock):
            return self._render_list(block)
        if isinstance(block, TableBlock):
            return self._render_table(block)
        if isinstance(block, CodeBlock):
            return self._render_code(block)
        if isinstance(block, ImageBlock):
            return self._render_image(block, result)
        if isinstance(block, LinkBlock):
            return self._render_link(block)
        if isinstance(block, UnsupportedBlock):
            return self._render_unsupported(block)
        # Unknown block type — emit a comment so content is not silently lost
        return f"<!-- unsupported block type: {type(block).__name__} -->"

    def _render_heading(self, block: HeadingBlock) -> str:
        level = max(1, min(6, block.level))
        return f"{'#' * level} {block.text}"

    def _render_paragraph(self, block: ParagraphBlock) -> str:
        return block.text.strip()

    def _render_list(self, block: ListBlock) -> str:
        lines: list[str] = []
        for i, item in enumerate(block.items, start=1):
            prefix = f"{i}." if block.ordered else "-"
            lines.append(f"{prefix} {item}")
        return "\n".join(lines)

    def _render_table(self, block: TableBlock) -> str:
        if not block.headers and not block.rows:
            return ""

        headers = block.headers or ([""] * len(block.rows[0]) if block.rows else [])
        sep = ["-" * max(3, len(h)) for h in headers]

        def _row(cells: list[str]) -> str:
            # Pad or truncate to match header count
            padded = list(cells) + [""] * max(0, len(headers) - len(cells))
            padded = padded[: len(headers)]
            return "| " + " | ".join(padded) + " |"

        lines = [_row(headers), "| " + " | ".join(sep) + " |"]
        for row in block.rows:
            lines.append(_row(row))
        return "\n".join(lines)

    def _render_code(self, block: CodeBlock) -> str:
        lang = block.language or ""
        return f"```{lang}\n{block.text}\n```"

    def _render_image(self, block: ImageBlock, result: ConversionResult) -> str:
        alt = block.alt or "image"
        if block.asset_index < len(result.embedded):
            asset = result.embedded[block.asset_index]
            path = self._asset_path(block.asset_index, asset.extension)
        else:
            path = f"md_embedded/asset_{block.asset_index:04d}"
        return f"![{alt}]({path})"

    def _render_link(self, block: LinkBlock) -> str:
        return f"[{block.text}]({block.url})"

    def _render_unsupported(self, block: UnsupportedBlock) -> str:
        return f"<!-- unsupported: {block.description} -->"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _asset_path(self, serial: int, extension: str) -> str:
        """Build a URL-encoded relative path for an embedded asset.

        Produces: ``md_embedded/{base_name}_{serial:04d}{ext}``
        """
        if self._base_name:
            filename = f"{self._base_name}_{serial + 1:04d}{extension}"
        else:
            filename = f"asset_{serial + 1:04d}{extension}"
        # URL-encode the filename component (handles spaces and special chars)
        encoded = url_quote(filename, safe="")
        return f"{EMBEDDED_DIR}/{encoded}"

    @staticmethod
    def _collapse_blank_lines(text: str) -> str:
        """Ensure no more than MAX_CONSECUTIVE_BLANK_LINES blank lines appear."""
        max_nl = MAX_CONSECUTIVE_BLANK_LINES + 1  # +1 because blank line = 2 \n
        pattern = re.compile(r"\n{" + str(max_nl + 1) + r",}")
        return pattern.sub("\n" * max_nl, text)
