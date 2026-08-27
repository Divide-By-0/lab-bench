from __future__ import annotations

from typing import Any

import pytest
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.cloning_simulators import pcr_v2
from lab_bench_2.cloning_simulators.gibson_v2 import gibson_v2
from lab_bench_2.cloning_simulators.golden_gate_v2 import (
    assemble_restriction_fragments_v2,
)
from lab_bench_2.cloning_simulators.restriction_v2 import restriction_assemble_v2
from lab_bench_2.cloning_simulators.rewards_v2 import cloning_reward_v2
from lab_bench_2.cloning_simulators.sequence_similarity_v2 import sequence_similarity_v2


@pytest.mark.asyncio
async def test_pcr_v2_recovers_unique_origin_crossing_amplicon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = "ACGTTGCAAGTCCTGATCGGATCCTAGGCTAACCGTATGGCATCGTACCTGAGTCAACGTAGCTGACT"
    forward_start = 48
    reverse_start = 20
    primer_length = 18
    forward = template[forward_start : forward_start + primer_length]
    from labbench2.cloning.utils import reverse_complement

    reverse = reverse_complement(
        template[reverse_start : reverse_start + primer_length]
    )

    async def no_amplicon(*args: Any, **kwargs: Any) -> Any:
        raise ValueError(
            "PCR simulation ran successfully, but no amplicon was observed."
        )

    monkeypatch.setattr(pcr_v2, "simulate_pcr_legacy", no_amplicon)
    result = await pcr_v2.simulate_pcr_v2(
        BioSequence(sequence=template, is_circular=True), forward, reverse
    )
    expected_middle = (
        template[forward_start + primer_length :] + template[:reverse_start]
    )
    assert result.sequence == forward + expected_middle + reverse_complement(reverse)
    assert result.is_circular is False


def test_golden_gate_v2_enumerates_empty_vector_and_insert_products() -> None:
    fragments = [
        BioSequence(
            sequence="AAAATTTTCCCC",
            overhang_5prime=4,
            overhang_3prime=4,
        ),
        BioSequence(
            sequence="CCCCGGGGAAAA",
            overhang_5prime=4,
            overhang_3prime=4,
        ),
        BioSequence(
            sequence="CCCCTTTTGGGGAAAA",
            overhang_5prime=4,
            overhang_3prime=4,
        ),
    ]
    products = assemble_restriction_fragments_v2(fragments)
    assert sorted(len(product.sequence) for product in products) == [16, 20]
    assert {product.fragment_count for product in products} == {2}


def test_golden_gate_v2_builds_three_fragment_intermediate() -> None:
    fragments = [
        BioSequence(
            sequence="AAAATTTTCCCC",
            overhang_5prime=4,
            overhang_3prime=4,
        ),
        BioSequence(
            sequence="CCCCGGGG",
            overhang_5prime=4,
            overhang_3prime=4,
        ),
        BioSequence(
            sequence="GGGGTTTTAAAA",
            overhang_5prime=4,
            overhang_3prime=4,
        ),
    ]
    products = assemble_restriction_fragments_v2(fragments)
    assert any(product.fragment_count == 3 for product in products)


def test_gibson_v2_keeps_circle_when_another_extension_is_possible() -> None:
    fragments = [
        BioSequence(sequence="AAAATTTTCCCC"),
        BioSequence(sequence="CCCCGGGGAAAA"),
        BioSequence(sequence="AAAACCCCGGGG"),
    ]
    products = gibson_v2(fragments, min_overlap=4, max_overlap=4)
    assert any(product.sequence == "AAAATTTTCCCCGGGG" for product in products)


def test_gibson_v2_tracks_duplicate_names_by_input_position() -> None:
    fragments = [
        BioSequence(sequence="AAAATTTTCCCC", name="same"),
        BioSequence(sequence="CCCCGGGGAAAA", name="same"),
    ]
    products = gibson_v2(fragments, min_overlap=4, max_overlap=4)
    assert any(product.sequence == "AAAATTTTCCCCGGGG" for product in products)


def test_restriction_v2_does_not_hide_insert_behind_self_ligation() -> None:
    backbone = BioSequence(
        sequence="AAAATTTTCCCCAAAA", overhang_5prime=4, overhang_3prime=4
    )
    insert = BioSequence(sequence="AAAAGGGGAAAA", overhang_5prime=4, overhang_3prime=4)
    products = restriction_assemble_v2(backbone, insert)
    assert any("GGGG" in product.sequence for product in products)
    assert any(len(product.sequence) > len(backbone.sequence) for product in products)


def test_similarity_aligns_unequal_circular_sequences_across_origin() -> None:
    sequence = (
        "GACTTACGATCGGATCCGTAGCTAGGCTAACCGTATGGCATCGTACCTGAGTCAACGTAG"
        "CTGACTACCGGTTAGCATGCTAGGATCCATGACCTTGAGCTACGGTACCTAGGCA"
    )
    rotation = 47
    rotated_with_insertion = sequence[rotation:] + "A" + sequence[:rotation]
    similarity = sequence_similarity_v2(
        BioSequence(sequence=sequence, is_circular=True),
        BioSequence(sequence=rotated_with_insertion, is_circular=True),
    )
    assert similarity == pytest.approx(len(sequence) / (len(sequence) + 1))


@pytest.mark.asyncio
async def test_reward_accepts_matching_nonfirst_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from lab_bench_2.cloning_simulators import rewards_v2

    candidates = [
        BioSequence(sequence="AAAA", is_circular=True),
        BioSequence(sequence="CCCC", is_circular=True),
    ]

    async def execute(*args: Any, **kwargs: Any) -> list[BioSequence]:
        return candidates

    monkeypatch.setattr(rewards_v2, "execute_cloning_protocol_v2", execute)
    reference = tmp_path / "reference.fa"
    reference.write_text(">reference (circular)\nCCCC\n", encoding="utf-8")
    score, reason = await cloning_reward_v2(
        answer="<protocol>gibson(a.gb, b.gb)</protocol>",
        base_dir=tmp_path,
        reference_path=reference,
    )
    assert score == 1.0
    assert "candidate 2/2" in reason
