from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lab_bench_2.cloning_visualization import (
    SourceFeature,
    build_sequence_comparison,
    load_source_features,
    render_comparison_png,
)


def _sequence(value: str, *, circular: bool = False) -> Any:
    return SimpleNamespace(sequence=value, is_circular=circular)


def test_aligns_circular_origin_and_transfers_feature() -> None:
    reference = _sequence("AAAACCCCGGGGTTTT", circular=True)
    predicted = _sequence("CCCCGGGGTTTTAAAA")
    features = (
        SourceFeature(
            label="insert",
            feature_type="CDS",
            sequence="CCCCGGGG",
            source="insert",
            strand=1,
        ),
    )

    comparison = build_sequence_comparison(predicted, reference, features)

    assert comparison.predicted == reference.sequence
    assert comparison.similarity == pytest.approx(1.0)
    assert comparison.differences == ()
    assert comparison.predicted_features[0].label == "insert"
    assert comparison.reference_features[0].start == 4


def test_labels_missing_reference_sequence() -> None:
    reference = _sequence("AAAACCCCGGGGTTTT")
    predicted = _sequence("AAAACCCCTTTT")

    comparison = build_sequence_comparison(predicted, reference)

    assert len(comparison.differences) == 1
    assert comparison.differences[0].kind == "missing"
    assert comparison.differences[0].reference_start == 8
    assert comparison.differences[0].reference_end == 12


def test_renders_png_with_reference_only() -> None:
    reference = _sequence("ACGT" * 100, circular=True)
    comparison = build_sequence_comparison(
        predicted=None,
        reference=reference,
        prediction_error="No executable protocol was submitted.",
    )

    png = render_comparison_png(comparison)

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png) > 1_000


def test_loads_annotations_from_input_genbank(tmp_path: Path) -> None:
    from Bio import SeqIO
    from Bio.Seq import Seq
    from Bio.SeqFeature import SeqFeature, SimpleLocation
    from Bio.SeqRecord import SeqRecord

    sequence = "A" * 20 + "ATGCGTACGTTAGCTA" + "C" * 20
    record = SeqRecord(Seq(sequence), id="input", name="input")
    record.annotations["molecule_type"] = "DNA"
    record.features.append(
        SeqFeature(
            SimpleLocation(20, 36, strand=1),
            type="CDS",
            qualifiers={"label": ["payload"]},
        )
    )
    SeqIO.write(record, tmp_path / "input.gb", "genbank")

    features = load_source_features(tmp_path)

    assert features == (
        SourceFeature(
            label="payload",
            feature_type="CDS",
            sequence="ATGCGTACGTTAGCTA",
            source="input",
            strand=1,
        ),
    )
