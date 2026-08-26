"""Compact cloning-assembly visualizations for the Inspect transcript."""

from __future__ import annotations

import base64
import io
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from labbench2.cloning.sequence_models import BioSequence


_FEATURE_TYPES = {
    "CDS",
    "gene",
    "misc_feature",
    "polyA_signal",
    "promoter",
    "protein_bind",
    "regulatory",
    "rep_origin",
    "terminator",
}
_FEATURE_COLORS = {
    "CDS": "#3b82f6",
    "gene": "#2563eb",
    "misc_feature": "#94a3b8",
    "polyA_signal": "#ec4899",
    "promoter": "#f59e0b",
    "protein_bind": "#8b5cf6",
    "regulatory": "#14b8a6",
    "rep_origin": "#10b981",
    "terminator": "#ef4444",
}
_MAX_FEATURES = 24
_MAX_DIFF_ROWS = 8
_MAX_ROTATION_CANDIDATES = 128
_MIN_FEATURE_LENGTH = 12
_MAX_FEATURE_OCCURRENCES = 8
_MIN_DIFFERENCE_WIDTH = 2
_MAX_SEQUENCE_WINDOW = 80
_FASTA_LINE_WIDTH = 80
_DNA_COMPLEMENT = str.maketrans("ACGTRYMKBDHVN", "TGCAYRKMVHDBN")
_PROVENANCE_COLORS = ("#0ea5e9", "#a855f7", "#f97316", "#22c55e")
_DIGEST_COLORS = ("#7c3aed", "#0f766e", "#be123c", "#b45309")


@dataclass(frozen=True)
class SourceFeature:
    """Annotation and sequence recovered from an input GenBank feature."""

    label: str
    feature_type: str
    sequence: str
    source: str
    strand: int


@dataclass(frozen=True)
class MappedFeature:
    """A source feature located on an assembled sequence."""

    label: str
    feature_type: str
    start: int
    end: int
    source: str
    strand: int


@dataclass(frozen=True)
class Difference:
    """One non-matching opcode between the predicted and reference sequences."""

    kind: str
    predicted_start: int
    predicted_end: int
    reference_start: int
    reference_end: int


@dataclass(frozen=True)
class SequenceComparison:
    """Data needed for both the image and text comparison."""

    predicted: str | None
    reference: str
    predicted_circular: bool
    reference_circular: bool
    similarity: float | None
    predicted_features: tuple[MappedFeature, ...]
    reference_features: tuple[MappedFeature, ...]
    differences: tuple[Difference, ...]
    prediction_error: str | None = None


@dataclass(frozen=True)
class FeatureLegendEntry:
    """Stable display identity for one annotation in either assembly."""

    code: str
    label: str
    feature_type: str
    length: int
    source: str
    predicted_ranges: tuple[tuple[int, int], ...]
    reference_ranges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ProvenanceSegment:
    """One protocol input fragment mapped onto the predicted assembly."""

    code: str
    operation: str
    source_files: tuple[str, ...]
    fragment_length: int
    ranges: tuple[tuple[int, int], ...]
    strand: int


@dataclass(frozen=True)
class RestrictionSite:
    """Recognition sequence and cut position for a restriction enzyme."""

    enzyme: str
    motif: str
    motif_start: int
    cut_position: int


@dataclass(frozen=True)
class DigestFragmentPair:
    """Size-sorted predicted/reference digest fragment comparison."""

    predicted_length: int
    reference_length: int
    similarity: float


@dataclass(frozen=True)
class DigestDiagnostic:
    """A transparent reproduction of the benchmark's digest validation."""

    enzymes: tuple[str, ...]
    threshold: float
    expected_lengths: tuple[int, ...]
    predicted_sites: tuple[RestrictionSite, ...]
    reference_sites: tuple[RestrictionSite, ...]
    predicted_lengths: tuple[int, ...]
    reference_lengths_as_loaded: tuple[int, ...]
    fragment_pairs_as_loaded: tuple[DigestFragmentPair, ...]
    circular_reference_lengths: tuple[int, ...]
    circular_reference_pairs: tuple[DigestFragmentPair, ...]
    topology_mismatch: bool


async def cloning_comparison_markdown(
    answer: str,
    base_dir: Path,
    reference_path: Path,
    validator_params: dict[str, Any] | None = None,
) -> str:
    """Build an Inspect-renderable annotated comparison for a cloning answer.

    The benchmark's protocol is executed independently so the predicted sequence
    can be shown. Visualization errors are returned as diagnostic text and must
    never alter the score.
    """
    from labbench2.cloning.cloning_protocol import (
        PROTOCOL_TAG_CLOSE,
        PROTOCOL_TAG_OPEN,
        CloningProtocol,
    )
    from labbench2.cloning.sequence_models import BioSequence
    from labbench2.cloning.utils import extract_between_tags

    reference = BioSequence.from_file(reference_path)
    predicted: BioSequence | None = None
    prediction_error: str | None = None
    protocol: Any | None = None

    if PROTOCOL_TAG_OPEN not in answer or PROTOCOL_TAG_CLOSE not in answer:
        prediction_error = "No executable protocol was submitted."
    else:
        try:
            expression = extract_between_tags(
                answer, PROTOCOL_TAG_OPEN, PROTOCOL_TAG_CLOSE
            )
            protocol = CloningProtocol(expression)
            results = await protocol.run(base_dir)
            if results:
                predicted = results[0]
            else:
                prediction_error = "The protocol produced no assembled sequence."
        except Exception as exc:  # visualization must not affect evaluation
            prediction_error = f"Could not visualize predicted assembly: {exc}"

    comparison = build_sequence_comparison(
        predicted=predicted,
        reference=reference,
        source_features=load_source_features(base_dir),
        prediction_error=prediction_error,
    )
    provenance = (
        await _protocol_provenance(protocol.operation, base_dir, comparison.predicted)
        if protocol is not None and comparison.predicted
        else ()
    )
    digest = _digest_diagnostic(comparison, validator_params or {})
    png = render_comparison_png(comparison, provenance=provenance, digest=digest)
    encoded = base64.b64encode(png).decode("ascii")
    return _comparison_markdown(
        comparison,
        encoded,
        provenance=provenance,
        digest=digest,
    )


