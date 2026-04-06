"""Intermediate Representation (IR) for document conversion.

All converters produce a ConversionResult containing an ordered list of Block
objects and a list of EmbeddedAsset objects.  The renderer then serialises the
IR to the desired output format (default: GitHub-Flavored Markdown).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


# ---------------------------------------------------------------------------
# Embedded assets
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedAsset:
    """A binary asset (image, SVG, …) extracted from a source document."""

    data: bytes
    extension: str                    # e.g. ".png", ".svg"
    original_name: str | None         # original filename if available
    alt_text: str                     # alt text for Markdown image tag
    source_vector_format: str | None  # "emf" | "wmf" | "eps" | None
    # When source_vector_format is set, data contains converted SVG bytes
    # and extension is always ".svg".


# ---------------------------------------------------------------------------
# Block types
# ---------------------------------------------------------------------------

@dataclass
class HeadingBlock:
    """ATX Markdown heading (level 1–6)."""
    level: int   # 1–6
    text: str


@dataclass
class ParagraphBlock:
    """Plain paragraph of text."""
    text: str


@dataclass
class ListBlock:
    """Ordered or unordered list."""
    ordered: bool
    items: list[str]


@dataclass
class TableBlock:
    """GitHub-Flavored Markdown pipe table."""
    headers: list[str]
    rows: list[list[str]]


@dataclass
class CodeBlock:
    """Fenced code block."""
    language: str | None
    text: str


@dataclass
class ImageBlock:
    """Reference to an EmbeddedAsset by index."""
    asset_index: int
    alt: str


@dataclass
class LinkBlock:
    """Inline hyperlink."""
    text: str
    url: str


@dataclass
class UnsupportedBlock:
    """Placeholder for elements that could not be converted."""
    description: str


# Union type for all block variants
Block = Union[
    HeadingBlock,
    ParagraphBlock,
    ListBlock,
    TableBlock,
    CodeBlock,
    ImageBlock,
    LinkBlock,
    UnsupportedBlock,
]


# ---------------------------------------------------------------------------
# Conversion result
# ---------------------------------------------------------------------------

@dataclass
class ConversionResult:
    """The complete intermediate representation of a converted document."""

    blocks: list[Block] = field(default_factory=list)
    embedded: list[EmbeddedAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
