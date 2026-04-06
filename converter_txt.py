"""TXT converter — wraps plain-text content in a fenced code block or paragraphs."""

from __future__ import annotations

import re
from pathlib import Path

from document2markdown.converter_base import BaseConverter
from document2markdown.document_model import CodeBlock, ConversionResult, ParagraphBlock

# Patterns that suggest code-like content
# Patterns that suggest code-like content
_CODE_PATTERNS = re.compile(
    r'(?:'
    r'^\s{4,}\S'                                                          # 4+ leading spaces
    r'|^\t\S'                                                             # line-leading tab
    r'|[{};\[\]]'                                                         # code punctuation
    r'|\b(?:def|class|import|from|return|if|else|elif|for|while|try|except)\b'  # Python
    r'|\b(?:function|var|let|const)\b'                                    # JavaScript
    r'|=>'                                                                # arrow function
    r'|\b(?:public|private|protected|static|void|int|str|bool)\b'        # typed langs
    r'|<[a-zA-Z][^>]*>'                                                   # HTML/XML tags
    r'|\$\w+'                                                             # shell variables
    r'|^#!\S'                                                             # shebang
    r')',
    re.MULTILINE,
)


def _looks_like_code(text: str) -> bool:
    """Return True if *text* appears to contain code rather than prose."""
    if not text.strip():
        return False
    lines = text.splitlines()
    if not lines:
        return False
    # Check ratio of code-like lines
    code_line_count = sum(1 for line in lines if _CODE_PATTERNS.search(line))
    ratio = code_line_count / len(lines)
    return ratio > 0.15  # more than 15% of lines look code-like


class TXTConverter(BaseConverter):
    """Convert a plain-text file to a :class:`ConversionResult`.

    If the content looks like plain prose (no code-like patterns), each
    non-empty paragraph is emitted as a :class:`ParagraphBlock`.  Otherwise
    the entire content is wrapped in a single :class:`CodeBlock` with
    ``language=None`` (produces a plain fenced code block in Markdown).
    """

    def convert(self, source_path: Path) -> ConversionResult:
        """Read *source_path* as UTF-8 and return an appropriate block result."""
        text = source_path.read_text(encoding="utf-8")

        if _looks_like_code(text):
            return ConversionResult(blocks=[CodeBlock(language=None, text=text)])

        # Plain paragraphs — split on blank lines
        paragraphs = re.split(r"\n{2,}", text.strip())
        blocks = [
            ParagraphBlock(text=para.strip())
            for para in paragraphs
            if para.strip()
        ]
        if not blocks:
            # Empty file — emit a single empty paragraph
            blocks = [ParagraphBlock(text="")]
        return ConversionResult(blocks=blocks)
