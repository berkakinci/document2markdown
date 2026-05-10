"""HTML converter — maps DOM elements to IR blocks via BeautifulSoup4."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup, NavigableString, Tag

from document2markdown.converter_base import BaseConverter
from document2markdown.document_model import (
    CodeBlock,
    ConversionResult,
    EmbeddedAsset,
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

# Tags that are silently skipped (structural / metadata, not content)
_SKIP_TAGS = {"html", "head", "body", "script", "style", "meta", "title", "noscript"}

# Tags whose text content is inlined into the parent rather than emitted as blocks
_INLINE_TAGS = {"span", "strong", "em", "b", "i", "u", "s", "small", "mark", "abbr", "cite"}


def _get_text(tag: Tag) -> str:
    """Return stripped inner text of *tag*."""
    return tag.get_text(separator=" ", strip=True)


def _parse_data_uri(src: str) -> tuple[bytes, str] | None:
    """Parse a data URI and return ``(bytes, extension)``, or ``None`` if not a data URI."""
    if not src.startswith("data:"):
        return None
    # data:[<mediatype>][;base64],<data>
    try:
        header, _, encoded = src.partition(",")
        mime = header[5:].split(";")[0].strip() or "application/octet-stream"
        is_base64 = ";base64" in header
        if is_base64:
            data = base64.b64decode(encoded)
        else:
            from urllib.parse import unquote_to_bytes
            data = unquote_to_bytes(encoded)
        ext = mimetypes.guess_extension(mime) or ".bin"
        # Prefer common extensions over obscure ones
        _PREFERRED = {".jpeg": ".jpg", ".jpe": ".jpg", ".svgz": ".svg"}
        ext = _PREFERRED.get(ext, ext)
        return data, ext
    except Exception:  # noqa: BLE001
        return None


class HTMLConverter(BaseConverter):
    """Convert an HTML file to a :class:`ConversionResult`.

    Supported mappings:

    * ``<h1>``–``<h6>``  → :class:`HeadingBlock`
    * ``<ul>``           → :class:`ListBlock` (unordered)
    * ``<ol>``           → :class:`ListBlock` (ordered)
    * ``<table>``        → :class:`TableBlock`
    * ``<a>``            → :class:`LinkBlock`
    * ``<code>``/``<pre>`` → :class:`CodeBlock`
    * ``<img>``          → :class:`ImageBlock` (data URI extracted; external src → empty asset)
    * Everything else    → :class:`UnsupportedBlock`
    """

    def convert(self, source_path: Path) -> ConversionResult:
        html = source_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")

        blocks: list[Block] = []
        embedded: list[EmbeddedAsset] = []
        warnings: list[str] = []

        # Walk top-level children of <body> (or the whole document if no body)
        root = soup.body if soup.body else soup
        for child in root.children:
            if isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    blocks.append(UnsupportedBlock(description=f"bare text: {text[:80]}"))
                    warnings.append(f"bare text node skipped: {text[:80]!r}")
                continue

            if not isinstance(child, Tag):
                continue

            tag_name = child.name.lower() if child.name else ""

            if tag_name in _SKIP_TAGS:
                continue

            block = self._convert_tag(child, tag_name, embedded, warnings)
            if block is not None:
                blocks.append(block)

        return ConversionResult(blocks=blocks, embedded=embedded, warnings=warnings)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _convert_tag(
        self,
        tag: Tag,
        tag_name: str,
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> "Block | None":
        """Convert a single top-level tag to a Block, or return None."""

        # Headings
        if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag_name[1])
            return HeadingBlock(level=level, text=_get_text(tag))

        # Unordered list
        if tag_name == "ul":
            items = [_get_text(li) for li in tag.find_all("li", recursive=False)]
            return ListBlock(ordered=False, items=items)

        # Ordered list
        if tag_name == "ol":
            items = [_get_text(li) for li in tag.find_all("li", recursive=False)]
            return ListBlock(ordered=True, items=items)

        # Table
        if tag_name == "table":
            return self._convert_table(tag, warnings)

        # Anchor / hyperlink
        if tag_name == "a":
            href = tag.get("href", "")
            return LinkBlock(text=_get_text(tag), url=str(href))

        # Code / preformatted
        if tag_name in {"code", "pre"}:
            return CodeBlock(language=None, text=tag.get_text())

        # Image
        if tag_name == "img":
            return self._convert_img(tag, embedded, warnings)

        # Paragraph — recurse into children to pick up nested elements
        if tag_name == "p":
            return self._convert_p(tag, embedded, warnings)

        # Div / section / article — container elements not fully decomposed
        if tag_name in {
            "div", "section", "article", "main", "aside",
            "figure", "figcaption", "header", "footer", "nav",
        }:
            desc = f"<{tag_name}> container (content may be partially captured)"
            warnings.append(f"container element <{tag_name}> not fully decomposed")
            return UnsupportedBlock(description=desc)

        # Anything else
        desc = f"<{tag_name}> element"
        warnings.append(f"unsupported element <{tag_name}>: emitting UnsupportedBlock")
        return UnsupportedBlock(description=desc)

    def _convert_table(self, tag: Tag, warnings: list[str]) -> "Block":
        """Parse a ``<table>`` into a :class:`TableBlock`."""
        headers: list[str] = []
        rows: list[list[str]] = []

        thead = tag.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                headers = [_get_text(cell) for cell in header_row.find_all(["th", "td"])]

        tbody = tag.find("tbody") or tag
        for tr in tbody.find_all("tr", recursive=False):
            cells = [_get_text(cell) for cell in tr.find_all(["td", "th"])]
            if cells:
                if not headers:
                    headers = cells
                else:
                    rows.append(cells)

        if not headers and not rows:
            warnings.append("empty <table> encountered")
        return TableBlock(headers=headers, rows=rows)

    def _convert_img(
        self,
        tag: Tag,
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> "Block":
        """Convert an ``<img>`` tag to an :class:`ImageBlock`.

        * If ``src`` is a data URI, extract the binary data and extension.
        * Otherwise, create an :class:`EmbeddedAsset` with empty ``data``
          and use the ``src`` value as ``original_name``.
        """
        src = str(tag.get("src", ""))
        alt = str(tag.get("alt", "image"))

        if not src:
            warnings.append("<img> tag has no src attribute; emitting UnsupportedBlock")
            return UnsupportedBlock(description="<img> with no src")

        data_result = _parse_data_uri(src)
        if data_result is not None:
            # Data URI — extract embedded bytes
            data, ext = data_result
            asset = EmbeddedAsset(
                data=data,
                extension=ext,
                original_name=None,
                alt_text=alt,
                source_vector_format=None,
            )
        else:
            # External or relative URL — store src as original_name, empty data
            ext = Path(src.split("?")[0]).suffix or ".bin"
            asset = EmbeddedAsset(
                data=b"",
                extension=ext,
                original_name=src,
                alt_text=alt,
                source_vector_format=None,
            )

        asset_index = len(embedded)
        embedded.append(asset)
        return ImageBlock(asset_index=asset_index, alt=alt)

    def _convert_p(
        self,
        tag: Tag,
        embedded: list[EmbeddedAsset],
        warnings: list[str],
    ) -> "Block | None":
        """Convert a ``<p>`` tag.

        If the paragraph contains only an ``<img>``, emit an ImageBlock.
        If it contains only an ``<a>``, emit a LinkBlock.
        Otherwise emit a ParagraphBlock.
        """
        children = [
            c for c in tag.children
            if not (isinstance(c, NavigableString) and not c.strip())
        ]
        if len(children) == 1 and isinstance(children[0], Tag):
            child = children[0]
            child_name = child.name.lower() if child.name else ""
            if child_name == "img":
                return self._convert_img(child, embedded, warnings)
            if child_name == "a":
                href = child.get("href", "")
                return LinkBlock(text=_get_text(child), url=str(href))

        text = _get_text(tag)
        if text:
            return ParagraphBlock(text=text)
        return None  # type: ignore[return-value]
