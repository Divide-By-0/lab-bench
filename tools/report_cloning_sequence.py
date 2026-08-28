#!/usr/bin/env python3
"""Build a complete provenance-separated report for one plasmid file."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lab_bench_2.cloning_external_sources import (
    ExternalSourceError,
    fetch_cloning_external_sources,
)
from lab_bench_2.cloning_inventory import (
    SEQUENCE_FORMATS,
    build_cloning_inventory,
    collect_feature_queries,
)
from lab_bench_2.cloning_report import CloningReportError, write_cloning_report
from lab_bench_2.plannotate_runner import (
    DEFAULT_CACHE_DIR,
    PlannotateError,
    annotate_with_plannotate,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Turn one GenBank/FASTA plasmid into inventory JSON, cached public "
            "iGEM/REBASE evidence, optional pLannotate outputs, and a standalone "
            "color-coded HTML report."
        )
    )
    parser.add_argument("input", type=Path, help="One single-record plasmid file")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source-cache-dir",
        type=Path,
        default=Path.home() / ".cache/labbench2/cloning-sources",
    )
    parser.add_argument("--plannotate-cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--full-plannotate", action="store_true")
    parser.add_argument("--skip-plannotate", action="store_true")
    parser.add_argument("--skip-igem", action="store_true")
    parser.add_argument("--skip-rebase", action="store_true")
    parser.add_argument(
        "--no-auto-setup",
        action="store_true",
        help="Fail instead of automatically installing pLannotate and its databases",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    source = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    try:
        _validate_source(source)
        if args.cores < 1:
            raise ValueError("cores must be positive")
        output_dir.mkdir(parents=True, exist_ok=True)
        external_sources = fetch_cloning_external_sources(
            args.source_cache_dir,
            refresh=args.refresh,
            include_rebase=not args.skip_rebase,
            include_igem=not args.skip_igem,
            feature_queries=(
                collect_feature_queries([source]) if not args.skip_igem else []
            ),
        )
        external_path = output_dir / "external-sources.json"
        _write_json(external_path, external_sources)
        inventory = build_cloning_inventory(
            [source],
            root=source.parent,
            external_sources=external_sources,
        )
        inventory_path = output_dir / "inventory.json"
        _write_json(inventory_path, inventory)

        plannotate_manifest: dict[str, Any] | None = None
        plannotate_dir: Path | None = None
        if not args.skip_plannotate:
            plannotate_dir = output_dir / "plannotate"
            plannotate_manifest = annotate_with_plannotate(
                [source],
                plannotate_dir,
                cache_dir=args.plannotate_cache_dir,
                fast=not args.full_plannotate,
                cores=args.cores,
                refresh=args.refresh,
                auto_setup=not args.no_auto_setup,
            )

        report_path = output_dir / "report.html"
        write_cloning_report(
            report_path,
            source,
            inventory,
            external_sources,
            plannotate_manifest=plannotate_manifest,
            plannotate_output_dir=plannotate_dir,
        )
        pipeline_manifest = _pipeline_manifest(
            source,
            output_dir,
            inventory_path,
            external_path,
            report_path,
            plannotate_manifest,
        )
        _write_json(output_dir / "report-manifest.json", pipeline_manifest)
    except (
        CloningReportError,
        ExternalSourceError,
        OSError,
        PlannotateError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary = inventory["summary"]
    plannotate_errors = (
        int(plannotate_manifest["summary"]["error_count"])
        if plannotate_manifest is not None
        else 0
    )
    print(
        f"Reported {summary['parsed_file_count']}/1 plasmid file; "
        f"{plannotate_errors} pLannotate error(s). Report: {report_path}"
    )
    return 1 if plannotate_errors else 0


def _validate_source(source: Path) -> None:
    if not source.is_file():
        raise ValueError(f"Input is not a file: {source}")
    if source.suffix.casefold() not in SEQUENCE_FORMATS:
        supported = ", ".join(sorted(SEQUENCE_FORMATS))
        raise ValueError(f"Unsupported input suffix; expected one of: {supported}")


def _pipeline_manifest(
    source: Path,
    output_dir: Path,
    inventory_path: Path,
    external_path: Path,
    report_path: Path,
    plannotate_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    artifacts = {
        "inventory": _artifact(output_dir, inventory_path),
        "external_sources": _artifact(output_dir, external_path),
        "report": _artifact(output_dir, report_path),
    }
    if plannotate_manifest is not None:
        plannotate_manifest_path = output_dir / "plannotate/plannotate-manifest.json"
        artifacts["plannotate_manifest"] = _artifact(
            output_dir, plannotate_manifest_path
        )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "path": str(source),
            "sha256": _sha256_file(source),
        },
        "artifacts": artifacts,
        "provenance_policy": {
            "source_file_modified": False,
            "source_annotations_are_ground_truth": True,
            "functional_summaries_are_rule_derived": True,
            "external_matches_remain_separate": True,
        },
    }


def _artifact(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)),
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
