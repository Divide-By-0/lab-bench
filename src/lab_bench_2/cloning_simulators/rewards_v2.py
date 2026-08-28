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


@dataclass(frozen=True)
class CandidateAssessment:
    """Verifier checks applied to one ranked top-level simulator product."""

    candidate: CandidateScore
    similarity_pass: bool
    digest_pass: bool | None

    @property
    def passes(self) -> bool:
        return self.similarity_pass and self.digest_pass is not False


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


def assess_candidates(
    candidates: list[Any],
    reference: Any,
    validator_params: dict[str, Any] | None = None,
    threshold: float = 0.95,
) -> list[CandidateAssessment]:
    """Apply the scorer's sequence and optional digest checks to every product."""
    params = validator_params or {}
    enzymes = _enzymes(params)
    digest_threshold = float(params.get("edit_distance_threshold", threshold))
    return [
        CandidateAssessment(
            candidate=candidate,
            similarity_pass=candidate.similarity >= threshold,
            digest_pass=(
                _digest_matches(
                    candidate.sequence,
                    reference,
                    enzymes,
                    digest_threshold,
                )
                if enzymes
                else None
            ),
        )
        for candidate in rank_candidates(candidates, reference)
    ]


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

    from lab_bench_2.cloning_simulators.execution import (
        normalize_quoted_file_references,
    )

    try:
        if PROTOCOL_TAG_OPEN not in answer or PROTOCOL_TAG_CLOSE not in answer:
            return 0.0, "Format invalid: no protocol tags found"
        expression = extract_between_tags(answer, PROTOCOL_TAG_OPEN, PROTOCOL_TAG_CLOSE)
        Parser(Tokenizer(expression).tokenize()).parse()
    except (SyntaxError, ValueError) as exc:
        return 0.0, f"Format invalid: {exc}"

    try:
        normalized_expression, normalized_files = normalize_quoted_file_references(
            expression, Path(base_dir)
        )
        candidates = await execute_cloning_protocol_v2(
            normalized_expression, Path(base_dir)
        )
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
    assessments = assess_candidates(candidates, reference, params, threshold)
    sequence_passing = [value for value in assessments if value.similarity_pass]
    best = assessments[0].candidate
    if not sequence_passing:
        return (
            0.0,
            "Accuracy failed: no candidate output matches reference "
            f"(best similarity: {best.similarity:.6f}, threshold: {threshold}, "
            f"candidates: {len(assessments)})",
        )

    enzymes = _enzymes(params)
    digest_threshold = float(params.get("edit_distance_threshold", threshold))
    passing = [value for value in sequence_passing if value.passes]
    if enzymes and not passing:
        return (
            0.0,
            "Digest validation failed: no globally matching candidate has "
            f"matching fragments (enzymes: {list(enzymes)}, threshold: "
            f"{digest_threshold}, candidates: {len(assessments)})",
        )

    selected = passing[0].candidate
    topology_note = (
        "; repaired missing circular reference topology" if topology_repaired else ""
    )
    syntax_note = (
        f"; accepted quoted filename references: {list(normalized_files)}"
        if normalized_files
        else ""
    )
    return (
        1.0,
        f"Cloning validation passed using candidate {selected.index + 1}/"
        f"{len(assessments)} "
        f"(similarity: {selected.similarity:.6f}{topology_note}{syntax_note})",
    )
