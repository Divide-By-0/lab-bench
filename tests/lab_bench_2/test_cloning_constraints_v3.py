from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.cloning_simulators.constraints_v3 import (
    ConstructSpec,
    evaluate_construct_constraints,
)
from lab_bench_2.cloning_simulators.features_v3 import FeatureCall
from lab_bench_2.cloning_simulators.rewards_v3 import (
    VerificationStatus,
    verify_cloning_v3,
)

PROMOTER = "AACCGTATGCCGATA"
PAYLOAD = "ATGAAACCCGGGTAA"
POLYA = "TGCATACGATCCTAG"


def _copy_spec(copies: int = 5) -> ConstructSpec:
    return ConstructSpec.from_mapping(
        {
            "name": "five-copy payload",
            "modules": [
                {
                    "id": "promoter",
                    "dna_sequences": [PROMOTER],
                    "match": "dna",
                    "copies": 1,
                },
                {
                    "id": "payload",
                    "dna_sequences": [PAYLOAD],
                    "match": "dna",
                    "copies": copies,
                },
                {
                    "id": "polya",
                    "dna_sequences": [POLYA],
                    "match": "dna",
                    "copies": 1,
                },
            ],
            "ordered": [["promoter", "payload", "polya"]],
        }
    )


def test_constraint_copy_count_and_partial_order_ignore_unrelated_tags(
    tmp_path: Path,
) -> None:
    tag = "GATCGATCGATC"
    sequence = POLYA + tag + PROMOTER + PAYLOAD * 5 + tag
    assessment = evaluate_construct_constraints(
        sequence,
        circular=True,
        spec=_copy_spec(),
        base_dir=tmp_path,
    )
    assert assessment.passes
    assert (
        next(
            value for value in assessment.modules if value.id == "payload"
        ).observed_copies
        == 5
    )


@pytest.mark.parametrize("copies", [4, 6])
def test_constraint_rejects_wrong_complete_copy_count(
    tmp_path: Path, copies: int
) -> None:
    sequence = PROMOTER + PAYLOAD * copies + POLYA
    assessment = evaluate_construct_constraints(
        sequence,
        circular=True,
        spec=_copy_spec(),
        base_dir=tmp_path,
    )
    assert not assessment.passes
    payload = next(value for value in assessment.modules if value.id == "payload")
    assert payload.observed_copies == copies
    assert not payload.passes


def test_constraint_rejects_only_an_explicitly_wrong_order(tmp_path: Path) -> None:
    sequence = PROMOTER + POLYA + PAYLOAD * 5
    assessment = evaluate_construct_constraints(
        sequence,
        circular=True,
        spec=_copy_spec(),
        base_dir=tmp_path,
    )
    assert not assessment.passes
    assert assessment.relationships[0].detail.startswith("required module order")


def test_accepted_protein_variants_are_deduplicated(tmp_path: Path) -> None:
    # DNA translates to MKT. The second accepted tag variant is deliberately
    # absent; either variant satisfies the one-copy module constraint.
    sequence = "GGGATGAAAACCTAACCC"
    spec = ConstructSpec.from_mapping(
        {
            "name": "tag variants",
            "modules": [
                {
                    "id": "tag",
                    "description": "accepted epitope tag",
                    "protein_sequences": ["MKT", "MRT"],
                    "match": "protein",
                    "copies": 1,
                }
            ],
        }
    )
    assessment = evaluate_construct_constraints(
        sequence, circular=True, spec=spec, base_dir=tmp_path
    )
    assert assessment.passes
    assert assessment.modules[0].observed_copies == 1


def test_missing_initial_methionine_requires_explicit_acceptance(
    tmp_path: Path,
) -> None:
    sequence = "GGGATTGAACAACCC"  # IEQ, without the standalone protein's initial M
    module = {
        "id": "selection_marker",
        "description": "selection-marker protein",
        "protein_sequences": ["MIEQ"],
        "match": "protein",
        "copies": 1,
    }
    strict = evaluate_construct_constraints(
        sequence,
        circular=True,
        spec=ConstructSpec.from_mapping(
            {"name": "strict protein", "modules": [module]}
        ),
        base_dir=tmp_path,
    )
    contextual = evaluate_construct_constraints(
        sequence,
        circular=True,
        spec=ConstructSpec.from_mapping(
            {
                "name": "polyprotein-context protein",
                "modules": [
                    {**module, "allow_missing_initial_methionine": True}
                ],
            }
        ),
        base_dir=tmp_path,
    )

    assert not strict.passes
    assert contextual.passes
    assert contextual.modules[0].calls[0].source.endswith(
        ":without-initial-methionine"
    )


