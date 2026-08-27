"""Candidate-aware cloning verifier for simulator v2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab_bench_2.cloning_simulators.execution import execute_cloning_protocol_v2


@dataclass(frozen=True)
class CandidateScore:
    index: int
    similarity: float
    sequence: Any


def _enzymes(validator_params: dict[str, Any]) -> tuple[str, ...]:
    enzymes: list[str] = []
    index = 1
    while value := validator_params.get(f"enzyme_{index}"):
        enzymes.append(str(value))
        index += 1
    return tuple(enzymes)


def _digest(sequence: Any, enzymes: tuple[str, ...]) -> list[Any]:
    from labbench2.cloning.enzyme_cut import enzyme_cut

    fragments = [sequence]
    for enzyme in enzymes:
        fragments = [
            output for fragment in fragments for output in enzyme_cut(fragment, enzyme)
        ]
    return fragments


def _digest_lengths(sequence: Any, enzymes: tuple[str, ...]) -> tuple[int, ...]:
    return tuple(
        sorted(len(fragment.sequence) for fragment in _digest(sequence, enzymes))
    )


def repair_reference_topology(
    reference: Any, validator_params: dict[str, Any]
) -> tuple[Any, bool]:
    """Repair missing circular topology only when digest metadata proves it."""
    enzymes = _enzymes(validator_params)
    expected = tuple(
        sorted(int(value) for value in validator_params.get("fragments", ()))
    )
    if reference.is_circular or not enzymes or not expected:
        return reference, False
    circular = reference.model_copy(update={"is_circular": True})
    if (
        _digest_lengths(reference, enzymes) != expected
        and _digest_lengths(circular, enzymes) == expected
    ):
        return circular, True
    return reference, False


def rank_candidates(candidates: list[Any], reference: Any) -> list[CandidateScore]:
    """Rank every top-level product by similarity to the hidden reference."""
    from lab_bench_2.cloning_simulators.sequence_similarity_v2 import (
        sequence_similarity_v2,
    )

    return sorted(
        (
            CandidateScore(
                index, sequence_similarity_v2(candidate, reference), candidate
            )
            for index, candidate in enumerate(candidates)
        ),
        key=lambda value: value.similarity,
        reverse=True,
    )


def _digest_matches(
    candidate: Any,
    reference: Any,
    enzymes: tuple[str, ...],
    threshold: float,
) -> bool:
    from labbench2.cloning.sequence_alignment import sequence_similarity

    output_fragments = sorted(
        _digest(candidate, enzymes), key=lambda value: len(value.sequence)
    )
    reference_fragments = sorted(
        _digest(reference, enzymes), key=lambda value: len(value.sequence)
    )
    return len(output_fragments) == len(reference_fragments) and all(
        sequence_similarity(output, expected) >= threshold
        for output, expected in zip(output_fragments, reference_fragments, strict=True)
    )


async def cloning_reward_v2(
    answer: str,
    base_dir: Path | str,
    reference_path: Path | str | None = None,
    threshold: float = 0.95,
    validator_params: dict[str, Any] | None = None,
) -> tuple[float, str]:
    """Validate every top-level simulator product and accept any passing candidate."""
    from labbench2.cloning.cloning_protocol import (
        PROTOCOL_TAG_CLOSE,
        PROTOCOL_TAG_OPEN,
        Parser,
        Tokenizer,
    )
    from labbench2.cloning.sequence_models import BioSequence
    from labbench2.cloning.utils import extract_between_tags

    try:
        if PROTOCOL_TAG_OPEN not in answer or PROTOCOL_TAG_CLOSE not in answer:
            return 0.0, "Format invalid: no protocol tags found"
        expression = extract_between_tags(answer, PROTOCOL_TAG_OPEN, PROTOCOL_TAG_CLOSE)
        Parser(Tokenizer(expression).tokenize()).parse()
    except (SyntaxError, ValueError) as exc:
        return 0.0, f"Format invalid: {exc}"

    try:
        candidates = await execute_cloning_protocol_v2(expression, Path(base_dir))
        if not candidates:
            return 0.0, "Execution failed: protocol did not produce output"
    except Exception as exc:
        return 0.0, f"Execution failed: protocol did not produce output. Details: {exc}"

    if reference_path is None:
        return 1.0, f"Cloning validation passed ({len(candidates)} candidate products)"
    try:
        reference = BioSequence.from_file(Path(reference_path))
    except Exception as exc:
        return 0.0, f"Reference file error: {exc}"

    params = validator_params or {}
    reference, topology_repaired = repair_reference_topology(reference, params)
    ranked = rank_candidates(candidates, reference)
    passing = [candidate for candidate in ranked if candidate.similarity >= threshold]
    best = ranked[0]
    if not passing:
        return (
            0.0,
            "Accuracy failed: no candidate output matches reference "
            f"(best similarity: {best.similarity:.6f}, threshold: {threshold}, "
            f"candidates: {len(ranked)})",
        )

    enzymes = _enzymes(params)
    digest_threshold = float(params.get("edit_distance_threshold", threshold))
    if enzymes:
        passing = [
            candidate
            for candidate in passing
            if _digest_matches(candidate.sequence, reference, enzymes, digest_threshold)
        ]
        if not passing:
            return (
                0.0,
                "Digest validation failed: no globally matching candidate has "
                f"matching fragments (enzymes: {list(enzymes)}, threshold: "
                f"{digest_threshold}, candidates: {len(ranked)})",
            )

    selected = passing[0]
    topology_note = (
        "; repaired missing circular reference topology" if topology_repaired else ""
    )
    return (
        1.0,
        f"Cloning validation passed using candidate {selected.index + 1}/{len(ranked)} "
        f"(similarity: {selected.similarity:.6f}{topology_note})",
    )
