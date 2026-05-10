"""Unit tests for the public API — Task 11.6."""
from __future__ import annotations

from pathlib import Path

import pytest

from document2markdown import (
    Converter,
    Document,
    ConversionResult,
    ParagraphBlock,
    convert_file,
    convert_to_markdown,
)
from document2markdown.document_model import HeadingBlock
from document2markdown.utils import convert_batch, convert_directory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_txt(path: Path, text: str = "Hello API test.\n") -> None:
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Converter.convert
# ---------------------------------------------------------------------------

class TestConverterConvert:
    def test_returns_document_with_nonempty_result(self, tmp_path):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        doc = Converter().convert(f)
        assert isinstance(doc, Document)
        assert isinstance(doc.result, ConversionResult)
        assert len(doc.result.blocks) > 0


# ---------------------------------------------------------------------------
# Document.to_markdown
# ---------------------------------------------------------------------------

class TestDocumentToMarkdown:
    def test_returns_nonempty_string(self, tmp_path):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        doc = Converter().convert(f)
        md = doc.to_markdown()
        assert isinstance(md, str)
        assert md.strip()


# ---------------------------------------------------------------------------
# Document.save
# ---------------------------------------------------------------------------

class TestDocumentSave:
    def test_writes_md_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        doc = Converter().convert(f)
        saved = doc.save(out_dir)
        assert saved.exists()
        assert saved.suffix == ".md"
        assert saved.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# convert_file
# ---------------------------------------------------------------------------

class TestConvertFile:
    def test_no_output_writes_no_files(self, tmp_path):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        result = convert_file(f, output=None)
        assert isinstance(result, ConversionResult)
        # No .md file should have been written
        assert not list(tmp_path.glob("*.md"))

    def test_with_output_writes_md_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        convert_file(f, output=out_dir)
        assert (out_dir / "sample.md").exists()


# ---------------------------------------------------------------------------
# convert_to_markdown
# ---------------------------------------------------------------------------

class TestConvertToMarkdown:
    def test_same_result_as_document_to_markdown(self, tmp_path):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        md_via_api = convert_to_markdown(f)
        md_via_doc = Converter().convert(f).to_markdown()
        assert md_via_api == md_via_doc


# ---------------------------------------------------------------------------
# convert_batch
# ---------------------------------------------------------------------------

class TestConvertBatch:
    def test_continues_on_failure_one_entry_per_input(self, tmp_path):
        good = tmp_path / "good.txt"
        _make_txt(good)
        bad = tmp_path / "missing.txt"

        results = convert_batch([good, bad], Converter())
        assert len(results) == 2
        paths = [p for p, _ in results]
        assert good in paths
        assert bad in paths

        good_outcome = next(o for p, o in results if p == good)
        bad_outcome = next(o for p, o in results if p == bad)
        assert isinstance(good_outcome, Document)
        assert isinstance(bad_outcome, Exception)


# ---------------------------------------------------------------------------
# convert_directory
# ---------------------------------------------------------------------------

class TestConvertDirectory:
    def test_returns_entries_for_all_matching_files(self, tmp_path):
        for name in ("a.txt", "b.txt", "c.txt"):
            _make_txt(tmp_path / name)

        results = convert_directory(tmp_path, Converter(), pattern="*.txt")
        assert len(results) == 3
        result_paths = {p for p, _ in results}
        for name in ("a.txt", "b.txt", "c.txt"):
            assert tmp_path / name in result_paths

    def test_pattern_filters_files(self, tmp_path):
        _make_txt(tmp_path / "a.txt")
        (tmp_path / "b.html").write_text("<html></html>", encoding="utf-8")

        results = convert_directory(tmp_path, Converter(), pattern="*.txt")
        assert len(results) == 1
        assert results[0][0].name == "a.txt"


# ---------------------------------------------------------------------------
# Default output directory (Req 3.3)
# ---------------------------------------------------------------------------

class TestDefaultOutputDirectory:
    def test_default_output_written_to_output_dir_name(self, tmp_path):
        """When no output is specified, .md is written to {source_parent}/OUTPUT_DIR_NAME/."""
        src = tmp_path / "sample.txt"
        src.write_text("Hello default output.", encoding="utf-8")
        doc = Converter().convert(src)
        saved = doc.save()  # no output argument
        assert saved.exists()
        assert saved.parent == tmp_path / "Exports - Conversions"
        assert saved.name == "sample.md"
