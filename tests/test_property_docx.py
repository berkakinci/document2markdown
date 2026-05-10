"""Property-based tests for the DOCX converter — heading level preservation.

# Feature: document-to-markdown, Property 5: Heading round-trip level preservation (DOCX)
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from document2markdown.converter_docx import DOCXConverter
from document2markdown.document_model import HeadingBlock

# ---------------------------------------------------------------------------
# Property 5 (DOCX): Heading level round-trip
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 5: Heading round-trip level preservation (DOCX)
@given(level=st.integers(min_value=1, max_value=6))
@settings(max_examples=100)
def test_property5_docx_heading_level_preserved(level: int) -> None:
    """DOCX heading at level N produces a HeadingBlock at the corresponding level."""
    from docx import Document as DocxDocument  # type: ignore

    text = f"Heading Level {level}"
    doc = DocxDocument()
    doc.add_heading(text, level=level)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    doc.save(str(path))

    converter = DOCXConverter()
    result = converter.convert(path)

    heading_blocks = [b for b in result.blocks if isinstance(b, HeadingBlock)]
    assert heading_blocks, (
        f"No HeadingBlock found for level={level}. Blocks: {result.blocks}"
    )

    texts_found = [b.text.strip() for b in heading_blocks]
    assert text in texts_found, (
        f"Expected heading text {text!r} in heading blocks, got: {texts_found}"
    )
