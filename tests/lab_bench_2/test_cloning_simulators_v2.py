from __future__ import annotations

from pathlib import Path
from random import Random
from typing import Any

import pytest
from labbench2.cloning.sequence_models import BioSequence
from labbench2.cloning.utils import reverse_complement

from lab_bench_2.cloning_simulators.execution import (
    execute_cloning_protocol_v2,
    normalize_quoted_file_references,
)
from lab_bench_2.cloning_simulators.gibson_v2 import gibson_v2
from lab_bench_2.cloning_simulators.golden_gate_v2 import goldengate_v2
from lab_bench_2.cloning_simulators.molecular import cut_sequence_v2
from lab_bench_2.cloning_simulators.pcr_v2 import simulate_pcr_v2
from lab_bench_2.cloning_simulators.restriction_v2 import restriction_assemble_v2
from lab_bench_2.cloning_simulators.rewards_v2 import (
    _digest_matches,
    cloning_reward_v2,
)
from lab_bench_2.cloning_simulators.sequence_similarity_v2 import sequence_similarity_v2


def test_normalizes_only_exact_local_quoted_file_references(tmp_path: Path) -> None:
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    (sample_dir / "vector.gbk").touch()
    (tmp_path / "outside.gbk").touch()
    expression = 'pcr("vector.gbk", "ACGT", "not-a-file.gbk"), "../outside.gbk"'

    normalized, filenames = normalize_quoted_file_references(expression, sample_dir)

    assert normalized == ('pcr(vector.gbk, "ACGT", "not-a-file.gbk"), "../outside.gbk"')
    assert filenames == ("vector.gbk",)


@pytest.mark.asyncio
async def test_protocol_accepts_quoted_exact_local_filenames(tmp_path: Path) -> None:
    (tmp_path / "a.fa").write_text(
        ">a\nGGGGGGGGGGAAAATTTTCCCCCCCCCC\n", encoding="utf-8"
    )
    (tmp_path / "b.fa").write_text(
        ">b\nCCCCCCCCCCACACACACGGGGGGGGGG\n", encoding="utf-8"
    )

    products = await execute_cloning_protocol_v2('gibson("a.fa", "b.fa")', tmp_path)

    assert len(products) == 1
    assert products[0].is_circular
    assert products[0].sequence == "GGGGGGGGGGAAAATTTTCCCCCCCCCCACACACAC"


@pytest.mark.asyncio
async def test_pcr_uses_tails_and_crosses_a_circular_origin() -> None:
    template = "ACGTTGCAAGTCCTGATCGGATCCTAGGCTAACCGTATGGCATCGTACCTGAGTCAACGTAGCTGACT"
    forward_start = 48
    reverse_start = 20
    primer_length = 18
    forward_footprint = template[forward_start : forward_start + primer_length]
    reverse_footprint = reverse_complement(
        template[reverse_start : reverse_start + primer_length]
    )
    forward = "GGGG" + forward_footprint
    reverse = "TTTT" + reverse_footprint

    result = await simulate_pcr_v2(
        BioSequence(sequence=template, is_circular=True), forward, reverse
    )
    expected_middle = (
        template[forward_start + primer_length :] + template[:reverse_start]
    )

    assert result.sequence == forward + expected_middle + reverse_complement(reverse)
    assert result.is_circular is False
    assert getattr(result, "_pydna_record").circular is False


@pytest.mark.asyncio
async def test_pcr_rejects_non_specific_primer_binding() -> None:
    template = BioSequence(sequence="ACGT" * 30, is_circular=True)

    with pytest.raises(ValueError, match="PCR not specific"):
        await simulate_pcr_v2(template, "ACGT" * 4, "ACGT" * 4)


def test_gibson_enumerates_competing_circular_products_with_provenance() -> None:
    fragments = [
        BioSequence(sequence="AAAATTTTCCCC"),
        BioSequence(sequence="CCCCGGGGAAAA"),
        BioSequence(sequence="AAAACCCCGGGG"),
    ]

    products = gibson_v2(fragments, min_overlap=4, max_overlap=4)

    assert {product.sequence for product in products} == {
        "AAAATTTTCCCCGGGG",
        "CCCCGGGGAAAA",
    }
    assert all(product.is_circular for product in products)
    first = next(product for product in products if len(product.sequence) == 16)
    assert {part.source_index for part in first._assembly_parts} == {0, 1}


def test_gibson_enforces_candidate_safety_limit() -> None:
    fragments = [
        BioSequence(sequence="AAAATTTTCCCC"),
        BioSequence(sequence="CCCCGGGGAAAA"),
        BioSequence(sequence="AAAACCCCGGGG"),
    ]

    with pytest.raises(ValueError, match="candidate safety limit"):
        gibson_v2(
            fragments,
            min_overlap=4,
            max_overlap=4,
            max_candidates=1,
        )


