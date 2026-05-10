"""Unit tests for MarkdownRenderer and OutputWriter — Task 9.8."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote as url_quote

import pytest

from document2markdown.document_model import (
    CodeBlock,
    ConversionResult,
    EmbeddedAsset,
    HeadingBlock,
    ImageBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
)
from document2markdown.renderer_base import BaseRenderer, MarkdownRenderer
from document2markdown.writer import OutputWriter


def _result(*blocks, embedded=None) -> ConversionResult:
    return ConversionResult(blocks=list(blocks), embedded=embedded or [])


# ---------------------------------------------------------------------------
# MarkdownRenderer
# ---------------------------------------------------------------------------

class TestMarkdownRenderer:
    def test_nonempty_output_for_valid_result(self):
        r = _result(ParagraphBlock(text="Hello"))
        md = MarkdownRenderer().render(r)
        assert md.strip()

    def test_heading_level1(self):
        r = _result(HeadingBlock(level=1, text="Title"))
        md = MarkdownRenderer().render(r)
        assert "# Title" in md

    def test_unordered_list(self):
        r = _result(ListBlock(ordered=False, items=["a", "b"]))
        md = MarkdownRenderer().render(r)
        assert "- a" in md
        assert "- b" in md

    def test_ordered_list(self):
        r = _result(ListBlock(ordered=True, items=["x", "y"]))
        md = MarkdownRenderer().render(r)
        assert "1. x" in md
        assert "2. y" in md

    def test_table_gfm_pipe(self):
        r = _result(TableBlock(headers=["A", "B"], rows=[["1", "2"]]))
        md = MarkdownRenderer().render(r)
        assert "| A | B |" in md
        assert "|" in md
        assert "1" in md

    def test_code_block_fenced(self):
        r = _result(CodeBlock(language="python", text="x = 1"))
        md = MarkdownRenderer().render(r)
        assert "```python" in md
        assert "x = 1" in md
        assert "```" in md

    def test_image_block_url_encoded_path(self):
        asset = EmbeddedAsset(
            data=b"\x89PNG",
            extension=".png",
            original_name="my image.png",
            alt_text="my image",
            source_vector_format=None,
        )
        r = _result(ImageBlock(asset_index=0, alt="my image"), embedded=[asset])
        md = MarkdownRenderer(base_name="doc name").render(r)
        assert "![my image](" in md
        assert "md_embedded/" in md
        # Path must be URL-encoded (space → %20)
        assert "%20" in md or "doc%20name" in md

    def test_custom_renderer_used(self):
        class UpperRenderer(BaseRenderer):
            def render(self, result):
                return "CUSTOM"

        r = _result(ParagraphBlock(text="ignored"))
        md = UpperRenderer().render(r)
        assert md == "CUSTOM"


# ---------------------------------------------------------------------------
# OutputWriter
# ---------------------------------------------------------------------------

class TestOutputWriter:
    def test_creates_output_dir_when_missing(self, tmp_path):
        new_dir = tmp_path / "new" / "nested"
        assert not new_dir.exists()
        r = _result(ParagraphBlock(text="Hello"))
        src = tmp_path / "doc.txt"
        src.write_text("Hello")
        writer = OutputWriter()
        md_path, skipped = writer.write(r, src, new_dir)
        assert new_dir.exists()
        assert md_path.exists()
        assert not skipped

    def test_overwrites_existing_file_warns_stderr(self, tmp_path, capsys):
        r = _result(ParagraphBlock(text="Hello"))
        src = tmp_path / "doc.txt"
        src.write_text("Hello")
        writer = OutputWriter()
        # Write once
        writer.write(r, src, tmp_path)
        # Touch source so it's newer than target — triggers overwrite path
        import os, time
        time.sleep(0.05)
        os.utime(src, None)
        # Write again — should warn about overwriting
        writer.write(r, src, tmp_path)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err or "overwriting" in captured.err.lower()

    def test_writes_embedded_assets_to_md_embedded(self, tmp_path):
        asset = EmbeddedAsset(
            data=b"\x89PNG",
            extension=".png",
            original_name=None,
            alt_text="img",
            source_vector_format=None,
        )
        r = _result(ImageBlock(asset_index=0, alt="img"), embedded=[asset])
        src = tmp_path / "report.txt"
        src.write_text("x")
        writer = OutputWriter()
        writer.write(r, src, tmp_path)
        embedded_dir = tmp_path / "md_embedded"
        assert embedded_dir.exists()
        assets = list(embedded_dir.iterdir())
        assert len(assets) == 1
        assert assets[0].name == "report_0001.png"

    def test_asset_naming_convention(self, tmp_path):
        """Assets named {base_name}_{serial:04d}{ext}."""
        assets = [
            EmbeddedAsset(data=b"a", extension=".png", original_name=None,
                          alt_text="a", source_vector_format=None),
            EmbeddedAsset(data=b"b", extension=".svg", original_name=None,
                          alt_text="b", source_vector_format=None),
        ]
        r = ConversionResult(
            blocks=[ImageBlock(0, "a"), ImageBlock(1, "b")],
            embedded=assets,
        )
        src = tmp_path / "My Doc.txt"
        src.write_text("x")
        OutputWriter().write(r, src, tmp_path)
        names = {f.name for f in (tmp_path / "md_embedded").iterdir()}
        assert "My Doc_0001.png" in names
        assert "My Doc_0002.svg" in names


    def test_image_block_renders_inline_markdown_syntax(self):
        """ImageBlock renders as ![alt](md_embedded/...) — Req 2.6."""
        import re
        import struct, zlib

        def _minimal_png():
            def _chunk(tag, data):
                c = struct.pack(">I", len(data)) + tag + data
                return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            sig = b"\x89PNG\r\n\x1a\n"
            ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            idat = _chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
            iend = _chunk(b"IEND", b"")
            return sig + ihdr + idat + iend

        asset = EmbeddedAsset(
            data=_minimal_png(), extension=".png",
            original_name="chart.png", alt_text="chart",
            source_vector_format=None,
        )
        r = _result(ImageBlock(asset_index=0, alt="chart"), embedded=[asset])
        md = MarkdownRenderer(base_name="report").render(r)

        assert "![chart](" in md
        refs = re.findall(r"!\[.*?\]\((.*?)\)", md)
        for ref in refs:
            assert not ref.startswith("/"), f"Image ref must be relative: {ref!r}"
            assert ref.startswith("md_embedded/"), f"Must start with md_embedded/: {ref!r}"