def load_source_features(base_dir: Path) -> tuple[SourceFeature, ...]:
    """Read useful annotations from the question's input GenBank files."""
    from Bio import SeqIO

    features: list[SourceFeature] = []
    for path in sorted(base_dir.iterdir()):
        if path.suffix.lower() not in {".gb", ".gbk", ".genbank", ".gbff"}:
            continue
        try:
            read_record = cast(Callable[[Path, str], Any], SeqIO.read)
            record = read_record(path, "genbank")
        except Exception:
            continue
        for feature in record.features:
            if feature.type not in _FEATURE_TYPES:
                continue
            sequence = str(feature.extract(record.seq)).upper()
            if len(sequence) < _MIN_FEATURE_LENGTH:
                continue
            features.append(
                SourceFeature(
                    label=_feature_label(feature.qualifiers, feature.type),
                    feature_type=feature.type,
                    sequence=sequence,
                    source=path.stem,
                    strand=feature.location.strand or 0,
                )
            )
    return tuple(features)


def build_sequence_comparison(
    predicted: BioSequence | None,
    reference: BioSequence,
    source_features: tuple[SourceFeature, ...] = (),
    prediction_error: str | None = None,
) -> SequenceComparison:
    """Align origins, transfer annotations, and summarize sequence edits."""
    reference_sequence = reference.sequence.upper()
    predicted_sequence: str | None = None
    similarity: float | None = None
    differences: tuple[Difference, ...] = ()

    if predicted is not None:
        predicted_sequence, similarity = _best_rotation(
            predicted.sequence.upper(),
            reference_sequence,
            predicted.is_circular or reference.is_circular,
        )
        differences = _differences(predicted_sequence, reference_sequence)

    return SequenceComparison(
        predicted=predicted_sequence,
        reference=reference_sequence,
        predicted_circular=predicted.is_circular if predicted else False,
        reference_circular=reference.is_circular,
        similarity=similarity,
        predicted_features=(
            tuple(_map_features(predicted_sequence, source_features))
            if predicted_sequence
            else ()
        ),
        reference_features=tuple(_map_features(reference_sequence, source_features)),
        differences=differences,
        prediction_error=prediction_error,
    )


async def _protocol_provenance(
    operation: Any,
    base_dir: Path,
    predicted_sequence: str,
) -> tuple[ProvenanceSegment, ...]:
    """Map top-level assembly inputs back onto the predicted plasmid."""
    from labbench2.cloning.utils import reverse_complement

    nodes = getattr(operation, "sequences", None)
    if not isinstance(nodes, list) or not nodes:
        nodes = [operation]
    doubled = predicted_sequence + predicted_sequence
    segments: list[ProvenanceSegment] = []
    for node_index, node in enumerate(nodes, start=1):
        try:
            fragments = await node.execute(base_dir)
        except Exception:
            continue
        for fragment_index, fragment in enumerate(fragments, start=1):
            mapped_ranges: tuple[tuple[int, int], ...] = ()
            mapped_strand = 1
            for strand, candidate in (
                (1, fragment.sequence.upper()),
                (-1, reverse_complement(fragment.sequence.upper())),
            ):
                start = doubled.find(candidate)
                if 0 <= start < len(predicted_sequence):
                    mapped_ranges = _split_circular_range(
                        start,
                        start + len(candidate),
                        len(predicted_sequence),
                    )
                    mapped_strand = strand
                    break
            code = f"P{node_index}"
            if len(fragments) > 1:
                code += f".{fragment_index}"
            source_files = tuple(
                sorted(Path(value).stem for value in node.file_references())
            )
            segments.append(
                ProvenanceSegment(
                    code=code,
                    operation=_operation_label(node),
                    source_files=source_files,
                    fragment_length=len(fragment.sequence),
                    ranges=mapped_ranges,
                    strand=mapped_strand,
                )
            )
    return tuple(segments)


def _operation_label(operation: Any) -> str:
    name = type(operation).__name__.removesuffix("Operation")
    return {
        "PCR": "PCR fragment",
        "Gibson": "Gibson input",
        "GoldenGate": "Golden Gate input",
        "RestrictionAssemble": "restriction-assembly input",
        "EnzymeCut": "restriction fragment",
        "FileReference": "input sequence",
    }.get(name, name)


def _split_circular_range(
    start: int, end: int, sequence_length: int
) -> tuple[tuple[int, int], ...]:
    if sequence_length <= 0 or end <= start:
        return ()
    span = min(end - start, sequence_length)
    start %= sequence_length
    normalized_end = start + span
    if normalized_end <= sequence_length:
        return ((start, normalized_end),)
    return ((start, sequence_length), (0, normalized_end - sequence_length))


