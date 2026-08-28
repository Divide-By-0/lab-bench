#!/usr/bin/env python3
"""Fetch public iGEM and REBASE data for cloning-sequence enrichment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lab_bench_2.cloning_external_sources import (
    ExternalSourceError,
    fetch_cloning_external_sources,
)
from lab_bench_2.cloning_inventory import collect_feature_queries


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch versioned public feature vocabularies from iGEM and the "
            "current supplier-N restriction catalog from REBASE."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help=(
            "Optional GenBank/FASTA files or directories. GenBank features are "
            "used for specific, evidence-ranked iGEM part searches."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache/labbench2/cloning-sources",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-igem", action="store_true")
    parser.add_argument("--no-rebase", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.no_igem and args.no_rebase:
        print("error: at least one source must be enabled", file=sys.stderr)
        return 2
    try:
        feature_queries = collect_feature_queries(args.inputs) if args.inputs else []
        data = fetch_cloning_external_sources(
            args.cache_dir,
            refresh=args.refresh,
            include_rebase=not args.no_rebase,
            include_igem=not args.no_igem,
            feature_queries=feature_queries,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (ExternalSourceError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    sources = data["sources"]
    rebase = sources.get("rebase_neb")
    if rebase:
        print(
            f"REBASE {rebase['source']['release']}: "
            f"{rebase['enzyme_count']} NEB-supplied restriction enzymes"
        )
    igem = sources.get("igem_registry")
    if igem:
        summary = igem["summary"]
        print(
            f"iGEM: {summary['published_part_count']} published parts, "
            f"{summary['role_count']} roles, {summary['category_count']} categories"
        )
        if feature_queries:
            print(
                f"Specific iGEM part matches: "
                f"{summary['specific_part_match_count']}/"
                f"{summary['feature_query_count']} feature queries"
            )
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