def test_tag_location_is_enforced_only_by_explicit_fusion_constraint(
    tmp_path: Path,
) -> None:
    left_dna = "ATGAAAACC"  # MKT
    tag_dna = "GGTGCTTCT"  # GAS
    base_spec = {
        "name": "explicit tag fusion",
        "modules": [
            {
                "id": "payload",
                "protein_sequences": ["MKT"],
                "match": "protein",
                "copies": 1,
            },
            {
                "id": "tag",
                "protein_sequences": ["GAS"],
                "match": "protein",
                "copies": 1,
            },
        ],
    }
    unconstrained = evaluate_construct_constraints(
        left_dna + "AAAAAA" + tag_dna,
        circular=True,
        spec=ConstructSpec.from_mapping(base_spec),
        base_dir=tmp_path,
    )
    assert unconstrained.passes

    constrained_spec = ConstructSpec.from_mapping(
        {
            **base_spec,
            "fusions": [{"left": "payload", "right": "tag", "max_linker_bp": 3}],
        }
    )
    constrained = evaluate_construct_constraints(
        left_dna + "AAAAAA" + tag_dna,
        circular=True,
        spec=constrained_spec,
        base_dir=tmp_path,
    )
    assert not constrained.passes
    assert "required in-frame fusion not found" in constrained.relationships[0].detail


def test_direct_sequence_evidence_takes_priority_over_duplicate_annotation_calls(
    tmp_path: Path,
) -> None:
    spec = ConstructSpec.from_mapping(
        {
            "name": "evidence priority",
            "modules": [
                {
                    "id": "payload",
                    "dna_sequences": [PAYLOAD],
                    "annotation_aliases": ["payload"],
                    "match": "either",
                    "copies": 1,
                }
            ],
        }
    )
    annotations = tuple(
        FeatureCall(
            key=f"cds:test:payload_{index}",
            label="payload",
            feature_type="cds",
            start=index * 3,
            end=index * 3 + 9,
            span=9,
            strand=1,
            identity=1.0,
            coverage=1.0,
            source="pLannotate:test",
        )
        for index in range(2)
    )
    assessment = evaluate_construct_constraints(
        "GGG" + PAYLOAD + "CCC",
        circular=True,
        spec=spec,
        base_dir=tmp_path,
        annotation_calls=annotations,
    )
    assert assessment.passes
    assert assessment.modules[0].observed_copies == 1
    assert assessment.modules[0].evidence == "direct DNA/protein sequence evidence"


def test_annotation_is_deterministic_fallback_when_no_sequence_template(
    tmp_path: Path,
) -> None:
    spec = ConstructSpec.from_mapping(
        {
            "name": "annotation fallback",
            "modules": [
                {
                    "id": "ires",
                    "annotation_aliases": ["IRES", "IRES2"],
                    "feature_types": ["misc_feature"],
                    "match": "annotation",
                    "copies": 1,
                }
            ],
        }
    )
    call = FeatureCall(
        key="misc_feature:snapgene:ires2",
        label="IRES2",
        feature_type="misc_feature",
        start=10,
        end=100,
        span=90,
        strand=1,
        identity=0.99,
        coverage=1.0,
        source="pLannotate:snapgene",
    )
    assessment = evaluate_construct_constraints(
        "A" * 200,
        circular=True,
        spec=spec,
        base_dir=tmp_path,
        annotation_calls=(call,),
    )
    assert assessment.passes
    assert assessment.modules[0].evidence == "pLannotate evidence"


@pytest.mark.asyncio
async def test_constraint_mode_makes_whole_reference_similarity_advisory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lab_bench_2.cloning_simulators import rewards_v3

    candidate = BioSequence(sequence="GGG" + PAYLOAD + "CCC", is_circular=True)

    async def execute(*args: Any, **kwargs: Any) -> list[BioSequence]:
        return [candidate]

    monkeypatch.setattr(rewards_v3, "execute_cloning_protocol_v2", execute)
    reference = tmp_path / "reference.fa"
    reference.write_text(
        ">reference (circular)\n" + "T" * len(candidate.sequence) + "\n",
        encoding="utf-8",
    )
    spec = {
        "name": "payload construct",
        "modules": [
            {
                "id": "payload",
                "dna_sequences": [PAYLOAD],
                "match": "dna",
                "copies": 1,
            }
        ],
    }
    report = await verify_cloning_v3(
        "<protocol>gibson(a.gb, b.gb)</protocol>",
        tmp_path,
        reference,
        construct_spec=spec,
    )
    assert report.status is VerificationStatus.PASS
    assert report.candidates[0].similarity_pass is False
    assert report.candidates[0].passes
    assert "advisory" in report.reason