def _digest_diagnostic(
    comparison: SequenceComparison,
    validator_params: dict[str, Any],
) -> DigestDiagnostic | None:
    if comparison.predicted is None:
        return None
    enzymes: list[str] = []
    index = 1
    while value := validator_params.get(f"enzyme_{index}"):
        enzymes.append(str(value))
        index += 1
    if not enzymes:
        return None

    from labbench2.cloning.enzyme_cut import enzyme_cut
    from labbench2.cloning.sequence_alignment import sequence_similarity
    from labbench2.cloning.sequence_models import BioSequence

    predicted = BioSequence(
        sequence=comparison.predicted,
        is_circular=comparison.predicted_circular,
    )
    reference_as_loaded = BioSequence(
        sequence=comparison.reference,
        is_circular=comparison.reference_circular,
    )
    reference_circular = reference_as_loaded.model_copy(update={"is_circular": True})

    def digest(sequence: BioSequence) -> list[BioSequence]:
        fragments = [sequence]
        for enzyme in enzymes:
            fragments = [
                output
                for fragment in fragments
                for output in enzyme_cut(fragment, enzyme)
            ]
        return sorted(fragments, key=lambda value: len(value.sequence))

    predicted_fragments = digest(predicted)
    loaded_fragments = digest(reference_as_loaded)
    circular_fragments = digest(reference_circular)

    def pairs(reference_fragments: list[BioSequence]) -> tuple[DigestFragmentPair, ...]:
        if len(predicted_fragments) != len(reference_fragments):
            return ()
        return tuple(
            DigestFragmentPair(
                predicted_length=len(predicted_fragment.sequence),
                reference_length=len(reference_fragment.sequence),
                similarity=sequence_similarity(predicted_fragment, reference_fragment),
            )
            for predicted_fragment, reference_fragment in zip(
                predicted_fragments, reference_fragments, strict=True
            )
        )

    expected_lengths = tuple(
        sorted(int(value) for value in validator_params.get("fragments", []))
    )
    circular_lengths = tuple(len(value.sequence) for value in circular_fragments)
    topology_mismatch = bool(
        comparison.predicted_circular
        and not comparison.reference_circular
        and expected_lengths
        and expected_lengths == circular_lengths
    )
    return DigestDiagnostic(
        enzymes=tuple(enzymes),
        threshold=float(validator_params.get("edit_distance_threshold", 0.95)),
        expected_lengths=expected_lengths,
        predicted_sites=_restriction_sites(
            comparison.predicted, comparison.predicted_circular, tuple(enzymes)
        ),
        reference_sites=_restriction_sites(
            comparison.reference, comparison.reference_circular, tuple(enzymes)
        ),
        predicted_lengths=tuple(len(value.sequence) for value in predicted_fragments),
        reference_lengths_as_loaded=tuple(
            len(value.sequence) for value in loaded_fragments
        ),
        fragment_pairs_as_loaded=pairs(loaded_fragments),
        circular_reference_lengths=circular_lengths,
        circular_reference_pairs=pairs(circular_fragments),
        topology_mismatch=topology_mismatch,
    )


def _restriction_sites(
    sequence: str,
    circular: bool,
    enzymes: tuple[str, ...],
) -> tuple[RestrictionSite, ...]:
    from Bio.Restriction import RestrictionBatch  # type: ignore[attr-defined]
    from Bio.Seq import Seq

    sites: list[RestrictionSite] = []
    for enzyme_name in enzymes:
        enzyme = RestrictionBatch([enzyme_name]).get(enzyme_name)
        for cut_position in enzyme.search(Seq(sequence), linear=not circular):
            motif_start = (cut_position - enzyme.fst5 - 1) % len(sequence)
            sites.append(
                RestrictionSite(
                    enzyme=enzyme_name,
                    motif=str(enzyme.site),
                    motif_start=motif_start,
                    cut_position=((cut_position - 1) % len(sequence)) + 1,
                )
            )
    return tuple(sorted(sites, key=lambda value: value.motif_start))


