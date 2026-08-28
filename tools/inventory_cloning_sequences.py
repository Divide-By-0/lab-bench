#!/usr/bin/env python3
"""Generate JSON indexes for cloning GenBank and FASTA attachments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lab_bench_2.cloning_inventory import build_cloning_inventory


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory sequence files, GenBank features/primers, duplicates, and "
            "New England Biolabs restriction-enzyme sites."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument(
        "--root", type=Path, help="Root used to make paths in the JSON relative"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--no-enzymes",
        action="store_true",
        help="Skip the Biopython supplier-N enzyme catalog and site index",
    )
    parser.add_argument(
        "--external-sources",
        type=Path,
        help=(
            "JSON created by fetch_cloning_source_data.py; adds provenance-marked "
            "specific iGEM parts, descriptions, roles, and label-vocabulary "
            "candidates without replacing source annotations"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        external_sources = (
            json.loads(args.external_sources.read_text(encoding="utf-8"))
            if args.external_sources
            else None
        )
        inventory = build_cloning_inventory(
            args.inputs,
            root=args.root,
            include_enzymes=not args.no_enzymes,
            external_sources=external_sources,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary = inventory["summary"]
    print(
        f"Inventoried {summary['parsed_file_count']}/"
        f"{summary['discovered_file_count']} sequence files; "
        f"{summary['parse_error_count']} parse error(s). Output: {args.output}"
    )
    print(
        f"No part features: "
        f"{len(summary['files_with_no_part_features'])}; "
        f"no primers: {len(summary['files_with_no_primers'])}"
    )
    return 1 if summary["parse_error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
