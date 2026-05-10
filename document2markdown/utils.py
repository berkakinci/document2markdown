"""Batch and directory conversion utilities for document2markdown.

Thin wrappers over the single-file Converter API for multi-file use cases.
The core library stays single-file only; these helpers are opt-in.

Requirements: 4.1–4.5
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Union

from document2markdown.config import OUTPUT_DIR_NAME

if TYPE_CHECKING:
    from document2markdown.api import Converter
    from document2markdown.document import Document


def convert_batch(
    paths: list[Path],
    converter: "Converter",
) -> "list[tuple[Path, Union[Document, Exception]]]":
    """Convert a list of files, capturing exceptions instead of raising.

    Each file is processed independently.  If a file fails, the exception
    is stored in the result list and processing continues.

    Parameters
    ----------
    paths:
        Ordered list of source document paths to convert.
    converter:
        A :class:`~document2markdown.api.Converter` instance.

    Returns
    -------
    list[tuple[Path, Document | Exception]]
        One ``(path, result)`` tuple per input path.  *result* is either
        the :class:`~document2markdown.document.Document` returned by the
        converter or the :class:`Exception` that was raised.
    """
    results: list[tuple[Path, Union[Document, Exception]]] = []
    for path in paths:
        try:
            doc = converter.convert(path)
            results.append((path, doc))
        except Exception as exc:  # noqa: BLE001
            results.append((path, exc))
    return results


def convert_directory(
    directory: Path,
    converter: "Converter",
    pattern: str = "*",
) -> "list[tuple[Path, Union[Document, Exception]]]":
    """Convert all files matching *pattern* in *directory*.

    Mirrors the source subdirectory structure inside the output directory.
    Each converted file is saved to
    ``{directory}/{OUTPUT_DIR_NAME}/{relative_parent}/``, so that
    ``docs/deeper/file.pdf`` produces
    ``docs/Exports - Conversions/deeper/file.md``.

    Parameters
    ----------
    directory:
        Directory to scan for source documents (the traversed root).
    converter:
        A :class:`~document2markdown.api.Converter` instance.
    pattern:
        Glob pattern relative to *directory* (default ``"*"`` — all files).
        Use ``"**/*"`` for recursive traversal.

    Returns
    -------
    list[tuple[Path, Document | Exception]]
        One ``(path, result)`` tuple per matched file, in filesystem order.
        Exceptions are captured rather than raised (same as
        :func:`convert_batch`).
    """
    paths = sorted(p for p in directory.glob(pattern) if p.is_file())
    results: list[tuple[Path, Union[Document, Exception]]] = []
    for source_path in paths:
        try:
            doc = converter.convert(source_path)
            # Compute mirrored output directory preserving subdirectory structure
            relative = source_path.relative_to(directory)
            output_dir = directory / OUTPUT_DIR_NAME / relative.parent
            doc.save(output=output_dir)
            results.append((source_path, doc))
        except Exception as exc:  # noqa: BLE001
            results.append((source_path, exc))
    return results