def render_comparison_png(
    comparison: SequenceComparison,
    *,
    provenance: tuple[ProvenanceSegment, ...] = (),
    digest: DigestDiagnostic | None = None,
) -> bytes:
    """Render a compact PNG that Inspect can display inside an Info event."""
    from PIL import Image, ImageDraw, ImageFont

    width = 1200
    legend = _feature_legend(comparison)
    feature_codes = {_legend_key(entry): entry.code for entry in legend}
    predicted_lanes = _feature_lane_counts(
        comparison.predicted_features, comparison.predicted, width
    )
    reference_lanes = _feature_lane_counts(
        comparison.reference_features, comparison.reference, width
    )
    predicted_sites = digest.predicted_sites if digest else ()
    reference_sites = digest.reference_sites if digest else ()
    predicted_height = _sequence_track_height(
        *predicted_lanes,
        digest_sites=len(predicted_sites),
        provenance_segments=len(provenance),
    )
    reference_height = _sequence_track_height(
        *reference_lanes,
        digest_sites=len(reference_sites),
    )
    legend_rows = math.ceil(len(legend) / 2)
    legend_height = 48 + legend_rows * 24 if legend else 0
    height = 84 + predicted_height + 24 + reference_height + 94 + legend_height + 28
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=14)
    bold = ImageFont.load_default(size=20)

    draw.text((48, 28), "Cloning assembly comparison", fill="#0f172a", font=bold)
    metrics = _metric_line(comparison)
    draw.text((48, 50), metrics, fill="#475569", font=font)

    next_y = _draw_sequence_track(
        draw,
        title="Predicted assembly",
        sequence=comparison.predicted,
        circular=comparison.predicted_circular,
        features=comparison.predicted_features,
        top=82,
        width=width,
        font=font,
        feature_codes=feature_codes,
        digest_sites=predicted_sites,
        provenance=provenance,
        empty_message=comparison.prediction_error or "No predicted assembly",
    )
    next_y = _draw_sequence_track(
        draw,
        title="Reference assembly",
        sequence=comparison.reference,
        circular=comparison.reference_circular,
        features=comparison.reference_features,
        top=next_y + 24,
        width=width,
        font=font,
        feature_codes=feature_codes,
        digest_sites=reference_sites,
    )
    difference_y = next_y + 64
    _draw_difference_track(draw, comparison, y=difference_y, width=width, font=font)
    if legend:
        _draw_feature_legend(
            draw,
            legend,
            top=difference_y + 76,
            width=width,
            font=font,
        )

    with io.BytesIO() as output:
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()


def _feature_label(qualifiers: dict[str, Any], fallback: str) -> str:
    for key in ("label", "gene", "product", "note"):
        value = qualifiers.get(key)
        if isinstance(value, list) and value:
            return str(value[0])[:42]
        if isinstance(value, str) and value:
            return value[:42]
    return fallback


