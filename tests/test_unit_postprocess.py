"""Unit tests for postprocess module — Task 9.3."""
from __future__ import annotations

import copy

from document2markdown.document_model import (
    ConversionResult,
    HeadingBlock,
    ParagraphBlock,
)
from document2markdown.postprocess import postprocess


def _result(*blocks) -> ConversionResult:
    return ConversionResult(blocks=list(blocks))


class TestControlCharStripping:
    def test_null_bytes_removed(self):
        r = _result(ParagraphBlock(text="hello\x00world"))
        out = postprocess(r)
        assert out.blocks[0].text == "helloworld"

    def test_control_chars_removed(self):
        r = _result(ParagraphBlock(text="\x01\x02text\x1f"))
        out = postprocess(r)
        assert out.blocks[0].text == "text"

    def test_newline_and_tab_preserved(self):
        r = _result(ParagraphBlock(text="line1\nline2\ttabbed"))
        out = postprocess(r)
        assert "\n" in out.blocks[0].text
        assert "\t" in out.blocks[0].text


class TestBlankLineCollapse:
    def test_three_newlines_collapsed_to_two(self):
        r = _result(ParagraphBlock(text="a\n\n\nb"))
        out = postprocess(r)
        assert "\n\n\n" not in out.blocks[0].text
        assert out.blocks[0].text == "a\n\nb"

    def test_many_newlines_collapsed(self):
        r = _result(ParagraphBlock(text="x\n\n\n\n\ny"))
        out = postprocess(r)
        assert "\n\n\n" not in out.blocks[0].text


class TestPageNumberRemoval:
    def test_bare_integer_removed(self):
        r = _result(ParagraphBlock(text="1"))
        out = postprocess(r)
        assert not out.blocks

    def test_page_n_removed(self):
        r = _result(ParagraphBlock(text="Page 2"))
        out = postprocess(r)
        assert not out.blocks

    def test_n_of_m_removed(self):
        r = _result(ParagraphBlock(text="3 of 10"))
        out = postprocess(r)
        assert not out.blocks

    def test_normal_paragraph_kept(self):
        r = _result(ParagraphBlock(text="This is real content."))
        out = postprocess(r)
        assert len(out.blocks) == 1


class TestHeadingNormalisation:
    def test_min_level_shifted_to_h1(self):
        r = _result(
            HeadingBlock(level=2, text="First"),
            HeadingBlock(level=3, text="Second"),
        )
        out = postprocess(r)
        levels = [b.level for b in out.blocks if isinstance(b, HeadingBlock)]
        assert levels == [1, 2]

    def test_already_h1_unchanged(self):
        r = _result(
            HeadingBlock(level=1, text="Top"),
            HeadingBlock(level=2, text="Sub"),
        )
        out = postprocess(r)
        levels = [b.level for b in out.blocks if isinstance(b, HeadingBlock)]
        assert levels == [1, 2]


class TestImmutability:
    def test_original_not_mutated(self):
        original = _result(
            HeadingBlock(level=3, text="Title"),
            ParagraphBlock(text="hello\x00world"),
        )
        original_blocks_copy = [
            HeadingBlock(level=b.level, text=b.text) if isinstance(b, HeadingBlock)
            else ParagraphBlock(text=b.text)
            for b in original.blocks
        ]
        postprocess(original)
        # Original blocks should be unchanged
        for orig, copy_b in zip(original.blocks, original_blocks_copy):
            if isinstance(orig, HeadingBlock):
                assert orig.level == copy_b.level
                assert orig.text == copy_b.text
            elif isinstance(orig, ParagraphBlock):
                assert orig.text == copy_b.text
