"""Unit tests for TXTConverter and _looks_like_code heuristic."""
import tempfile
from pathlib import Path

import pytest

from document2markdown.converter_txt import TXTConverter, _looks_like_code
from document2markdown.document_model import CodeBlock, ParagraphBlock


def test_looks_like_code_detects_python():
    assert _looks_like_code("def foo():\n    return 42\n") is True


def test_looks_like_code_rejects_prose():
    assert _looks_like_code("Hello world.\n\nThis is prose.\n") is False


def test_txt_plain_paragraphs():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", encoding="utf-8", delete=False) as f:
        f.write("Hello world.\n\nThis is a second paragraph.\n\nAnd a third one here.")
        path = Path(f.name)
    result = TXTConverter().convert(path)
    assert all(isinstance(b, ParagraphBlock) for b in result.blocks)
    assert len(result.blocks) == 3


def test_txt_code_content():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", encoding="utf-8", delete=False) as f:
        f.write("def foo():\n    return 42\n\nclass Bar:\n    pass\n")
        path = Path(f.name)
    result = TXTConverter().convert(path)
    assert len(result.blocks) == 1
    assert isinstance(result.blocks[0], CodeBlock)
