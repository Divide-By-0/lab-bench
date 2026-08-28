from __future__ import annotations

from pathlib import Path
from random import Random
from types import SimpleNamespace
from typing import Any

import pytest

from lab_bench_2.cloning_visualization import (
    SourceFeature,
    _assembly_part_provenance,
    _covered_length,
    _digest_diagnostic,
    _feature_legend,
    _nice_tick_interval,
    _ProvenanceInput,
    _split_circular_range,
    _unquote_exact_file_references,
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


def test_unquotes_only_exact_local_file_references(tmp_path: Path) -> None:
    sample_dir = tmp_path / "sample"
    sample_dir.mkdir()
    (sample_dir / "vector.gbk").touch()
    (tmp_path / "outside.gbk").touch()
    expression = 'pcr("vector.gbk", "ACGT", "not-a-file.gbk"), "../outside.gbk"'

    normalized = _unquote_exact_file_references(expression, sample_dir)

    assert normalized == ('pcr(vector.gbk, "ACGT", "not-a-file.gbk"), "../outside.gbk"')


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


def test_uses_readable_base_pair_tick_intervals() -> None:
    assert _nice_tick_interval(8_970) == 1_000
    assert _nice_tick_interval(42_000) == 5_000
    assert _nice_tick_interval(850) == 100


def test_feature_key_has_stable_ids_and_both_coordinate_sets() -> None:
    reference = _sequence("AAAACCCCGGGGTTTT")
    predicted = _sequence("AAAACCCCGGGGTTTT")
    features = (
        SourceFeature(
            label="payload",
            feature_type="CDS",
            sequence="CCCCGGGG",
            source="input",
            strand=1,
        ),
    )

    legend = _feature_legend(build_sequence_comparison(predicted, reference, features))

    assert len(legend) == 1
    assert legend[0].code == "F1"
    assert legend[0].label == "payload"
    assert legend[0].length == 8
    assert legend[0].predicted_ranges == ((4, 12),)
    assert legend[0].reference_ranges == ((4, 12),)


def test_splits_provenance_fragment_across_circular_origin() -> None:
    assert _split_circular_range(8, 13, 10) == ((8, 10), (0, 3))


def test_assembly_part_provenance_tracks_selected_candidate_rotation() -> None:
    inputs = [
        _ProvenanceInput("P1", "backbone", ("vector",), "AAAACCCC", True, "file"),
        _ProvenanceInput("P2", "insert", ("insert",), "GGGGTTTT", False, "PCR"),
    ]
    product = SimpleNamespace(
        sequence="AAAACCCCGGGGTTTT",
        _assembly_parts=(
            SimpleNamespace(source_index=0, orientation=1, start=0, end=8),
            SimpleNamespace(source_index=1, orientation=1, start=8, end=16),
        ),
    )

    result = _assembly_part_provenance(inputs, product, "GGGGTTTTAAAACCCC")

    assert result is not None
    segments, mask = result
    assert segments[0].ranges == ((8, 16),)
    assert segments[1].ranges == ((0, 8),)
    assert (
        _covered_length(
            tuple(value for segment in segments for value in segment.ranges), 16
        )
        == 16
    )
    assert mask.bit_count() == 16


def test_digest_diagnostic_detects_missing_reference_topology() -> None:
    sequence = "A" * 20 + "AGATCT" + "C" * 20 + "CGATCG" + "G" * 20
    comparison = build_sequence_comparison(
        _sequence(sequence, circular=True),
        _sequence(sequence, circular=False),
    )
    validator_params = {
        "enzyme_1": "BglII",
        "enzyme_2": "PvuI",
        "edit_distance_threshold": 0.95,
    }
    initial = _digest_diagnostic(comparison, validator_params)
    assert initial is not None
    validator_params["fragments"] = list(initial.circular_reference_lengths)

    diagnostic = _digest_diagnostic(comparison, validator_params)

    assert diagnostic is not None
    assert diagnostic.topology_mismatch
    assert len(diagnostic.predicted_lengths) == 2
    assert len(diagnostic.reference_lengths_as_loaded) == 3
    assert all(pair.similarity == 1.0 for pair in diagnostic.circular_reference_pairs)


def test_maps_repeated_cds_with_modified_assembly_boundaries() -> None:
    feature_sequence = "".join(Random(7).choices("ACGT", k=180))
    variant = "CCC" + feature_sequence[3:-3] + "GGG"
    reference = _sequence(("TTTT" + variant) * 5)
    feature = SourceFeature(
        label="reporter",
        feature_type="CDS",
        sequence=feature_sequence,
        source="insert",
        strand=1,
    )

    comparison = build_sequence_comparison(None, reference, (feature,))
    reporters = [
        mapped for mapped in comparison.reference_features if mapped.label == "reporter"
    ]

    assert len(reporters) == 5
    assert all(0.95 <= mapped.identity < 1.0 for mapped in reporters)
