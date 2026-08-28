#!/usr/bin/env python3
"""Rescore cloning traces after evidence-based circular-reference repair."""

from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path
from typing import Any

from inspect_ai.log import EvalLog, EvalSample, read_eval_log, write_eval_log
from inspect_ai.scorer import CORRECT, INCORRECT
from labbench2.cloning.enzyme_cut import enzyme_cut
from labbench2.cloning.rewards import cloning_digest_reward
from labbench2.cloning.sequence_models import BioSequence

GCS_BUCKET = "labbench2-data-public"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing .eval logs")
    parser.add_argument("output_dir", type=Path, help="Directory for rescored logs")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        required=True,
        help="Cache containing labbench2-data-public/cloning and validation",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        required=True,
        help="Directory for corrected reference FASTA copies",
    )
    parser.add_argument(
        "--suffix",
        default="_rescored",
        help="Suffix added to copied log filenames (default: _rescored)",
    )
    parser.add_argument(
        "--all-cloning-references-circular",
        action="store_true",
        help=(
            "Mark every cloning reference circular when the corpus is known to "
            "contain final plasmid/vector assemblies"
        ),
    )
    return parser.parse_args()


def _enzymes(validator_params: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    index = 1
    while value := validator_params.get(f"enzyme_{index}"):
        values.append(str(value))
        index += 1
    return tuple(values)


def _digest_lengths(sequence: BioSequence, enzymes: tuple[str, ...]) -> tuple[int, ...]:
    fragments = [sequence]
    for enzyme in enzymes:
        fragments = [
            output for fragment in fragments for output in enzyme_cut(fragment, enzyme)
        ]
    return tuple(sorted(len(fragment.sequence) for fragment in fragments))


def corrected_reference(
    source: Path,
    destination: Path,
    validator_params: dict[str, Any],
    assume_plasmid_circular: bool = False,
) -> tuple[Path, bool, str]:
    """Copy a reference, marking it circular only when digest metadata proves it."""
    reference = BioSequence.from_file(source)
    enzymes = _enzymes(validator_params)
    expected = tuple(
        sorted(int(value) for value in validator_params.get("fragments", []))
    )
    loaded_lengths = _digest_lengths(reference, enzymes) if enzymes else ()
    circular = reference.model_copy(update={"is_circular": True})
    circular_lengths = _digest_lengths(circular, enzymes) if enzymes else ()
    digest_evidence = bool(
        not reference.is_circular
        and enzymes
        and expected
        and loaded_lengths != expected
        and circular_lengths == expected
    )
    repair = bool(
        not reference.is_circular and (digest_evidence or assume_plasmid_circular)
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if repair:
        destination.write_text(circular.to_fasta(), encoding="utf-8")
        reason = (
            "reference FASTA lacked circular topology; dataset fragment metadata "
            f"matches circular digest {list(circular_lengths)}"
            if digest_evidence
            else "reference FASTA marked circular under cloning-plasmid corpus policy"
        )
    else:
        shutil.copy2(source, destination)
        reason = "no evidence-based topology repair required"
    return destination, repair, reason


def _answer(sample: EvalSample) -> str:
    score = (sample.scores or {}).get("cloning_scorer")
    if score is not None and score.answer:
        return score.answer
    return sample.output.completion


async def rescore_sample(
    sample: EvalSample,
    cache_dir: Path,
    reference_dir: Path,
    assume_plasmid_circular: bool,
) -> tuple[bool, bool]:
    if sample.metadata.get("tag") != "cloning":
        return False, False
    question_id = str(sample.metadata["id"])
    cache_root = cache_dir / GCS_BUCKET
    base_dir = cache_root / "cloning" / question_id
    source_reference = cache_root / "validation" / f"{question_id}_assembled.fa"
    repaired_reference, repaired, repair_reason = corrected_reference(
        source_reference,
        reference_dir / source_reference.name,
        sample.metadata.get("validator_params") or {},
        assume_plasmid_circular,
    )
    score = (sample.scores or {}).get("cloning_scorer")
    if score is None:
        return repaired, False
    original_value = score.value
    original_explanation = score.explanation
    if not repaired:
        return False, False

    validator_params = sample.metadata.get("validator_params") or {}
    enzymes = list(_enzymes(validator_params))
    if not enzymes:
        score.explanation = (
            f"Reference handling: {repair_reason}. This does not alter the recorded "
            "score because this sample has no digest validator.\n\n"
            f"Original recorded explanation: {original_explanation or 'n/a'}"
        )
        score.metadata = {
            **(score.metadata or {}),
            "rescored": True,
            "reference_topology_repaired": True,
            "original_score_value": original_value,
        }
        return True, False
    reference = BioSequence.from_file(repaired_reference)
    digest_score = await cloning_digest_reward(
        text=_answer(sample),
        reference=reference,
        base_dir=base_dir,
        enzymes=enzymes,
        threshold=float(validator_params.get("edit_distance_threshold", 0.95)),
    )
    passed_prior_stages = bool(
        original_explanation
        and original_explanation.startswith("Digest validation failed")
    )
    score_value = 1.0 if passed_prior_stages and digest_score >= 1.0 else 0.0
    score.value = CORRECT if score_value >= 1.0 else INCORRECT
    explanation = (
        "Digest validation passed after circular-reference repair"
        if digest_score >= 1.0
        else "Digest validation still failed after circular-reference repair"
    )
    score.explanation = (
        f"Rescored result: {explanation}\n\n"
        "Format, execution, and global-similarity stages were reused from the "
        "original evaluation because the original digest-failure explanation proves "
        "they passed.\n\n"
        f"Reference handling: {repair_reason}\n\n"
        f"Original recorded explanation: {original_explanation or 'n/a'}"
    )
    score.metadata = {
        **(score.metadata or {}),
        "cloning_score": score_value,
        "rescored_digest_score": digest_score,
        "rescored": True,
        "reference_topology_repaired": repaired,
        "original_score_value": original_value,
    }
    changed = original_value != score.value
    print(
        f"rescored {sample.id} ({question_id}): {original_value} -> {score.value}; "
        f"topology_repaired={repaired}"
    )
    return repaired, changed


async def rescore_logs(
    source_dir: Path,
    output_dir: Path,
    cache_dir: Path,
    reference_dir: Path,
    suffix: str,
    assume_plasmid_circular: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    repaired_samples = 0
    changed_scores = 0
    for source_path in sorted(source_dir.glob("*.eval")):
        log: EvalLog = read_eval_log(source_path)
        for sample in log.samples or []:
            repaired, changed = await rescore_sample(
                sample,
                cache_dir,
                reference_dir,
                assume_plasmid_circular,
            )
            repaired_samples += int(repaired)
            changed_scores += int(changed)
        destination = output_dir / f"{source_path.stem}{suffix}{source_path.suffix}"
        write_eval_log(log, destination)
        print(f"wrote {destination}")
    print(
        f"complete: {repaired_samples} sample evaluations used corrected circular "
        f"references; {changed_scores} recorded scores changed"
    )


def main() -> None:
    args = parse_args()
    asyncio.run(
        rescore_logs(
            args.source_dir,
            args.output_dir,
            args.cache_dir,
            args.reference_dir,
            args.suffix,
            args.all_cloning_references_circular,
        )
    )


if __name__ == "__main__":
    main()
