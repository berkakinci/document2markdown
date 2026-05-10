"""Property-based tests for batch conversion.

# Feature: document-to-markdown, Property 7: Batch mode processes all files independently
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from document2markdown.api import Converter
from document2markdown.document import Document
from document2markdown.utils import convert_batch

# ---------------------------------------------------------------------------
# Property 7: Batch mode processes all files independently
# ---------------------------------------------------------------------------

# Feature: document-to-markdown, Property 7: Batch mode processes all files independently
@given(
    good_count=st.integers(min_value=1, max_value=10),
    bad_count=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_property7_batch_processes_all_files_independently(
    good_count: int, bad_count: int
) -> None:
    """convert_batch returns exactly N results and succeeded + failed == N."""
    total = good_count + bad_count

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        paths: list[Path] = []

        # Create good_count real .txt files
        for i in range(good_count):
            p = tmp / f"good_{i}.txt"
            p.write_text(f"Content of file {i}.", encoding="utf-8")
            paths.append(p)

        # Add bad_count nonexistent paths
        for i in range(bad_count):
            p = tmp / f"nonexistent_{i}.txt"
            # Intentionally do NOT create this file
            paths.append(p)

        converter = Converter()
        results = convert_batch(paths, converter)

        # Must return exactly N results
        assert len(results) == total, (
            f"Expected {total} results, got {len(results)}"
        )

        succeeded = sum(1 for _, r in results if isinstance(r, Document))
        failed = sum(1 for _, r in results if isinstance(r, Exception))

        # succeeded + failed must equal total
        assert succeeded + failed == total, (
            f"succeeded ({succeeded}) + failed ({failed}) != total ({total})"
        )

        # All good files should have succeeded
        assert succeeded == good_count, (
            f"Expected {good_count} successes, got {succeeded}"
        )

        # All bad files should have failed
        assert failed == bad_count, (
            f"Expected {bad_count} failures, got {failed}"
        )
