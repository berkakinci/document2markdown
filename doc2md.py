#!/usr/bin/env python3
"""doc2md — convert documents to Markdown.

Usage:
    doc2md.py [-h] [--output OUTPUT] [--verbose] file [file ...]

Positional arguments:
    file        One or more source document paths to convert.

Optional arguments:
    --output    Target file path or directory for Markdown output.
    --verbose   Print per-file progress to stdout.

Requirements: 3.1–3.5, 4.1–4.5, 5.1–5.4
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from document2markdown.api import Converter
from document2markdown.utils import convert_batch


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CLIArgs:
    files: list[Path]
    output: Path | None
    verbose: bool


@dataclass
class BatchSummary:
    total: int
    succeeded: int
    failed: int
    errors: list[tuple[Path, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> CLIArgs:
    parser = argparse.ArgumentParser(
        prog="doc2md.py",
        description="Convert documents (PDF, DOCX, HTML, PPTX, TXT) to Markdown.",
    )
    parser.add_argument(
        "files",
        metavar="file",
        nargs="+",
        help="Source document path(s) to convert.",
    )
    parser.add_argument(
        "--output",
        metavar="OUTPUT",
        default=None,
        help="Target file path or directory for Markdown output.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print per-file progress to stdout.",
    )
    ns = parser.parse_args(argv)
    return CLIArgs(
        files=[Path(f) for f in ns.files],
        output=Path(ns.output) if ns.output else None,
        verbose=ns.verbose,
    )


# ---------------------------------------------------------------------------
# Output path resolution
# ---------------------------------------------------------------------------

def _resolve_output_dir(output: Path | None, source: Path) -> Path | None:
    """Return the output directory for *source*, or None (same dir as source).

    If ``--output`` points to an existing directory or looks like a directory
    (no suffix), use it as the output directory.  Otherwise treat it as a
    single-file output path and use its parent.
    """
    if output is None:
        return None  # writer defaults to source's parent
    if output.is_dir():
        return output
    # If output has no suffix or ends with '/', treat as directory
    if not output.suffix or str(output).endswith("/"):
        return output
    # Single-file output: use parent directory
    return output.parent


# ---------------------------------------------------------------------------
# Main batch loop
# ---------------------------------------------------------------------------

def _run(args: CLIArgs) -> BatchSummary:
    summary = BatchSummary(total=len(args.files), succeeded=0, failed=0)

    # Determine output directory (shared for all files when --output is a dir)
    output_is_dir = (
        args.output is None
        or args.output.is_dir()
        or not args.output.suffix
        or str(args.output).endswith("/")
    )

    if output_is_dir:
        shared_output_dir = args.output  # None → each file's own directory
    else:
        # Single-file output only makes sense for a single input file
        shared_output_dir = None  # handled per-file below

    converter = Converter(
        output_dir=shared_output_dir,
        verbose=args.verbose,
    )

    results = convert_batch(args.files, converter)

    for path, outcome in results:
        if isinstance(outcome, Exception):
            summary.failed += 1
            reason = str(outcome)
            summary.errors.append((path, reason))
            print(f"ERROR: {path}: {reason}", file=sys.stderr)
        else:
            # outcome is a _Document
            if args.verbose:
                print(f"Converting: {path}")

            try:
                # Determine per-file output path
                if not output_is_dir and args.output is not None:
                    # --output is a specific file path (single-file mode)
                    out_path = args.output
                    saved = outcome.save(out_path.parent)
                else:
                    saved = outcome.save()

                summary.succeeded += 1

                if args.verbose:
                    print(f"  -> {saved}")
                    for warning in outcome.warnings:
                        print(f"  WARNING: {path}: {warning}")

            except Exception as exc:  # noqa: BLE001
                summary.failed += 1
                reason = str(exc)
                summary.errors.append((path, reason))
                print(f"ERROR: {path}: {reason}", file=sys.stderr)

    return summary


def _print_summary(summary: BatchSummary) -> None:
    """Print the batch summary to stdout."""
    print(
        f"\nSummary: {summary.total} total, "
        f"{summary.succeeded} succeeded, "
        f"{summary.failed} failed"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns the exit code."""
    args = _parse_args(argv)
    summary = _run(args)
    _print_summary(summary)
    return 1 if summary.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
