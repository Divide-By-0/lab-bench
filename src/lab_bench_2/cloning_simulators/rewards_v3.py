"""Hybrid physical and feature-architecture verifier for cloning tasks."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from lab_bench_2.cloning_simulators.execution import execute_cloning_protocol_v2
from lab_bench_2.cloning_simulators.features_v3 import (
    FeatureAnnotationError,
    FeatureArchitectureAssessment,
    PlannotateAnnotator,
    RepeatAssessment,
    compare_repeat_burden,
    plannotate_assessments,
    source_feature_assessment,
)
from lab_bench_2.cloning_simulators.rewards_v2 import (
    CandidateAssessment,
    assess_candidates,
    repair_reference_topology,
)


class VerificationStatus(str, Enum):
    """Top-level verifier outcome."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "verifier_error"


@dataclass(frozen=True)
class HybridCandidateAssessment:
    """Every hard gate applied to one physical simulator product."""

    simulator_index: int
    similarity: float
    similarity_pass: bool
    exact_sequence_match: bool
    topology_pass: bool
    digest_pass: bool | None
    repeat_integrity: RepeatAssessment | None
    source_features: FeatureArchitectureAssessment | None
    plannotate_features: FeatureArchitectureAssessment | None

    @property
    def passes(self) -> bool:
        """Require every configured gate to pass on this same candidate."""
        return bool(
            self.similarity_pass
            and self.topology_pass
            and self.digest_pass is not False
            and (self.repeat_integrity is None or self.repeat_integrity.passes)
            and (self.source_features is None or self.source_features.passes)
            and (self.plannotate_features is None or self.plannotate_features.passes)
        )


@dataclass(frozen=True)
class HybridVerificationReport:
    """Structured pass/fail/error result for one submitted cloning protocol."""

    status: VerificationStatus
    reason: str
    candidates: tuple[HybridCandidateAssessment, ...] = ()
    normalized_files: tuple[str, ...] = ()
    topology_repaired: bool = False
    plannotate_manifest: dict[str, Any] | None = None

    @property
    def score(self) -> float:
        """Return the benchmark-compatible binary score."""
        return 1.0 if self.status is VerificationStatus.PASS else 0.0

    def metadata(self) -> dict[str, Any]:
        """Return JSON-compatible audit metadata."""
        return {
            "status": self.status.value,
            "reason": self.reason,
            "candidates": [
                {
                    **asdict(candidate),
                    "passes": candidate.passes,
                }
                for candidate in self.candidates
            ],
            "normalized_files": list(self.normalized_files),
            "topology_repaired": self.topology_repaired,
            "plannotate_manifest": self.plannotate_manifest,
        }


def _candidate_report(
    assessment: CandidateAssessment,
    *,
    require_circular: bool,
    source_features: FeatureArchitectureAssessment | None = None,
    plannotate_features: FeatureArchitectureAssessment | None = None,
    repeat_integrity: RepeatAssessment | None = None,
) -> HybridCandidateAssessment:
    report = HybridCandidateAssessment(
        simulator_index=assessment.candidate.index,
        similarity=assessment.candidate.similarity,
        similarity_pass=assessment.similarity_pass,
        exact_sequence_match=assessment.candidate.similarity == 1.0,
        topology_pass=(
            bool(assessment.candidate.sequence.is_circular)
            if require_circular
            else True
        ),
        digest_pass=assessment.digest_pass,
        repeat_integrity=repeat_integrity,
        source_features=source_features,
        plannotate_features=plannotate_features,
    )
    return report