def test_golden_gate_uses_bsai_sticky_ends_for_three_fragment_products() -> None:
    # Each linear input has inward-facing BsaI sites.  Digestion exposes the
    # designed AAAA -> CCCC -> GGGG -> AAAA overhang cycle.
    fragments = [
        BioSequence(sequence="GGTCTCAAAAATTTTCCCCAGAGACC"),
        BioSequence(sequence="GGTCTCACCCCCACAGGGGAGAGACC"),
        BioSequence(sequence="GGTCTCAGGGGTATAAAAAAGAGACC"),
    ]

    products = goldengate_v2(fragments, "BsaI", min_fragment_length=0)

    assert len(products) == 2
    assert all(product.is_circular for product in products)
    assert all("GGTCTC" not in product.sequence for product in products)
    assert all(
        {part.source_index for part in product._assembly_parts} == {0, 1, 2}
        for product in products
    )


def test_restriction_ligation_preserves_sticky_end_polarity() -> None:
    backbone = BioSequence(sequence="cccGAATTCaaaGAATTCccc".upper(), is_circular=True)
    insert = BioSequence(sequence="ggGAATTCaggtGAATTCgg".upper())
    backbone_fragment = max(
        cut_sequence_v2(backbone, "EcoRI"), key=lambda value: len(value.sequence)
    )
    insert_fragment = max(
        cut_sequence_v2(insert, "EcoRI"), key=lambda value: len(value.sequence)
    )

    products = restriction_assemble_v2(backbone_fragment, insert_fragment)

    two_input_products = [
        product
        for product in products
        if "2 input fragments" in (product.description or "")
    ]
    assert len(two_input_products) == 2
    assert all(product.is_circular for product in two_input_products)
    assert {part.source_index for part in two_input_products[0]._assembly_parts} == {
        0,
        1,
    }


def test_restriction_ligation_returns_no_unassembled_inputs() -> None:
    assert (
        restriction_assemble_v2(
            BioSequence(sequence="AAAA"), BioSequence(sequence="CCCC")
        )
        == []
    )


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


def test_similarity_is_exact_for_reverse_complemented_ds_dna() -> None:
    sequence = "ACGTTGCAAGTCCTGATCGGATCCTAGGCTAACCGTATGGCATCGTAC"
    reverse = reverse_complement(sequence)

    assert sequence_similarity_v2(
        BioSequence(sequence=sequence), BioSequence(sequence=reverse)
    ) == pytest.approx(1.0)
    assert sequence_similarity_v2(
        BioSequence(sequence=sequence, is_circular=True),
        BioSequence(sequence=reverse[17:] + reverse[:17], is_circular=True),
    ) == pytest.approx(1.0)


def test_similarity_does_not_depend_on_exact_anchors() -> None:
    sequence = "".join(Random(17).choices("ACGT", k=1_000))
    rotation = 137
    changed = list(sequence[rotation:] + sequence[:rotation])
    for index in range(10, len(changed), 21):
        changed[index] = "A" if changed[index] != "A" else "C"

    similarity = sequence_similarity_v2(
        BioSequence(sequence=sequence, is_circular=True),
        BioSequence(sequence="".join(changed), is_circular=True),
    )

    assert similarity == pytest.approx(1 - 48 / 1_000)


def test_digest_matching_is_unordered_for_equal_length_fragments() -> None:
    sequence = "GAATTC" + "A" * 34 + "GAATTC" + "C" * 34
    rotated = sequence[13:] + sequence[:13]

    assert _digest_matches(
        BioSequence(sequence=sequence, is_circular=True),
        BioSequence(sequence=rotated, is_circular=True),
        ("EcoRI",),
        1.0,
    )


@pytest.mark.asyncio
async def test_reward_accepts_matching_nonfirst_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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


@pytest.mark.asyncio
async def test_reward_reports_accepted_quoted_filename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lab_bench_2.cloning_simulators import rewards_v2

    async def execute(*args: Any, **kwargs: Any) -> list[BioSequence]:
        return [BioSequence(sequence="CCCC", is_circular=True)]

    monkeypatch.setattr(rewards_v2, "execute_cloning_protocol_v2", execute)
    (tmp_path / "a.gb").touch()
    reference = tmp_path / "reference.fa"
    reference.write_text(">reference (circular)\nCCCC\n", encoding="utf-8")

    score, reason = await cloning_reward_v2(
        answer='<protocol>gibson("a.gb", b.gb)</protocol>',
        base_dir=tmp_path,
        reference_path=reference,
    )

    assert score == 1.0
    assert "accepted quoted filename references: ['a.gb']" in reason
