#!/usr/bin/env python3
"""Download the curated Addgene subset and write a cloning inventory."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from lab_bench_2.addgene_downloader import AddgeneDownloadError
from lab_bench_2.addgene_inventory_subset import (
    annotate_inventory_with_subset,
    subset_gbk_dir,
    subset_plasmids,
)
from lab_bench_2.addgene_web_downloader import AddgeneWebDownloader
from lab_bench_2.cloning_inventory import build_cloning_inventory

DEFAULT_GBK_DIR = subset_gbk_dir()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download the curated Addgene full-sequence subset and inventory "
            "features, primers, and same-plasmid map conflicts."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_GBK_DIR,
        help=f"Directory for GBK files (default: {DEFAULT_GBK_DIR})",
    )
    parser.add_argument(
        "--inventory-out",
        type=Path,
        help="Write the combined catalog+inventory JSON here",
    )
    parser.add_argument(
        "--catalog-out",
        type=Path,
        help="Write the catalog JSON (no sequences) here",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--no-enzymes", action="store_true")
    parser.add_argument(
        "--via",
        choices=("chrome-session",),
        default="chrome-session",
        help="Only chrome-session is supported for this subset builder",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    catalog = subset_plasmids()
    if args.catalog_out:
        args.catalog_out.parent.mkdir(parents=True, exist_ok=True)
        from lab_bench_2.addgene_inventory_subset import catalog_records

        args.catalog_out.write_text(
            json.dumps(catalog_records(catalog), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote catalog ({len(catalog)} plasmids) to {args.catalog_out}")

    downloader = AddgeneWebDownloader(
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )
    download_records = []
    errors = []
    for entry in catalog:
        try:
            records = downloader.download_plasmid(
                entry.plasmid_id,
                args.output_dir,
                sequence_source=entry.sequence_source,
                refresh=args.refresh,
            )
        except AddgeneDownloadError as exc:
            errors.append({"plasmid_id": entry.plasmid_id, "error": str(exc)})
            print(f"error {entry.plasmid_id}: {exc}", file=sys.stderr)
            continue
        for record in records:
            payload = asdict(record)
            payload["catalog_name"] = entry.name
            payload["catalog_role"] = entry.role
            download_records.append(payload)
            print(
                f"{entry.plasmid_id} {record.status} "
                f"{record.filename} features={record.feature_count} "
                f"len={record.length} bucket={record.source_bucket}"
            )

    if not download_records:
        print("error: no GBK files downloaded", file=sys.stderr)
        return 2

    inventory = build_cloning_inventory(
        [args.output_dir],
        root=args.output_dir,
        include_enzymes=not args.no_enzymes,
    )
    combined = annotate_inventory_with_subset(inventory, download_records, catalog)
    combined["download_errors"] = errors

    if args.inventory_out:
        args.inventory_out.parent.mkdir(parents=True, exist_ok=True)
        args.inventory_out.write_text(
            json.dumps(combined, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote inventory to {args.inventory_out}")

    summary = inventory["summary"]
    gotchas = combined["gotcha_index"]
    print(
        f"Inventoried {summary['parsed_file_count']}/"
        f"{summary['discovered_file_count']} files; "
        f"{len(errors)} download error(s)."
    )
    print(
        f"Conflicting full maps: {len(gotchas['conflicting_full_maps'])}; "
        f"identical extra maps: {len(gotchas['identical_full_maps'])}; "
        f"no primers: {len(gotchas['files_with_no_primers'])}"
    )
    return 1 if errors or summary["parse_error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
