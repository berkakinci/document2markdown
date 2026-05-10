"""Post-processor for ConversionResult IR.

Applies cleanup passes to the blocks in a ConversionResult:
- Strips non-printable control characters (except \\n, \\t) from text fields
- Strips page numbers, headers, and footers via heuristic patterns
- Normalises heading levels (ensures H1 is not duplicated excessively)
- Collapses runs of more than two consecutive blank lines (enforced at render
  time by MarkdownRenderer, but also applied here to ParagraphBlock text)

Requirements: 6.2, 6.4
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from document2markdown.document_model import Block

# ---------------------------------------------------------------------------
# Control-character stripping
# ---------------------------------------------------------------------------

# Match any C0/C1 control character except \t (0x09) and \n (0x0A).
# This covers 0x00–0x08, 0x0B–0x0C, 0x0E–0x1F, 0x7F, 0x80–0x9F.
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]")


def _strip_ctrl(text: str) -> str:
    """Remove non-printable control characters, keeping \\n and \\t."""
    return _CTRL_RE.sub("", text)


# ---------------------------------------------------------------------------
# Page-number / header / footer heuristics
# ---------------------------------------------------------------------------

# Patterns that strongly suggest a line is a page number or running header/footer.
# Each pattern is applied to a *stripped* single line.
_PAGE_NUMBER_RE = re.compile(
    r"""
    ^                           # start of line
    (?:
        page\s+\d+              # "Page 3", "page 12"
        | \d+\s+of\s+\d+        # "3 of 12"
        | -\s*\d+\s*-           # "- 3 -"
        | \d+                   # bare integer (only if very short line)
    )
    $                           # end of line
    """,
    re.IGNORECASE | re.VERBOSE,
)

# A bare integer line is only treated as a page number if it is ≤ 4 digits.
_BARE_INT_RE = re.compile(r"^\d{1,4}$")

# Running headers/footers often repeat the same short text on every page.
# We use a length heuristic: a paragraph of ≤ 60 chars that matches common
# footer patterns (confidential, copyright, date-like strings, etc.).
_FOOTER_HEADER_RE = re.compile(
    r"""
    (?:
        confidential            # "Confidential"
        | proprietary
        | all\s+rights\s+reserved
        | copyright\s*©?
        | ©
        | draft
        | \b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4}\b
        | \d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}   # date like 01/01/2024
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _is_page_number_or_running_text(text: str) -> bool:
    """Return True if *text* looks like a page number, header, or footer."""
    stripped = text.strip()
    if not stripped:
        return False
    # Bare integer (≤ 4 digits) → page number
    if _BARE_INT_RE.match(stripped):
        return True
    # Explicit page-number patterns
    if _PAGE_NUMBER_RE.match(stripped):
        return True
    # Short line matching footer/header keywords
    if len(stripped) <= 80 and _FOOTER_HEADER_RE.search(stripped):
        return True
    return False


# ---------------------------------------------------------------------------
# Heading-level normalisation
# ---------------------------------------------------------------------------

def _normalise_heading_levels(blocks: list[Block]) -> list[Block]:
    """Shift heading levels so the minimum level present becomes H1.

    If the document already starts at H1 (or has no headings), nothing changes.
    If the minimum heading level is H2, all headings are shifted down by 1, etc.
    Levels are clamped to the 1–6 range after shifting.
    """
    heading_levels = [b.level for b in blocks if isinstance(b, HeadingBlock)]
    if not heading_levels:
        return blocks

    min_level = min(heading_levels)
    if min_level == 1:
        return blocks  # already normalised

    shift = min_level - 1
    result: list[Block] = []
    for block in blocks:
        if isinstance(block, HeadingBlock):
            new_level = max(1, min(6, block.level - shift))
            result.append(HeadingBlock(level=new_level, text=block.text))
        else:
            result.append(block)
    return result


# ---------------------------------------------------------------------------
# Text-field helpers
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Strip control chars and collapse internal runs of 3+ blank lines."""
    text = _strip_ctrl(text)
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def postprocess(result: ConversionResult) -> ConversionResult:
    """Apply all post-processing passes to *result* and return a new instance.

    Passes (in order):
    1. Strip control characters from all text fields.
    2. Remove blocks that look like page numbers / running headers/footers.
    3. Normalise heading levels.

    The original *result* is not mutated.
    """
    blocks: list[Block] = []

    for block in result.blocks:
        if isinstance(block, HeadingBlock):
            cleaned = _clean_text(block.text)
            if not _is_page_number_or_running_text(cleaned):
                blocks.append(HeadingBlock(level=block.level, text=cleaned))

        elif isinstance(block, ParagraphBlock):
            cleaned = _clean_text(block.text)
            if cleaned.strip() and not _is_page_number_or_running_text(cleaned):
                blocks.append(ParagraphBlock(text=cleaned))

        elif isinstance(block, ListBlock):
            cleaned_items = [_clean_text(item) for item in block.items]
            cleaned_items = [i for i in cleaned_items if i.strip()]
            if cleaned_items:
                blocks.append(ListBlock(ordered=block.ordered, items=cleaned_items))

        elif isinstance(block, TableBlock):
            cleaned_headers = [_clean_text(h) for h in block.headers]
            cleaned_rows = [
                [_clean_text(cell) for cell in row] for row in block.rows
            ]
            blocks.append(TableBlock(headers=cleaned_headers, rows=cleaned_rows))

        elif isinstance(block, CodeBlock):
            # Preserve code verbatim — only strip C0/C1 control chars
            cleaned = _strip_ctrl(block.text)
            blocks.append(CodeBlock(language=block.language, text=cleaned))

        elif isinstance(block, (ImageBlock, LinkBlock, UnsupportedBlock)):
            # These blocks have no free-form text to clean (or we leave them as-is)
            blocks.append(block)

        else:
            # Unknown block type — pass through unchanged
            blocks.append(block)

    blocks = _normalise_heading_levels(blocks)

    return ConversionResult(
        blocks=blocks,
        embedded=result.embedded,
        warnings=list(result.warnings),
    )