def _failure_reason(
    candidates: tuple[HybridCandidateAssessment, ...], threshold: float
) -> str:
    if not candidates:
        return "Execution failed: protocol did not produce output"
    if not any(value.similarity_pass for value in candidates):
        best = max(candidates, key=lambda value: value.similarity)
        return (
            "Sequence gate failed: no candidate reached the required similarity "
            f"threshold (best {best.similarity:.6f}; required {threshold:.6f}). "
            "Topology, digest, repeat, and feature gates were not evaluated for "
            "that candidate."
        )
    eligible = [value for value in candidates if value.similarity_pass]
    if not any(value.topology_pass for value in eligible):
        return (
            "Topology gate failed: every candidate that passed the sequence gate "
            "is linear, but the expected final construct is circular."
        )
    digest_eligible = [value for value in eligible if value.topology_pass]
    if digest_eligible and all(value.digest_pass is False for value in digest_eligible):
        return (
            "Digest gate failed: no sequence-matching circular candidate has the "
            "expected unordered restriction-fragment lengths."
        )
    feature_failures: list[str] = []
    for candidate in digest_eligible:
        if candidate.digest_pass is False:
            continue
        if (
            candidate.repeat_integrity is not None
            and not candidate.repeat_integrity.passes
        ):
            feature_failures.append(
                f"candidate {candidate.simulator_index + 1}: "
                f"{candidate.repeat_integrity.summary}"
            )
        for result in (candidate.source_features, candidate.plannotate_features):
            if result is not None and not result.passes:
                feature_failures.append(
                    f"candidate {candidate.simulator_index + 1}: {result.summary}"
                )
    if feature_failures:
        return (
            "Structural gate failed after the sequence and topology gates passed "
            "(the digest gate either passed or was not configured): "
            + " | ".join(feature_failures)
        )
    return "Cloning validation failed: no single candidate passed every gate"


