"""Property-based tests for the post-processor.

# Feature: document-to-markdown, Property 4: No excessive blank lines in output
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from document2markdown.document_model import ConversionResult, ParagraphBlock
from document2markdown.postprocess import postprocess
from document2markdown.renderer_base import MarkdownRenderer

# ---------------------------------------------------------------------------
# Property 4: No excessive blank lines in output
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 4: No excessive blank lines in output
@given(
    texts=st.lists(
        st.text(min_size=0, max_size=100),
        min_size=0,
        max_size=20,
    )
)
@settings(max_examples=100)
def test_property4_no_excessive_blank_lines(texts: list[str]) -> None:
    """Rendered Markdown never contains more than 2 consecutive blank lines."""
    blocks = [ParagraphBlock(text=t) for t in texts]
    result = ConversionResult(blocks=blocks, embedded=[], warnings=[])
    processed = postprocess(result)
    renderer = MarkdownRenderer(base_name="test")
    markdown = renderer.render(processed)

    # More than 2 consecutive blank lines means 3+ '\n' in a row
    assert "\n\n\n" not in markdown, (
        f"Found 3+ consecutive newlines in output. "
        f"Snippet: {markdown[:300]!r}"
    )
