#!/usr/bin/env python3
"""Rescore stored cloning traces with the hybrid v3 verifier."""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
from pathlib import Path
from typing import Any

from enrich_cloning_traces import apply_pr_repairs, download_sample_files
from inspect_ai.log import EvalLog, EvalSample, read_eval_log, write_eval_log
from inspect_ai.scorer import CORRECT, INCORRECT
from rescore_cloning_traces import GCS_BUCKET, corrected_reference

from lab_bench_2.cloning_simulators.features_v3 import PlannotateAnnotator
from lab_bench_2.cloning_simulators.rewards_v3 import verify_cloning_v3

VERIFIER_TASK_VERSION = "3-A"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing .eval logs")
    parser.add_argument("output_dir", type=Path, help="Directory for rescored logs")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--plannotate-executable", type=Path)
    parser.add_argument("--require-plannotate", action="store_true")
    parser.add_argument("--plannotate-full", action="store_true")
    parser.add_argument("--plannotate-cores", type=int, default=2)
    parser.add_argument("--download-missing", action="store_true")
    parser.add_argument("--suffix", default="_hybrid_v3")
    parser.add_argument("--all-cloning-references-circular", action="store_true")
    parser.add_argument("--report-csv", type=Path)
    return parser.parse_args()


def _answer(sample: EvalSample) -> str:
    score = (sample.scores or {}).get("cloning_scorer")
    if score is not None and score.answer:
        return score.answer
    return sample.output.completion


def _sync_score_event(sample: EvalSample) -> None:
    score = (sample.scores or {}).get("cloning_scorer")
    if score is None:
        return
    for event in reversed(sample.events):
        if event.event == "score" and event.scorer == "cloning_scorer":
            event.score = score.model_copy(deep=True)
            return


def _existing_directory(value: object) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_dir() else None


def _existing_file(value: object) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_file() else None


def _best_candidate_metadata(report: Any) -> tuple[float | None, bool | None]:
    if not report.candidates:
        return None, None
    best = max(report.candidates, key=lambda value: value.similarity)
    return best.similarity, best.exact_sequence_match


async def rescore_sample(
    sample: EvalSample,
    cache_dir: Path,
    reference_dir: Path,
    assume_plasmid_circular: bool,
    annotator: PlannotateAnnotator | None,
    require_plannotate: bool,
) -> tuple[bool, dict[str, Any] | None]:
    if sample.metadata.get("tag") != "cloning":
        return False, None
    score = (sample.scores or {}).get("cloning_scorer")
    if score is None:
        return False, None

    question_id = str(sample.metadata["id"])
    cache_root = cache_dir / GCS_BUCKET
    base_dir = _existing_directory(sample.metadata.get("files_path")) or (
        cache_root / "cloning" / question_id
    )
    source_reference = _existing_file(sample.metadata.get("reference_path")) or (
        cache_root / "validation" / f"{question_id}_assembled.fa"
    )
    if not base_dir.is_dir() or not source_reference.is_file():
        raise FileNotFoundError(
            f"Cannot rescore {question_id}: files={base_dir}, "
            f"reference={source_reference}"
        )

    reference_path, repaired, repair_reason = corrected_reference(
        source_reference,
        reference_dir / source_reference.name,
        sample.metadata.get("validator_params") or {},
        assume_plasmid_circular,
    )
    original_value = score.value
    original_explanation = score.explanation
    report = await verify_cloning_v3(
        answer=_answer(sample),
        base_dir=base_dir,
        reference_path=reference_path,
        validator_params=sample.metadata.get("validator_params") or {},
        require_circular=True,
        plannotate=annotator,
        require_plannotate=require_plannotate,
    )
    score.value = CORRECT if report.score >= 1.0 else INCORRECT
    score.explanation = (
        f"Hybrid verifier v3 rescoring: {report.reason}\n\n"
        f"Reference handling: {repair_reason}\n\n"
        f"Original recorded explanation: {original_explanation or 'n/a'}"
    )
    score.metadata = {
        **(score.metadata or {}),
        "cloning_score": report.score,
        "verifier_version": "v3",
        "verifier_status": report.status.value,
        "hybrid_verifier_report": report.metadata(),
        "rescored": True,
        "reused_recorded_model_answer": True,
        "reference_topology_repaired": repaired,
        "original_score_value": original_value,
        "original_score_explanation": original_explanation,
    }
    _sync_score_event(sample)
    changed = original_value != score.value
    best_similarity, exact_match = _best_candidate_metadata(report)
    row = {
        "sample_id": sample.id,
        "question_id": question_id,
        "original_score": original_value,
        "hybrid_v3_score": score.value,
        "changed": changed,
        "status": report.status.value,
        "best_similarity": best_similarity,
        "exact_sequence_match": exact_match,
        "reason": report.reason,
    }
    print(
        f"rescored {sample.id} ({question_id}): {original_value} -> {score.value}; "
        f"{report.reason}"
    )
    return changed, row


