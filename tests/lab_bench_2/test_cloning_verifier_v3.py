"""Regression tests for the hybrid cloning verifier."""

from __future__ import annotations

from pathlib import Path
from random import Random
from typing import Any

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.cloning_simulators.features_v3 import (
    FeatureCall,
    FeatureTemplate,
    compare_feature_architecture,
    compare_repeat_burden,
    map_feature_templates,
    parse_plannotate_csv,
)
from lab_bench_2.cloning_simulators.rewards_v3 import (
    VerificationStatus,
    verify_cloning_v3,
)


def _call(
    key: str,
    feature_type: str,
    start: int,
    strand: int = 1,
    span: int = 50,
) -> FeatureCall:
    return FeatureCall(
        key=key,
        label=key,
        feature_type=feature_type,
        start=start,
        end=(start + span) % 1_000,
        span=span,
        strand=strand,
        identity=1.0,
        coverage=1.0,
        source="test",
    )


def test_feature_graph_accepts_circular_rotation_and_global_reverse() -> None:
    expected = (
        _call("cds:payload", "cds", 40),
        _call("term:t1", "terminator", 180),
        _call("prom:cmv", "promoter", 900),
    )
    rotated = (
        _call("prom:cmv", "promoter", 100),
        _call("cds:payload", "cds", 240),
        _call("term:t1", "terminator", 380),
    )
    reverse = (
        _call("term:t1", "terminator", 100, -1),
        _call("cds:payload", "cds", 240, -1),
        _call("prom:cmv", "promoter", 380, -1),
    )

    assert compare_feature_architecture(
        expected,
        rotated,
        backend="test",
        sequence_length=1_000,
        minimum_expected=1,
    ).passes
    assert compare_feature_architecture(
        expected,
        reverse,
        backend="test",
        sequence_length=1_000,
        minimum_expected=1,
    ).passes


def test_feature_graph_rejects_wrong_order_and_missing_feature() -> None:
    expected = (
        _call("prom:cmv", "promoter", 100),
        _call("cds:payload", "cds", 300),
        _call("term:t1", "terminator", 500),
    )
    wrong_order = (
        _call("prom:cmv", "promoter", 100),
        _call("term:t1", "terminator", 300),
        _call("cds:payload", "cds", 500),
    )

    assessment = compare_feature_architecture(
        expected,
        wrong_order,
        backend="test",
        sequence_length=1_000,
        minimum_expected=1,
    )
    assert not assessment.passes
    assert not assessment.order_matches

    missing = compare_feature_architecture(
        expected,
        wrong_order[:-1],
        backend="test",
        sequence_length=1_000,
        minimum_expected=1,
    )
    assert not missing.passes
    assert missing.missing == ("cds:payload",)


def test_input_feature_mapping_crosses_circular_origin() -> None:
    sequence = "CCCC" + "G" * 32 + "AAAA"
    template = FeatureTemplate(
        key="cds:origin_crossing:8",
        label="origin crossing",
        feature_type="cds",
        sequence="AAAACCCC",
        strand=1,
        source="input.gbk",
    )

    circular = map_feature_templates(sequence, (template,), circular=True)
    linear = map_feature_templates(sequence, (template,), circular=False)

    assert [(value.start, value.end) for value in circular] == [(36, 4)]
    assert linear == ()


def test_plannotate_csv_filters_fragments_and_low_coverage(tmp_path: Path) -> None:
    csv_path = tmp_path / "annotations.csv"
    csv_path.write_text(
        "sseqid,start location,end location,strand,percent identity,"
        "full length of feature in db,length of found feature,percent match length,"
        "fragment,database,Feature,Type,Description,sequence\n"
        "cmv,10,210,1,99,200,200,100,False,snapgene,CMV,promoter,,ACGT\n"
        "partial,300,420,1,99,500,120,24,False,snapgene,partial,CDS,,ACGT\n"
        "fragment,500,650,1,99,150,150,100,True,snapgene,fragment,CDS,,ACGT\n",
        encoding="utf-8",
    )

    calls = parse_plannotate_csv(csv_path)

    assert len(calls) == 1
    assert calls[0].key == "promoter:snapgene:cmv"


