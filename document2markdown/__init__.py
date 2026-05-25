"""document2markdown — convert documents to Markdown.

Public API
----------
OO interface (preferred):
    Converter, Document

Functional convenience API:
    convert_file, to_markdown, convert_to_markdown

Renderer interface:
    BaseRenderer, MarkdownRenderer

IR types:
    ConversionResult, EmbeddedAsset

Block types:
    HeadingBlock, ParagraphBlock, ListBlock, TableBlock,
    CodeBlock, ImageBlock, LinkBlock, UnsupportedBlock

Requirements: 9.1–9.7, 10.3
"""

from __future__ import annotations

from pathlib import Path

# OO API
from document2markdown.api import Converter
from document2markdown.document import Document

# Renderer interface
from document2markdown.renderer_base import BaseRenderer, MarkdownRenderer

# IR types
from document2markdown.document_model import (
    ConversionResult,
    EmbeddedAsset,
    HeadingBlock,
    ParagraphBlock,
    ListBlock,
    TableBlock,
    CodeBlock,
    ImageBlock,
    LinkBlock,
    UnsupportedBlock,
)

__all__ = [
    # OO API
    "Converter",
    "Document",
    # Renderer interface
    "BaseRenderer",
    "MarkdownRenderer",
    # IR types
    "ConversionResult",
    "EmbeddedAsset",
    # Block types
    "HeadingBlock",
    "ParagraphBlock",
    "ListBlock",
    "TableBlock",
    "CodeBlock",
    "ImageBlock",
    "LinkBlock",
    "UnsupportedBlock",
    # Functional API
    "convert_file",
    "to_markdown",
    "convert_to_markdown",
]


# ---------------------------------------------------------------------------
# Functional API
# ---------------------------------------------------------------------------

def convert_file(
    source_path: Path,
    output: Path | None = None,
    renderer: BaseRenderer | None = None,
) -> ConversionResult:
    """Run the full pipeline for *source_path*.

    If *output* is provided, write the ``.md`` file and ``md_embedded/``
    assets to disk.

    Parameters
    ----------
    source_path:
        Path to the source document.
    output:
        Destination directory (or file path) for the output.  When *None*,
        no files are written to disk.
    renderer:
        Renderer to use.  Defaults to
        :class:`~document2markdown.renderer_base.MarkdownRenderer`.

    Returns
    -------
    ConversionResult
        The post-processed intermediate representation.
    """
    converter = Converter(renderer=renderer)
    doc = converter.convert(Path(source_path))
    if output is not None:
        doc.save(Path(output))
    return doc.result


def to_markdown(
    result: ConversionResult,
    renderer: BaseRenderer | None = None,
) -> str:
    """Serialize *result* to a Markdown string (no disk I/O).

    Parameters
    ----------
    result:
        A :class:`~document2markdown.document_model.ConversionResult`.
    renderer:
        Renderer to use.  Defaults to
        :class:`~document2markdown.renderer_base.MarkdownRenderer`.

    Returns
    -------
    str
        The rendered Markdown string.
    """
    effective_renderer: BaseRenderer = renderer or MarkdownRenderer()
    return effective_renderer.render(result)


def convert_to_markdown(
    source_path: Path,
    renderer: BaseRenderer | None = None,
) -> str:
    """Convert *source_path* and return the rendered Markdown string.

    Convenience wrapper: runs the full pipeline and renders to a string
    without writing any files to disk.

    Parameters
    ----------
    source_path:
        Path to the source document.
    renderer:
        Renderer to use.  Defaults to
        :class:`~document2markdown.renderer_base.MarkdownRenderer`.

    Returns
    -------
    str
        The rendered Markdown string.
    """
    converter = Converter(renderer=renderer)
    doc = converter.convert(Path(source_path))
    return doc.to_markdown()
