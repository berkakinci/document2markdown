"""Property-based tests for OutputWriter.

# Feature: document-to-markdown, Property 6: Embedded asset paths are URL-encoded relative paths
# Feature: document-to-markdown, Property 8: Output path derivation
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from document2markdown.api import Converter
from document2markdown.document_model import (
    ConversionResult,
    EmbeddedAsset,
    ImageBlock,
)
from document2markdown.renderer_base import MarkdownRenderer

# ---------------------------------------------------------------------------
# Property 6: Embedded asset paths are URL-encoded relative paths
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 6: Embedded asset paths are URL-encoded relative paths
@given(
    base_name=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters=" _-",
        ),
    )
)
@settings(max_examples=100)
def test_property6_image_references_are_url_encoded_relative_paths(
    base_name: str,
) -> None:
    """Every ![...] reference in rendered Markdown starts with md_embedded/ and is URL-encoded."""
    assume(base_name.strip())  # skip all-whitespace names

    asset = EmbeddedAsset(
        data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 16,  # minimal PNG-like bytes
        extension=".png",
        original_name=None,
        alt_text="test image",
        source_vector_format=None,
    )
    result = ConversionResult(
        blocks=[ImageBlock(asset_index=0, alt="test image")],
        embedded=[asset],
        warnings=[],
    )

    renderer = MarkdownRenderer(base_name=base_name)
    markdown = renderer.render(result)

    # Find all image references: ![alt](path)
    image_refs = re.findall(r"!\[.*?\]\((.*?)\)", markdown)
    assert image_refs, f"No image references found in markdown: {markdown!r}"

    for ref in image_refs:
        # Must start with md_embedded/
        assert ref.startswith("md_embedded/"), (
            f"Image ref {ref!r} does not start with 'md_embedded/'"
        )
        # Must not contain raw spaces (must be URL-encoded)
        assert " " not in ref, (
            f"Raw space found in image reference: {ref!r}"
        )


# ---------------------------------------------------------------------------
# Property 8: Output path derivation
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 8: Output path derivation
@given(
    stem=st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_-",
        ),
    )
)
@settings(max_examples=100)
def test_property8_output_path_is_stem_dot_md(stem: str) -> None:
    """Output .md file is written to {output_dir}/{stem}.md exactly."""
    assume(stem.strip())  # skip empty/whitespace stems

    with tempfile.TemporaryDirectory() as src_dir:
        with tempfile.TemporaryDirectory() as out_dir:
            src_path = Path(src_dir) / f"{stem}.txt"
            src_path.write_text("Hello, world!", encoding="utf-8")

            output_dir = Path(out_dir)
            converter = Converter(output_dir=output_dir)
            doc = converter.convert(src_path)
            doc.save(output_dir)

            expected_md = output_dir / f"{stem}.md"
            assert expected_md.exists(), (
                f"Expected output file {expected_md} does not exist. "
                f"Files in output_dir: {list(output_dir.iterdir())}"
            )
