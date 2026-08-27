#!/usr/bin/env python3
"""Rescore stored cloning traces with the candidate-aware v2 simulators."""

from __future__ import annotations

import argparse
import asyncio
import math
from pathlib import Path
from typing import Any

from inspect_ai.log import EvalLog, EvalSample, read_eval_log, write_eval_log
from inspect_ai.scorer import CORRECT, INCORRECT
from rescore_cloning_traces import GCS_BUCKET, corrected_reference

from lab_bench_2.cloning_simulators.rewards_v2 import cloning_reward_v2

SIMULATOR_TASK_VERSION = "2-A"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing .eval logs")
    parser.add_argument("output_dir", type=Path, help="Directory for rescored logs")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--suffix", default="_simulator_v2")
    parser.add_argument("--all-cloning-references-circular", action="store_true")
    return parser.parse_args()


def _answer(sample: EvalSample) -> str:
    score = (sample.scores or {}).get("cloning_scorer")
    if score is not None and score.answer:
        return score.answer
    return sample.output.completion


def _sync_score_event(sample: EvalSample) -> None:
    """Keep Inspect's event-stream score consistent with ``sample.scores``."""
    score = (sample.scores or {}).get("cloning_scorer")
    if score is None:
        return
    for event in reversed(sample.events):
        if event.event == "score" and event.scorer == "cloning_scorer":
            event.score = score.model_copy(deep=True)
            return


async def rescore_sample(
    sample: EvalSample,
    cache_dir: Path,
    reference_dir: Path,
    assume_plasmid_circular: bool,
) -> bool:
    if sample.metadata.get("tag") != "cloning":
        return False
    score = (sample.scores or {}).get("cloning_scorer")
    if score is None:
        return False
    question_id = str(sample.metadata["id"])
    cache_root = cache_dir / GCS_BUCKET
    base_dir = cache_root / "cloning" / question_id
    source_reference = cache_root / "validation" / f"{question_id}_assembled.fa"
    reference_path, repaired, repair_reason = corrected_reference(
        source_reference,
        reference_dir / source_reference.name,
        sample.metadata.get("validator_params") or {},
        assume_plasmid_circular,
    )
    original_value = score.value
    original_explanation = score.explanation
    value, reason = await cloning_reward_v2(
        answer=_answer(sample),
        base_dir=base_dir,
        reference_path=reference_path,
        validator_params=sample.metadata.get("validator_params") or {},
    )
    score.value = CORRECT if value >= 1.0 else INCORRECT
    score.explanation = (
        f"Simulator v2 rescoring: {reason}\n\n"
        f"Reference handling: {repair_reason}\n\n"
        f"Original recorded explanation: {original_explanation or 'n/a'}"
    )
    score.metadata = {
        **(score.metadata or {}),
        "cloning_score": value,
        "simulator_version": "v2",
        "rescored": True,
        "reference_topology_repaired": repaired,
        "original_score_value": original_value,
    }
    _sync_score_event(sample)
    changed = original_value != score.value
    print(
        f"rescored {sample.id} ({question_id}): {original_value} -> {score.value}; "
        f"{reason}"
    )
    return changed


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


async def rescore_logs(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reference_dir.mkdir(parents=True, exist_ok=True)
    changes = 0
    samples = 0
    for source_path in sorted(args.source_dir.glob("*.eval")):
        log: EvalLog = read_eval_log(source_path)
        original_version = log.eval.task_version
        original_metrics = _metric_snapshot(log)
        for sample in log.samples or []:
            if sample.metadata.get("tag") == "cloning":
                samples += 1
                changes += int(
                    await rescore_sample(
                        sample,
                        args.cache_dir,
                        args.reference_dir,
                        args.all_cloning_references_circular,
                    )
                )
        passed, count = _refresh_cloning_summary(log)
        log.eval.task_version = SIMULATOR_TASK_VERSION
        log.eval.metadata = {
            **(log.eval.metadata or {}),
            "simulator_rescore": {
                "simulator_version": "v2",
                "original_task_version": original_version,
                "original_metrics": original_metrics,
                "reused_recorded_model_answers": True,
            },
        }
        destination = (
            args.output_dir / f"{source_path.stem}{args.suffix}{source_path.suffix}"
        )
        write_eval_log(log, destination)
        print(f"wrote {destination} ({passed}/{count} correct, version 2-A)")
    print(f"complete: rescored {samples} cloning samples; {changes} scores changed")


def main() -> None:
    asyncio.run(rescore_logs(parse_args()))


if __name__ == "__main__":
    main()
