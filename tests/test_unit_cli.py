"""Unit tests for doc2md CLI — Task 10.3."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _make_txt(path: Path) -> None:
    path.write_text("Hello from CLI test.\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_main(argv: list[str]) -> int:
    """Import and call doc2md.main() with the given argv."""
    # Ensure the project root (where doc2md.py lives) is on sys.path
    import importlib, os
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import doc2md
    return doc2md.main(argv)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBatchSummaryCounts:
    def test_mixed_success_failure_counts(self, tmp_path, capsys):
        good1 = tmp_path / "a.txt"
        good2 = tmp_path / "b.txt"
        _make_txt(good1)
        _make_txt(good2)
        bad = tmp_path / "nonexistent.txt"

        out_dir = tmp_path / "out"
        out_dir.mkdir()

        rc = _run_main([str(good1), str(good2), str(bad), "--output", str(out_dir)])

        captured = capsys.readouterr()
        assert "3 total" in captured.out
        assert "2 succeeded" in captured.out
        assert "1 failed" in captured.out
        assert rc != 0  # failures → non-zero exit


class TestNonExistentFile:
    def test_nonexistent_logged_as_failure(self, tmp_path, capsys):
        good = tmp_path / "good.txt"
        _make_txt(good)
        bad = tmp_path / "missing.txt"
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        rc = _run_main([str(good), str(bad), "--output", str(out_dir)])

        captured = capsys.readouterr()
        # Error should appear on stderr
        assert "missing.txt" in captured.err or "missing" in captured.err.lower()
        # Good file should still be processed
        assert "1 succeeded" in captured.out
        assert "1 failed" in captured.out

    def test_remaining_files_processed_after_failure(self, tmp_path, capsys):
        bad = tmp_path / "missing.txt"
        good = tmp_path / "good.txt"
        _make_txt(good)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        _run_main([str(bad), str(good), "--output", str(out_dir)])
        # The good file should have been converted
        assert (out_dir / "good.md").exists()


class TestVerboseFlag:
    def test_verbose_prints_progress(self, tmp_path, capsys):
        f = tmp_path / "sample.txt"
        _make_txt(f)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        _run_main([str(f), "--output", str(out_dir), "--verbose"])

        captured = capsys.readouterr()
        # Verbose mode should print something about the file being converted
        assert "sample.txt" in captured.out or "Converting" in captured.out