async def verify_cloning_v3(
    answer: str,
    base_dir: Path | str,
    reference_path: Path | str | None = None,
    threshold: float = 0.95,
    validator_params: dict[str, Any] | None = None,
    *,
    require_circular: bool = True,
    plannotate: PlannotateAnnotator | None = None,
    require_plannotate: bool = False,
) -> HybridVerificationReport:
    """Run physical, reference, topology, and feature-architecture gates."""
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
            return HybridVerificationReport(
                VerificationStatus.FAIL, "Format invalid: no protocol tags found"
            )
        expression = extract_between_tags(answer, PROTOCOL_TAG_OPEN, PROTOCOL_TAG_CLOSE)
        Parser(Tokenizer(expression).tokenize()).parse()
    except (SyntaxError, ValueError) as exc:
        return HybridVerificationReport(
            VerificationStatus.FAIL, f"Format invalid: {exc}"
        )

    base_path = Path(base_dir)
    try:
        normalized_expression, normalized_files = normalize_quoted_file_references(
            expression, base_path
        )
        products = await execute_cloning_protocol_v2(normalized_expression, base_path)
        if not products:
            return HybridVerificationReport(
                VerificationStatus.FAIL,
                "Execution failed: protocol did not produce output",
                normalized_files=normalized_files,
            )
    except Exception as exc:
        return HybridVerificationReport(
            VerificationStatus.FAIL,
            f"Execution failed: protocol did not produce output. Details: {exc}",
        )

    if reference_path is None:
        circular = [value for value in products if value.is_circular]
        status = (
            VerificationStatus.PASS
            if circular or not require_circular
            else VerificationStatus.FAIL
        )
        reason = (
            f"Execution-only validation produced {len(products)} products"
            if status is VerificationStatus.PASS
            else "Topology failed: protocol produced no circular plasmid"
        )
        return HybridVerificationReport(
            status, reason, normalized_files=normalized_files
        )

    try:
        reference = BioSequence.from_file(Path(reference_path))
    except Exception as exc:
        return HybridVerificationReport(
            VerificationStatus.ERROR, f"Reference file error: {exc}"
        )

    params = validator_params or {}
    reference, topology_repaired = repair_reference_topology(reference, params)
    ranked = assess_candidates(products, reference, params, threshold)
    preliminary = tuple(
        _candidate_report(value, require_circular=require_circular) for value in ranked
    )
    eligible_indices = [
        index
        for index, value in enumerate(preliminary)
        if value.similarity_pass
        and value.topology_pass
        and value.digest_pass is not False
    ]

    source_results: dict[int, FeatureArchitectureAssessment] = {}
    repeat_results: dict[int, RepeatAssessment] = {}
    for index in eligible_indices:
        repeat_results[index] = compare_repeat_burden(
            ranked[index].candidate.sequence, reference
        )
        source_results[index] = source_feature_assessment(
            ranked[index].candidate.sequence, reference, base_path
        )

    plannotate_results: dict[int, FeatureArchitectureAssessment] = {}
    manifest: dict[str, Any] | None = None
    if require_plannotate and plannotate is None:
        return HybridVerificationReport(
            VerificationStatus.ERROR,
            "Verifier error: pLannotate was required but no executable was configured",
            candidates=preliminary,
            normalized_files=normalized_files,
            topology_repaired=topology_repaired,
        )
    if plannotate is not None and eligible_indices:
        try:
            eligible_products = [
                ranked[index].candidate.sequence for index in eligible_indices
            ]
            assessments = await asyncio.to_thread(
                plannotate_assessments,
                eligible_products,
                reference,
                plannotate,
            )
            plannotate_results.update(zip(eligible_indices, assessments, strict=True))
            manifest = await asyncio.to_thread(plannotate.manifest)
        except FeatureAnnotationError as exc:
            if require_plannotate:
                return HybridVerificationReport(
                    VerificationStatus.ERROR,
                    f"Verifier error: {exc}",
                    candidates=preliminary,
                    normalized_files=normalized_files,
                    topology_repaired=topology_repaired,
                )

    candidates = tuple(
        _candidate_report(
            assessment,
            require_circular=require_circular,
            repeat_integrity=repeat_results.get(index),
            source_features=source_results.get(index),
            plannotate_features=plannotate_results.get(index),
        )
        for index, assessment in enumerate(ranked)
    )
    passing = [value for value in candidates if value.passes]
    if passing:
        selected = passing[0]
        evidence = [
            selected.repeat_integrity.summary
            if selected.repeat_integrity is not None
            else "repeat gate unavailable"
        ]
        evidence.extend(
            result.summary
            for result in (selected.source_features, selected.plannotate_features)
            if result is not None
        )
        sequence_note = (
            "exact circular/reverse-complement sequence match"
            if selected.exact_sequence_match
            else f"similarity gate passed at threshold {threshold:.6f}"
        )
        digest_note = (
            "digest gate passed"
            if selected.digest_pass is True
            else "digest gate not configured"
        )
        reason = (
            f"Hybrid verifier passed candidate "
            f"{selected.simulator_index + 1}/{len(candidates)}: "
            f"sequence similarity {selected.similarity:.6f} ({sequence_note}); "
            f"circular topology gate passed; {digest_note}; "
            + "; ".join(evidence)
            + "."
        )
        return HybridVerificationReport(
            VerificationStatus.PASS,
            reason,
            candidates=candidates,
            normalized_files=normalized_files,
            topology_repaired=topology_repaired,
            plannotate_manifest=manifest,
        )
    return HybridVerificationReport(
        VerificationStatus.FAIL,
        _failure_reason(candidates, threshold),
        candidates=candidates,
        normalized_files=normalized_files,
        topology_repaired=topology_repaired,
        plannotate_manifest=manifest,
    )


async def cloning_reward_v3(
    answer: str,
    base_dir: Path | str,
    reference_path: Path | str | None = None,
    threshold: float = 0.95,
    validator_params: dict[str, Any] | None = None,
    *,
    require_circular: bool = True,
    plannotate: PlannotateAnnotator | None = None,
    require_plannotate: bool = False,
) -> tuple[float, str]:
    """Compatibility wrapper returning the traditional ``(score, reason)`` pair."""
    report = await verify_cloning_v3(
        answer,
        base_dir,
        reference_path,
        threshold,
        validator_params,
        require_circular=require_circular,
        plannotate=plannotate,
        require_plannotate=require_plannotate,
    )
    return report.score, report.reason