def test_repeat_gate_rejects_only_new_direct_or_inverted_repeats() -> None:
    reference_sequence = "".join(Random(7).choices("ACGT", k=1_000))
    candidate_sequence = list(reference_sequence)
    candidate_sequence[500:520] = reference_sequence[100:120]
    reference = BioSequence(sequence=reference_sequence, is_circular=True)
    candidate = BioSequence(sequence="".join(candidate_sequence), is_circular=True)

    unchanged = compare_repeat_burden(reference, reference, repeat_length=20)
    introduced = compare_repeat_burden(candidate, reference, repeat_length=20)

    assert unchanged.passes
    assert not introduced.passes
    assert introduced.new_repeat_hashes


@pytest.mark.asyncio
async def test_same_candidate_must_pass_sequence_and_topology(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lab_bench_2.cloning_simulators import rewards_v3

    candidates = [
        BioSequence(sequence="A" * 200, is_circular=False),
        BioSequence(sequence="C" * 200, is_circular=True),
    ]

    async def execute(*args: Any, **kwargs: Any) -> list[BioSequence]:
        return candidates

    monkeypatch.setattr(rewards_v3, "execute_cloning_protocol_v2", execute)
    reference = tmp_path / "reference.fa"
    reference.write_text(">reference (circular)\n" + "A" * 200 + "\n", encoding="utf-8")

    report = await verify_cloning_v3(
        "<protocol>gibson(a.gb, b.gb)</protocol>", tmp_path, reference
    )

    assert report.status is VerificationStatus.FAIL
    assert "Topology gate failed" in report.reason


@pytest.mark.asyncio
async def test_feature_damage_fails_despite_high_global_similarity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lab_bench_2.cloning_simulators import rewards_v3

    sequence = "".join(Random(42).choices("ACGT", k=1_000))
    record = SeqRecord(Seq(sequence), id="input", name="input")
    record.annotations["molecule_type"] = "DNA"
    record.features.append(
        SeqFeature(
            FeatureLocation(100, 220, strand=1),
            type="CDS",
            qualifiers={"label": ["payload"]},
        )
    )
    SeqIO.write(record, tmp_path / "input.gbk", "genbank")
    damaged = list(sequence)
    for index in range(105, 220, 16):
        damaged[index] = "A" if damaged[index] != "A" else "C"
    candidate = BioSequence(sequence="".join(damaged), is_circular=True)

    async def execute(*args: Any, **kwargs: Any) -> list[BioSequence]:
        return [candidate]

    monkeypatch.setattr(rewards_v3, "execute_cloning_protocol_v2", execute)
    reference = tmp_path / "reference.fa"
    reference.write_text(">reference (circular)\n" + sequence + "\n", encoding="utf-8")

    report = await verify_cloning_v3(
        "<protocol>gibson(input.gbk, input.gbk)</protocol>",
        tmp_path,
        reference,
    )

    assert report.candidates[0].similarity > 0.99
    assert report.status is VerificationStatus.FAIL
    assert "Structural gate failed" in report.reason


@pytest.mark.asyncio
async def test_required_plannotate_without_backend_is_verifier_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lab_bench_2.cloning_simulators import rewards_v3

    async def execute(*args: Any, **kwargs: Any) -> list[BioSequence]:
        return [BioSequence(sequence="A" * 200, is_circular=True)]

    monkeypatch.setattr(rewards_v3, "execute_cloning_protocol_v2", execute)
    reference = tmp_path / "reference.fa"
    reference.write_text(">reference (circular)\n" + "A" * 200 + "\n", encoding="utf-8")

    report = await verify_cloning_v3(
        "<protocol>gibson(a.gb, b.gb)</protocol>",
        tmp_path,
        reference,
        require_plannotate=True,
    )

    assert report.status is VerificationStatus.ERROR
    assert "pLannotate was required" in report.reason
