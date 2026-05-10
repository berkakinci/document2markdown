"""Property-based tests for the HTML converter — heading level preservation.

# Feature: document-to-markdown, Property 5: Heading round-trip level preservation (HTML)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from document2markdown.converter_html import HTMLConverter
from document2markdown.document_model import HeadingBlock

# ---------------------------------------------------------------------------
# Property 5 (HTML): Heading level round-trip
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 5: Heading round-trip level preservation (HTML)
@given(level=st.integers(min_value=1, max_value=6))
@settings(max_examples=100)
def test_property5_html_heading_level_preserved(level: int) -> None:
    """HTML <h{level}> produces a HeadingBlock at the corresponding level."""
    text = f"Heading Level {level}"
    html = f"<html><body><h{level}>{text}</h{level}></body></html>"

    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(html)
        path = Path(f.name)

    converter = HTMLConverter()
    result = converter.convert(path)

    heading_blocks = [b for b in result.blocks if isinstance(b, HeadingBlock)]
    assert heading_blocks, (
        f"No HeadingBlock found for level={level}. Blocks: {result.blocks}"
    )

    levels_found = [b.level for b in heading_blocks]
    assert level in levels_found, (
        f"Expected HeadingBlock with level={level}, found levels: {levels_found}"
    )