def _best_rotation(predicted: str, reference: str, circular: bool) -> tuple[str, float]:
    from rapidfuzz.distance import Levenshtein

    if not predicted:
        return predicted, 0.0
    offsets = {0}
    shortest_length = min(len(predicted), len(reference))
    anchor_length = min(31, max(8, shortest_length // 4))
    if circular and shortest_length >= anchor_length:
        step = max(1, len(reference) // 40)
        doubled = predicted + predicted
        for reference_pos in range(0, len(reference) - anchor_length + 1, step):
            anchor = reference[reference_pos : reference_pos + anchor_length]
            predicted_pos = doubled.find(anchor)
            while (
                0 <= predicted_pos < len(predicted)
                and len(offsets) < _MAX_ROTATION_CANDIDATES
            ):
                offsets.add((predicted_pos - reference_pos) % len(predicted))
                predicted_pos = doubled.find(anchor, predicted_pos + 1)
            if len(offsets) >= _MAX_ROTATION_CANDIDATES:
                break

    best_sequence = predicted
    best_similarity = -1.0
    for offset in offsets:
        rotated = predicted[offset:] + predicted[:offset]
        similarity = float(Levenshtein.normalized_similarity(rotated, reference))
        if similarity > best_similarity:
            best_sequence = rotated
            best_similarity = similarity
    return best_sequence, max(0.0, best_similarity)


def _differences(predicted: str, reference: str) -> tuple[Difference, ...]:
    from rapidfuzz.distance import Levenshtein

    return tuple(
        Difference(
            kind={"insert": "missing", "delete": "extra"}.get(opcode.tag, opcode.tag),
            predicted_start=opcode.src_start,
            predicted_end=opcode.src_end,
            reference_start=opcode.dest_start,
            reference_end=opcode.dest_end,
        )
        for opcode in Levenshtein.opcodes(predicted, reference)
        if opcode.tag != "equal"
    )


def _map_features(
    sequence: str, source_features: tuple[SourceFeature, ...]
) -> list[MappedFeature]:
    mapped: list[MappedFeature] = []
    seen: set[tuple[str, str, int, int]] = set()
    for feature in sorted(
        source_features, key=lambda value: len(value.sequence), reverse=True
    ):
        candidates: tuple[tuple[str, int], ...] = ((feature.sequence, feature.strand),)
        reverse = feature.sequence.translate(_DNA_COMPLEMENT)[::-1]
        if reverse != feature.sequence:
            candidates += ((reverse, -feature.strand),)
        for candidate, strand in candidates:
            start = sequence.find(candidate)
            occurrence_count = 0
            while start >= 0 and occurrence_count < _MAX_FEATURE_OCCURRENCES:
                key = (
                    feature.label,
                    feature.feature_type,
                    start,
                    start + len(candidate),
                )
                if key not in seen:
                    seen.add(key)
                    mapped.append(
                        MappedFeature(
                            label=feature.label,
                            feature_type=feature.feature_type,
                            start=start,
                            end=start + len(candidate),
                            source=feature.source,
                            strand=strand,
                        )
                    )
                occurrence_count += 1
                start = sequence.find(candidate, start + 1)
        if len(mapped) >= _MAX_FEATURES * 2:
            break

    priority = {"CDS": 0, "gene": 1, "promoter": 2, "polyA_signal": 3}
    mapped.sort(
        key=lambda value: (
            priority.get(value.feature_type, 9),
            value.start,
            -(value.end - value.start),
        )
    )
    return mapped[:_MAX_FEATURES]


def _draw_sequence_track(
    draw: Any,
    *,
    title: str,
    sequence: str | None,
    circular: bool,
    features: tuple[MappedFeature, ...],
    top: int,
    width: int,
    font: Any,
    feature_codes: dict[tuple[str, str, str, int], str],
    digest_sites: tuple[RestrictionSite, ...] = (),
    provenance: tuple[ProvenanceSegment, ...] = (),
    empty_message: str = "",
) -> int:
    left, right = 70, width - 70
    draw.text((left, top), title, fill="#0f172a", font=font)
    if sequence is None:
        box_top = top + 34
        draw.rounded_rectangle((left, box_top, right, box_top + 50), 8, fill="#f8fafc")
        draw.text(
            (left + 14, box_top + 16),
            empty_message[:150],
            fill="#b91c1c",
            font=font,
        )
        return box_top + 50

    topology = "circular" if circular else "linear"
    tick_interval = _nice_tick_interval(len(sequence))
    draw.text(
        (left, top + 20),
        (f"{len(sequence):,} bp, {topology} · scale ticks every {tick_interval:,} bp"),
        fill="#64748b",
        font=font,
    )
    positive_lanes, negative_lanes = _feature_lane_counts(features, sequence, width)
    y = top + 66 + positive_lanes * 24
    draw.line((left, y, right, y), fill="#334155", width=5)
    scale = (right - left) / max(1, len(sequence))
    _draw_scale(draw, left, right, y, len(sequence), scale, tick_interval, font)
    for feature, lane, start_x, end_x in _layout_features(features, sequence, width):
        feature_y = y - 27 - lane * 24 if feature.strand >= 0 else y + 28 + lane * 24
        color = _FEATURE_COLORS.get(feature.feature_type, "#64748b")
        draw.rounded_rectangle(
            (start_x, feature_y, end_x, feature_y + 16), 3, fill=color
        )
        code = feature_codes[_mapped_feature_key(feature)]
        code_box = draw.textbbox((0, 0), code, font=font)
        code_width = code_box[2] - code_box[0]
        midpoint = (start_x + end_x) / 2
        code_x = min(right - code_width, max(left, midpoint - code_width / 2))
        code_y = feature_y - 16 if feature.strand >= 0 else feature_y + 17
        draw.rectangle(
            (code_x - 2, code_y, code_x + code_width + 2, code_y + 14),
            fill="#ffffff",
        )
        draw.text((code_x, code_y), code, fill=color, font=font)

    next_y = top + _sequence_track_height(positive_lanes, negative_lanes)
    if digest_sites:
        _draw_digest_sites(
            draw,
            digest_sites,
            left=left,
            right=right,
            sequence_length=len(sequence),
            axis_y=y,
            label_y=next_y,
            font=font,
        )
        next_y += 30
    if provenance:
        _draw_provenance_track(
            draw,
            provenance,
            left=left,
            right=right,
            sequence_length=len(sequence),
            top=next_y,
            font=font,
        )
        next_y += 26 + len(provenance) * 20
    return next_y


def _draw_scale(
    draw: Any,
    left: int,
    right: int,
    y: int,
    sequence_length: int,
    scale: float,
    interval: int,
    font: Any,
) -> None:
    ticks = list(range(0, sequence_length + 1, interval))
    if not ticks or ticks[-1] != sequence_length:
        ticks.append(sequence_length)
    previous_label_right = float("-inf")
    for position in ticks:
        x = left + position * scale
        draw.line((x, y - 6, x, y + 7), fill="#334155", width=1)
        label = f"{position:,}"
        bounds = draw.textbbox((0, 0), label, font=font)
        label_width = bounds[2] - bounds[0]
        label_x = min(right - label_width, max(left, x - label_width / 2))
        if position not in {0, sequence_length} and label_x < previous_label_right + 8:
            continue
        if position == sequence_length and label_x < previous_label_right + 8:
            draw.rectangle((label_x - 2, y + 8, right + 2, y + 23), fill="#ffffff")
        draw.text((label_x, y + 8), label, fill="#475569", font=font)
        previous_label_right = label_x + label_width


def _nice_tick_interval(sequence_length: int, target_ticks: int = 10) -> int:
    """Return a readable 1/2/5-multiple interval for a bp axis."""
    if sequence_length <= 0:
        return 1
    rough = sequence_length / target_ticks
    magnitude = 10 ** math.floor(math.log10(max(1.0, rough)))
    normalized = rough / magnitude
    multiplier = next(value for value in (1, 2, 5, 10) if normalized <= value)
    return max(1, int(multiplier * magnitude))


def _layout_features(
    features: tuple[MappedFeature, ...], sequence: str, width: int
) -> list[tuple[MappedFeature, int, float, float]]:
    """Assign every mapped feature a non-overlapping annotation lane."""
    left, right = 70, width - 70
    scale = (right - left) / max(1, len(sequence))
    lane_ends: dict[int, list[float]] = {1: [], -1: []}
    layout: list[tuple[MappedFeature, int, float, float]] = []
    for feature in sorted(
        features,
        key=lambda value: (value.start, -(value.end - value.start), value.label),
    ):
        start_x = left + feature.start * scale
        end_x = max(start_x + 2, left + min(feature.end, len(sequence)) * scale)
        occupied_start = min(start_x, (start_x + end_x) / 2 - 12)
        occupied_end = max(end_x, (start_x + end_x) / 2 + 12)
        direction = 1 if feature.strand >= 0 else -1
        lanes = lane_ends[direction]
        lane = next(
            (
                index
                for index, lane_end in enumerate(lanes)
                if occupied_start > lane_end + 8
            ),
            len(lanes),
        )
        if lane == len(lanes):
            lanes.append(occupied_end)
        else:
            lanes[lane] = occupied_end
        layout.append((feature, lane, start_x, end_x))
    return layout


def _feature_lane_counts(
    features: tuple[MappedFeature, ...], sequence: str | None, width: int
) -> tuple[int, int]:
    if not sequence:
        return (0, 0)
    layout = _layout_features(features, sequence, width)
    positive = max(
        (lane + 1 for feature, lane, _, _ in layout if feature.strand >= 0),
        default=0,
    )
    negative = max(
        (lane + 1 for feature, lane, _, _ in layout if feature.strand < 0),
        default=0,
    )
    return positive, negative


def _sequence_track_height(
    positive_lanes: int,
    negative_lanes: int,
    *,
    digest_sites: int = 0,
    provenance_segments: int = 0,
) -> int:
    return (
        101
        + positive_lanes * 24
        + negative_lanes * 24
        + (30 if digest_sites else 0)
        + (26 + provenance_segments * 20 if provenance_segments else 0)
    )


def _draw_digest_sites(
    draw: Any,
    sites: tuple[RestrictionSite, ...],
    *,
    left: int,
    right: int,
    sequence_length: int,
    axis_y: int,
    label_y: int,
    font: Any,
) -> None:
    scale = (right - left) / max(1, sequence_length)
    enzyme_colors = {
        enzyme: _DIGEST_COLORS[index % len(_DIGEST_COLORS)]
        for index, enzyme in enumerate(dict.fromkeys(site.enzyme for site in sites))
    }
    for site in sites:
        x = left + site.motif_start * scale
        color = enzyme_colors[site.enzyme]
        draw.line((x, axis_y - 10, x, label_y + 13), fill=color, width=2)
        label = f"{site.enzyme} {site.motif_start + 1:,}"
        bounds = draw.textbbox((0, 0), label, font=font)
        label_width = bounds[2] - bounds[0]
        label_x = min(right - label_width, max(left, x + 3))
        draw.rectangle(
            (label_x - 2, label_y, label_x + label_width + 2, label_y + 15),
            fill="#ffffff",
        )
        draw.text((label_x, label_y), label, fill=color, font=font)


def _draw_provenance_track(
    draw: Any,
    segments: tuple[ProvenanceSegment, ...],
    *,
    left: int,
    right: int,
    sequence_length: int,
    top: int,
    font: Any,
) -> None:
    draw.text(
        (left, top),
        "Submitted-protocol fragment provenance",
        fill="#0f172a",
        font=font,
    )
    scale = (right - left) / max(1, sequence_length)
    for index, segment in enumerate(segments):
        y = top + 20 + index * 20
        color = _PROVENANCE_COLORS[index % len(_PROVENANCE_COLORS)]
        for start, end in segment.ranges:
            start_x = left + start * scale
            end_x = max(start_x + 2, left + end * scale)
            draw.rounded_rectangle((start_x, y, end_x, y + 12), 2, fill=color)
        label = (
            f"{segment.code}  {', '.join(segment.source_files) or segment.operation}"
        )
        draw.text((left + 4, y - 1), label[:80], fill="#0f172a", font=font)


def _mapped_feature_key(feature: MappedFeature) -> tuple[str, str, str, int]:
    return (
        feature.label,
        feature.feature_type,
        feature.source,
        feature.end - feature.start,
    )


def _legend_key(entry: FeatureLegendEntry) -> tuple[str, str, str, int]:
    return entry.label, entry.feature_type, entry.source, entry.length


def _feature_legend(comparison: SequenceComparison) -> tuple[FeatureLegendEntry, ...]:
    grouped: dict[
        tuple[str, str, str, int],
        dict[str, list[tuple[int, int]] | MappedFeature],
    ] = {}
    for assembly, features in (
        ("predicted", comparison.predicted_features),
        ("reference", comparison.reference_features),
    ):
        for feature in features:
            key = _mapped_feature_key(feature)
            values = grouped.setdefault(
                key,
                {"feature": feature, "predicted": [], "reference": []},
            )
            ranges = cast(list[tuple[int, int]], values[assembly])
            ranges.append((feature.start, feature.end))

    ordered = sorted(
        grouped.values(),
        key=lambda values: (
            min(
                start
                for name in ("predicted", "reference")
                for start, _ in cast(list[tuple[int, int]], values[name])
            ),
            cast(MappedFeature, values["feature"]).label,
        ),
    )
    entries: list[FeatureLegendEntry] = []
    for index, values in enumerate(ordered, start=1):
        feature = cast(MappedFeature, values["feature"])
        entries.append(
            FeatureLegendEntry(
                code=f"F{index}",
                label=feature.label,
                feature_type=feature.feature_type,
                length=feature.end - feature.start,
                source=feature.source,
                predicted_ranges=tuple(
                    cast(list[tuple[int, int]], values["predicted"])
                ),
                reference_ranges=tuple(
                    cast(list[tuple[int, int]], values["reference"])
                ),
            )
        )
    return tuple(entries)


def _draw_feature_legend(
    draw: Any,
    entries: tuple[FeatureLegendEntry, ...],
    *,
    top: int,
    width: int,
    font: Any,
) -> None:
    left = 70
    draw.text((left, top), "Feature key", fill="#0f172a", font=font)
    draw.text(
        (left + 92, top),
        "IDs appear on every colored region; exact coordinates are listed below the image.",
        fill="#64748b",
        font=font,
    )
    rows = math.ceil(len(entries) / 2)
    column_width = (width - 140) / 2
    for index, entry in enumerate(entries):
        column, row = divmod(index, rows)
        x = left + column * column_width
        y = top + 28 + row * 24
        color = _FEATURE_COLORS.get(entry.feature_type, "#64748b")
        draw.rounded_rectangle((x, y + 2, x + 15, y + 15), 2, fill=color)
        text = (
            f"{entry.code}  {entry.label} · {entry.feature_type} · {entry.length:,} bp"
        )
        draw.text((x + 22, y), text[:62], fill="#334155", font=font)


def _draw_difference_track(
    draw: Any, comparison: SequenceComparison, *, y: int, width: int, font: Any
) -> None:
    left, right = 70, width - 70
    draw.text(
        (left, y - 34),
        "Differences on reference coordinates",
        fill="#0f172a",
        font=font,
    )
    draw.line((left, y, right, y), fill="#cbd5e1", width=8)
    if comparison.predicted is None:
        draw.text(
            (left, y + 14),
            "Unavailable without a predicted assembly",
            fill="#64748b",
            font=font,
        )
        return
    scale = (right - left) / max(1, len(comparison.reference))
    colors = {"replace": "#ef4444", "missing": "#f97316", "extra": "#a855f7"}
    for difference in comparison.differences:
        start_x = left + difference.reference_start * scale
        end_x = left + difference.reference_end * scale
        if difference.kind == "extra" or end_x - start_x < _MIN_DIFFERENCE_WIDTH:
            draw.line(
                (start_x, y - 8, start_x, y + 8), fill=colors[difference.kind], width=2
            )
        else:
            draw.line((start_x, y, end_x, y), fill=colors[difference.kind], width=8)
    draw.text(
        (left, y + 18),
        "red: replacement   orange: missing from prediction   purple: extra in prediction",
        fill="#64748b",
        font=font,
    )


def _metric_line(comparison: SequenceComparison) -> str:
    predicted_length = len(comparison.predicted) if comparison.predicted else 0
    similarity = (
        f"{comparison.similarity:.4f}" if comparison.similarity is not None else "n/a"
    )
    return (
        f"predicted: {predicted_length:,} bp   |   reference: "
        f"{len(comparison.reference):,} bp   |   aligned similarity: {similarity}   |   "
        f"difference blocks: {len(comparison.differences)}"
    )


def _comparison_markdown(
    comparison: SequenceComparison,
    encoded_png: str,
    *,
    provenance: tuple[ProvenanceSegment, ...] = (),
    digest: DigestDiagnostic | None = None,
) -> str:
    lines = [
        "### Cloning sequence comparison",
        "",
        f"![Annotated predicted and reference assemblies](data:image/png;base64,{encoded_png})",
        "",
        "| Metric | Predicted | Reference |",
        "| --- | ---: | ---: |",
        (
            f"| Length | {len(comparison.predicted) if comparison.predicted else 'n/a'} bp "
            f"| {len(comparison.reference)} bp |"
        ),
        (
            f"| Topology | {'circular' if comparison.predicted_circular else 'linear or unavailable'} "
            f"| {'circular' if comparison.reference_circular else 'linear'} |"
        ),
        (
            f"| Aligned similarity | {comparison.similarity:.6f} | 1.000000 |"
            if comparison.similarity is not None
            else "| Aligned similarity | n/a | 1.000000 |"
        ),
    ]
    if comparison.prediction_error:
        lines.extend(
            ("", f"**Prediction visualization:** {comparison.prediction_error}")
        )
    if digest:
        lines.extend(_digest_markdown(digest, comparison))
    if provenance:
        lines.extend(
            (
                "",
                "#### Submitted-protocol fragment provenance",
                "",
                (
                    "Coordinates are on the aligned predicted assembly. Overlapping ranges "
                    "are Gibson homology regions contributed by both adjacent PCR products."
                ),
                "",
                "| ID | Operation | Source file(s) | Fragment length | Predicted coordinates | Orientation |",
                "| --- | --- | --- | ---: | --- | --- |",
            )
        )
        for segment in provenance:
            lines.append(
                "| "
                + " | ".join(
                    (
                        segment.code,
                        _markdown_cell(segment.operation),
                        ", ".join(
                            _markdown_cell(value) for value in segment.source_files
                        )
                        or "—",
                        f"{segment.fragment_length:,} bp",
                        _format_feature_ranges(segment.ranges),
                        "+" if segment.strand >= 0 else "−",
                    )
                )
                + " |"
            )
    feature_legend = _feature_legend(comparison)
    if feature_legend:
        lines.extend(
            (
                "",
                "#### Feature key",
                "",
                (
                    "Coordinates are 1-based and inclusive. Feature IDs match the labels "
                    "printed on every colored region in the image."
                ),
                "",
                "| ID | Annotation | Type | Length | Predicted coordinates | Reference coordinates | Source |",
                "| --- | --- | --- | ---: | --- | --- | --- |",
            )
        )
        for entry in feature_legend:
            lines.append(
                "| "
                + " | ".join(
                    (
                        entry.code,
                        _markdown_cell(entry.label),
                        _markdown_cell(entry.feature_type),
                        f"{entry.length:,} bp",
                        _format_feature_ranges(entry.predicted_ranges),
                        _format_feature_ranges(entry.reference_ranges),
                        _markdown_cell(entry.source),
                    )
                )
                + " |"
            )
    if comparison.differences:
        lines.extend(("", "#### First sequence differences", ""))
        for difference in comparison.differences[:_MAX_DIFF_ROWS]:
            predicted = _sequence_window(
                comparison.predicted or "",
                difference.predicted_start,
                difference.predicted_end,
            )
            reference = _sequence_window(
                comparison.reference,
                difference.reference_start,
                difference.reference_end,
            )
            lines.extend(
                (
                    (
                        f"- **{difference.kind}** — predicted "
                        f"`{difference.predicted_start}:{difference.predicted_end}`, reference "
                        f"`{difference.reference_start}:{difference.reference_end}`"
                    ),
                    f"  - predicted: `{predicted}`",
                    f"  - reference: `{reference}`",
                )
            )
    if comparison.predicted:
        lines.extend(
            (
                "",
                "<details><summary>Predicted sequence (FASTA)</summary>",
                "",
                "```text",
                _format_fasta("predicted_assembly", comparison.predicted),
                "```",
                "</details>",
            )
        )
    lines.extend(
        (
            "",
            "<details><summary>Reference sequence (FASTA)</summary>",
            "",
            "```text",
            _format_fasta("reference_assembly", comparison.reference),
            "```",
            "</details>",
        )
    )
    lines.extend(
        (
            "",
            "Annotations are transferred from exact matches to features in the input GenBank files. "
            "The difference display is diagnostic; the benchmark scorer remains authoritative.",
        )
    )
    return "\n".join(lines)


def _digest_markdown(
    digest: DigestDiagnostic,
    comparison: SequenceComparison,
) -> list[str]:
    lines = [
        "",
        "#### Restriction-digest validator diagnostic",
        "",
        (
            f"The scorer digests both assemblies with **{', '.join(digest.enzymes)}**, "
            "sorts the resulting fragments by length, and requires every paired fragment "
            f"to have sequence similarity ≥ {digest.threshold:.2f}."
        ),
        "",
        "| Assembly | Enzyme | Recognition site | Motif coordinates | Cut coordinate |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for assembly, sites in (
        ("Predicted", digest.predicted_sites),
        ("Reference", digest.reference_sites),
    ):
        for site in sites:
            motif_end = site.motif_start + len(site.motif)
            motif_range = f"{site.motif_start + 1:,}–{motif_end:,}"
            lines.append(
                f"| {assembly} | {site.enzyme} | `{site.motif}` | "
                f"{motif_range} | {site.cut_position:,} |"
            )

    expected = ", ".join(f"{value:,}" for value in digest.expected_lengths) or "n/a"
    predicted = ", ".join(f"{value:,}" for value in digest.predicted_lengths)
    loaded = ", ".join(f"{value:,}" for value in digest.reference_lengths_as_loaded)
    circular = ", ".join(f"{value:,}" for value in digest.circular_reference_lengths)
    lines.extend(
        (
            "",
            "| Digest interpretation | Fragment lengths (bp, ascending) |",
            "| --- | --- |",
            f"| Dataset metadata expectation | {expected} |",
            f"| Predicted assembly ({'circular' if comparison.predicted_circular else 'linear'}) | {predicted} |",
            f"| Reference as loaded ({'circular' if comparison.reference_circular else 'linear'}) | {loaded} |",
            f"| Reference forced circular (diagnostic) | {circular} |",
        )
    )
    if digest.topology_mismatch:
        lines.extend(
            (
                "",
                (
                    "**Likely verifier topology error:** the reference FASTA was loaded as "
                    "linear, but the submitted Gibson product is circular and the dataset's "
                    "expected fragment sizes exactly match a circular digest. The current "
                    "scorer therefore compares different fragment counts before sequence "
                    "similarity can be meaningfully evaluated."
                ),
            )
        )
    if digest.circular_reference_pairs:
        lines.extend(
            (
                "",
                "Circular-reference counterfactual:",
                "",
                "| Predicted fragment | Reference fragment | Similarity | Passes threshold? |",
                "| ---: | ---: | ---: | --- |",
            )
        )
        for pair in digest.circular_reference_pairs:
            lines.append(
                f"| {pair.predicted_length:,} bp | {pair.reference_length:,} bp | "
                f"{pair.similarity:.6f} | "
                f"{'yes' if pair.similarity >= digest.threshold else 'no'} |"
            )
    return lines


def _format_feature_ranges(ranges: tuple[tuple[int, int], ...]) -> str:
    if not ranges:
        return "—"
    return ", ".join(f"{start + 1:,}–{end:,}" for start, end in ranges)


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _sequence_window(sequence: str, start: int, end: int, flank: int = 16) -> str:
    left = max(0, start - flank)
    right = min(len(sequence), end + flank)
    value = sequence[left:right]
    if len(value) > _MAX_SEQUENCE_WINDOW:
        value = value[:38] + "..." + value[-38:]
    return value or "∅"


def _format_fasta(name: str, sequence: str) -> str:
    lines = [f">{name}"]
    lines.extend(
        sequence[start : start + _FASTA_LINE_WIDTH]
        for start in range(0, len(sequence), _FASTA_LINE_WIDTH)
    )
    return "\n".join(lines)