def _metric_snapshot(log: EvalLog) -> dict[str, dict[str, Any]]:
    if log.results is None:
        return {}
    return {
        score.name: {
            metric_name: metric.value for metric_name, metric in score.metrics.items()
        }
        for score in log.results.scores
    }


def _refresh_cloning_summary(log: EvalLog) -> tuple[int, int]:
    samples = [
        sample
        for sample in log.samples or []
        if sample.metadata.get("tag") == "cloning"
        and (sample.scores or {}).get("cloning_scorer") is not None
    ]
    passed = sum(
        (sample.scores or {})["cloning_scorer"].value == CORRECT for sample in samples
    )
    count = len(samples)
    accuracy = passed / count if count else 0.0
    standard_error = math.sqrt(accuracy * (1.0 - accuracy) / count) if count else 0.0
    if log.results is not None:
        for score in log.results.scores:
            if score.name != "cloning_scorer":
                continue
            score.scored_samples = count
            score.unscored_samples = 0
            if "accuracy" in score.metrics:
                score.metrics["accuracy"].value = accuracy
            if "stderr" in score.metrics:
                score.metrics["stderr"].value = standard_error
    return passed, count


def _question_ids(logs: list[EvalLog]) -> set[str]:
    return {
        str(sample.metadata["id"])
        for log in logs
        for sample in log.samples or []
        if sample.metadata.get("tag") == "cloning"
        and sample.metadata.get("id")
        and _existing_directory(sample.metadata.get("files_path")) is None
    }


def _write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_log",
        "sample_id",
        "question_id",
        "original_score",
        "hybrid_v3_score",
        "changed",
        "status",
        "best_similarity",
        "exact_sequence_match",
        "reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def rescore_logs(args: argparse.Namespace) -> None:
    source_paths = sorted(args.source_dir.glob("*.eval"))
    logs = [read_eval_log(path) for path in source_paths]
    if args.download_missing:
        download_sample_files(args.cache_dir, _question_ids(logs))
        apply_pr_repairs(args.cache_dir)

    annotator = (
        PlannotateAnnotator(
            args.plannotate_executable,
            fast=not args.plannotate_full,
            cores=args.plannotate_cores,
        )
        if args.plannotate_executable is not None
        else None
    )
    if args.require_plannotate and annotator is None:
        raise ValueError("--require-plannotate needs --plannotate-executable")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reference_dir.mkdir(parents=True, exist_ok=True)
    changes = 0
    rows: list[dict[str, Any]] = []
    for source_path, log in zip(source_paths, logs, strict=True):
        original_version = log.eval.task_version
        original_metrics = _metric_snapshot(log)
        for sample in log.samples or []:
            changed, row = await rescore_sample(
                sample,
                args.cache_dir,
                args.reference_dir,
                args.all_cloning_references_circular,
                annotator,
                args.require_plannotate,
            )
            changes += int(changed)
            if row is not None:
                rows.append({"source_log": source_path.name, **row})
        passed, count = _refresh_cloning_summary(log)
        log.eval.task_version = VERIFIER_TASK_VERSION
        log.eval.metadata = {
            **(log.eval.metadata or {}),
            "hybrid_verifier_rescore": {
                "verifier_version": "v3",
                "original_task_version": original_version,
                "original_metrics": original_metrics,
                "reused_recorded_model_answers": True,
                "requires_same_candidate_for_all_gates": True,
                "pLannotate_required": args.require_plannotate,
                "pLannotate_manifest": annotator.manifest() if annotator else None,
            },
        }
        destination = (
            args.output_dir / f"{source_path.stem}{args.suffix}{source_path.suffix}"
        )
        write_eval_log(log, destination)
        print(
            f"wrote {destination} "
            f"({passed}/{count} correct, version {VERIFIER_TASK_VERSION})"
        )
    if args.report_csv is not None:
        _write_report(args.report_csv, rows)
        print(f"wrote {args.report_csv}")
    print(f"complete: rescored {len(rows)} cloning samples; {changes} scores changed")


def main() -> None:
    asyncio.run(rescore_logs(parse_args()))


if __name__ == "__main__":
    main()
