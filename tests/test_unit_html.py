"""Unit tests for HTMLConverter."""
import tempfile
from pathlib import Path

import pytest

from document2markdown.converter_html import HTMLConverter
from document2markdown.document_model import (
    CodeBlock, HeadingBlock, LinkBlock, ListBlock,
    ParagraphBlock, TableBlock, UnsupportedBlock,
)


def _html_file(content: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", encoding="utf-8", delete=False) as f:
        f.write(content)
        return Path(f.name)


def test_headings():
    path = _html_file("<html><body><h1>Title</h1><h2>Sub</h2><h3>Sub2</h3></body></html>")
    result = HTMLConverter().convert(path)
    headings = [b for b in result.blocks if isinstance(b, HeadingBlock)]
    assert len(headings) == 3
    assert headings[0].level == 1 and headings[0].text == "Title"
    assert headings[1].level == 2 and headings[1].text == "Sub"
    assert headings[2].level == 3 and headings[2].text == "Sub2"


def test_lists():
    path = _html_file("<html><body><ul><li>A</li><li>B</li></ul><ol><li>1</li><li>2</li></ol></body></html>")
    result = HTMLConverter().convert(path)
    lists = [b for b in result.blocks if isinstance(b, ListBlock)]
    assert len(lists) == 2
    assert lists[0].ordered is False
    assert lists[1].ordered is True


def test_table():
    path = _html_file(
        "<html><body><table>"
        "<thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td></tr></tbody>"
        "</table></body></html>"
    )
    result = HTMLConverter().convert(path)
    tables = [b for b in result.blocks if isinstance(b, TableBlock)]
    assert len(tables) == 1
    assert tables[0].headers == ["A", "B"]
    assert tables[0].rows == [["1", "2"]]


def test_link():
    path = _html_file('<html><body><a href="https://example.com">Click</a></body></html>')
    result = HTMLConverter().convert(path)
    links = [b for b in result.blocks if isinstance(b, LinkBlock)]
    assert len(links) == 1
    assert links[0].text == "Click"
    assert links[0].url == "https://example.com"


def test_code_block():
    path = _html_file("<html><body><pre>print('hello')</pre></body></html>")
    result = HTMLConverter().convert(path)
    code_blocks = [b for b in result.blocks if isinstance(b, CodeBlock)]
    assert len(code_blocks) == 1


def test_paragraph():
    path = _html_file("<html><body><p>Hello world</p></body></html>")
    result = HTMLConverter().convert(path)
    paras = [b for b in result.blocks if isinstance(b, ParagraphBlock)]
    assert len(paras) == 1
    assert paras[0].text == "Hello world"


def test_unsupported_element():
    path = _html_file("<html><body><video src='x.mp4'></video></body></html>")
    result = HTMLConverter().convert(path)
    unsupported = [b for b in result.blocks if isinstance(b, UnsupportedBlock)]
    assert len(unsupported) == 1


# ---------------------------------------------------------------------------
# _parse_data_uri
# ---------------------------------------------------------------------------

class TestParseDataUri:
    def test_base64_png_data_uri(self):
        from document2markdown.converter_html import _parse_data_uri
        import base64
        data = b"\x89PNG\r\n\x1a\n"
        uri = "data:image/png;base64," + base64.b64encode(data).decode()
        result = _parse_data_uri(uri)
        assert result is not None
        assert result[0] == data
        assert result[1] == ".png"

    def test_jpeg_extension_normalised_to_jpg(self):
        from document2markdown.converter_html import _parse_data_uri
        import base64
        uri = "data:image/jpeg;base64," + base64.b64encode(b"JFIF").decode()
        result = _parse_data_uri(uri)
        assert result is not None
        assert result[1] == ".jpg"

    def test_percent_encoded_data_uri(self):
        from document2markdown.converter_html import _parse_data_uri
        uri = "data:text/plain,Hello%20World"
        result = _parse_data_uri(uri)
        assert result is not None
        assert result[0] == b"Hello World"

    def test_non_data_uri_returns_none(self):
        from document2markdown.converter_html import _parse_data_uri
        assert _parse_data_uri("https://example.com/img.png") is None

    def test_malformed_data_uri_returns_none(self):
        from document2markdown.converter_html import _parse_data_uri
        # Invalid base64 payload
        result = _parse_data_uri("data:image/png;base64,!!!not_valid_base64!!!")
        assert result is None


# ---------------------------------------------------------------------------
# Bare text nodes and skip tags
# ---------------------------------------------------------------------------

class TestBareTextAndSkipTags:
    def test_bare_text_node_emits_unsupported(self):
        """A bare text node directly under <body> should produce an UnsupportedBlock."""
        path = _html_file("<html><body>bare text here</body></html>")
        result = HTMLConverter().convert(path)
        unsupported = [b for b in result.blocks if isinstance(b, UnsupportedBlock)]
        assert any("bare text" in b.description for b in unsupported)
        assert any("bare text" in w for w in result.warnings)

    def test_script_and_style_tags_skipped(self):
        """<script> and <style> tags should produce no blocks."""
        path = _html_file(
            "<html><body>"
            "<script>alert('x')</script>"
            "<style>body{color:red}</style>"
            "<p>Real content</p>"
            "</body></html>"
        )
        result = HTMLConverter().convert(path)
        paras = [b for b in result.blocks if isinstance(b, ParagraphBlock)]
        assert len(paras) == 1
        assert paras[0].text == "Real content"


# ---------------------------------------------------------------------------
# <p> tag edge cases
# ---------------------------------------------------------------------------

class TestParagraphEdgeCases:
    def test_p_containing_only_img_emits_image_block(self):
        """<p><img src='x.png'></p> should emit an ImageBlock, not a ParagraphBlock."""
        from document2markdown.document_model import ImageBlock
        path = _html_file('<html><body><p><img src="photo.png" alt="a photo"></p></body></html>')
        result = HTMLConverter().convert(path)
        image_blocks = [b for b in result.blocks if isinstance(b, ImageBlock)]
        assert len(image_blocks) == 1
        assert image_blocks[0].alt == "a photo"

    def test_p_containing_only_a_emits_link_block(self):
        """<p><a href='...'>text</a></p> should emit a LinkBlock."""
        path = _html_file('<html><body><p><a href="https://x.com">Go</a></p></body></html>')
        result = HTMLConverter().convert(path)
        links = [b for b in result.blocks if isinstance(b, LinkBlock)]
        assert len(links) == 1
        assert links[0].url == "https://x.com"

    def test_empty_p_produces_no_block(self):
        """An empty <p></p> should not produce any block."""
        path = _html_file("<html><body><p></p><p>Real</p></body></html>")
        result = HTMLConverter().convert(path)
        paras = [b for b in result.blocks if isinstance(b, ParagraphBlock)]
        assert len(paras) == 1
        assert paras[0].text == "Real"


# ---------------------------------------------------------------------------
# <img> edge cases
# ---------------------------------------------------------------------------

class TestImgEdgeCases:
    def test_img_with_no_src_emits_unsupported(self):
        """<img> with no src should emit an UnsupportedBlock."""
        path = _html_file("<html><body><img alt='broken'></body></html>")
        result = HTMLConverter().convert(path)
        unsupported = [b for b in result.blocks if isinstance(b, UnsupportedBlock)]
        assert len(unsupported) == 1

    def test_img_with_external_src_emits_image_block(self):
        """<img src='https://...'> should emit an ImageBlock with empty data."""
        from document2markdown.document_model import ImageBlock
        path = _html_file('<html><body><img src="https://example.com/img.png" alt="ext"></body></html>')
        result = HTMLConverter().convert(path)
        image_blocks = [b for b in result.blocks if isinstance(b, ImageBlock)]
        assert len(image_blocks) == 1
        assert result.embedded[0].data == b""
        assert result.embedded[0].original_name == "https://example.com/img.png"

    def test_img_with_data_uri_extracts_bytes(self):
        """<img src='data:...'> should extract binary data into EmbeddedAsset."""
        import base64
        from document2markdown.document_model import ImageBlock
        png = b"\x89PNG\r\n\x1a\n"
        uri = "data:image/png;base64," + base64.b64encode(png).decode()
        path = _html_file(f'<html><body><img src="{uri}" alt="inline"></body></html>')
        result = HTMLConverter().convert(path)
        image_blocks = [b for b in result.blocks if isinstance(b, ImageBlock)]
        assert len(image_blocks) == 1
        assert result.embedded[0].data == png


# ---------------------------------------------------------------------------
# <table> edge cases
# ---------------------------------------------------------------------------

class TestTableEdgeCases:
    def test_table_without_thead_uses_first_row_as_headers(self):
        """A table with no <thead> should treat the first row as headers."""
        path = _html_file(
            "<html><body><table>"
            "<tr><td>Col1</td><td>Col2</td></tr>"
            "<tr><td>val1</td><td>val2</td></tr>"
            "</table></body></html>"
        )
        result = HTMLConverter().convert(path)
        tables = [b for b in result.blocks if isinstance(b, TableBlock)]
        assert len(tables) == 1
        assert tables[0].headers == ["Col1", "Col2"]
        assert tables[0].rows == [["val1", "val2"]]

    def test_empty_table_produces_table_block_with_warning(self):
        """An empty <table> should still produce a TableBlock and a warning."""
        path = _html_file("<html><body><table></table></body></html>")
        result = HTMLConverter().convert(path)
        tables = [b for b in result.blocks if isinstance(b, TableBlock)]
        assert len(tables) == 1
        assert any("empty" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Container and unknown elements
# ---------------------------------------------------------------------------

class TestContainerAndUnknownElements:
    def test_div_emits_unsupported_with_warning(self):
        """<div> should emit an UnsupportedBlock and a warning."""
        path = _html_file("<html><body><div>some content</div></body></html>")
        result = HTMLConverter().convert(path)
        unsupported = [b for b in result.blocks if isinstance(b, UnsupportedBlock)]
        assert len(unsupported) == 1
        assert any("div" in w for w in result.warnings)

    def test_unknown_tag_emits_unsupported_with_warning(self):
        """An unrecognised tag should emit an UnsupportedBlock and a warning."""
        path = _html_file("<html><body><marquee>old school</marquee></body></html>")
        result = HTMLConverter().convert(path)
        unsupported = [b for b in result.blocks if isinstance(b, UnsupportedBlock)]
        assert len(unsupported) == 1
        assert any("marquee" in w for w in result.warnings)

    def test_h4_h5_h6_headings(self):
        """h4, h5, h6 should produce HeadingBlocks at the correct level."""
        path = _html_file(
            "<html><body><h4>Four</h4><h5>Five</h5><h6>Six</h6></body></html>"
        )
        result = HTMLConverter().convert(path)
        headings = [b for b in result.blocks if isinstance(b, HeadingBlock)]
        assert len(headings) == 3
        assert headings[0].level == 4
        assert headings[1].level == 5
        assert headings[2].level == 6
