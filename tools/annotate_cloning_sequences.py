#!/usr/bin/env python3
"""Annotate cloning files with a managed, provenance-pinned pLannotate setup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lab_bench_2.plannotate_runner import (
    DEFAULT_CACHE_DIR,
    PlannotateError,
    annotate_with_plannotate,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run pLannotate into a separate output directory. Missing conda "
            "environment and databases are installed automatically and cached."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also search Swiss-Prot and Rfam; default fast mode uses SnapGene/FPbase",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--no-auto-setup",
        action="store_true",
        help="Fail instead of creating the cached conda environment/databases",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        manifest = annotate_with_plannotate(
            args.inputs,
            args.output_dir,
            cache_dir=args.cache_dir,
            fast=not args.full,
            cores=args.cores,
            refresh=args.refresh,
            auto_setup=not args.no_auto_setup,
        )
    except (OSError, PlannotateError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = manifest["summary"]
    print(
        f"pLannotate enriched {summary['annotated_or_cached_count']}/"
        f"{summary['discovered_file_count']} file(s); "
        f"{summary['error_count']} error(s). Output: {args.output_dir}"
    )
    return 1 if summary["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
