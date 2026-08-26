"""Compact cloning-assembly visualizations for the Inspect transcript."""

from __future__ import annotations

import base64
import io
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
_MAX_LABELED_FEATURE_LANE = 2
_MIN_FEATURE_LABEL_WIDTH = 18
_MIN_DIFFERENCE_WIDTH = 2
_MAX_SEQUENCE_WINDOW = 80
_FASTA_LINE_WIDTH = 80
_DNA_COMPLEMENT = str.maketrans("ACGTRYMKBDHVN", "TGCAYRKMVHDBN")


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


async def cloning_comparison_markdown(
    answer: str,
    base_dir: Path,
    reference_path: Path,
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

    if PROTOCOL_TAG_OPEN not in answer or PROTOCOL_TAG_CLOSE not in answer:
        prediction_error = "No executable protocol was submitted."
    else:
        try:
            expression = extract_between_tags(
                answer, PROTOCOL_TAG_OPEN, PROTOCOL_TAG_CLOSE
            )
            results = await CloningProtocol(expression).run(base_dir)
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
    png = render_comparison_png(comparison)
    encoded = base64.b64encode(png).decode("ascii")
    return _comparison_markdown(comparison, encoded)


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


def render_comparison_png(comparison: SequenceComparison) -> bytes:
    """Render a compact PNG that Inspect can display inside an Info event."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1200, 560
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=14)
    bold = ImageFont.load_default(size=20)

    draw.text((48, 28), "Cloning assembly comparison", fill="#0f172a", font=bold)
    metrics = _metric_line(comparison)
    draw.text((48, 50), metrics, fill="#475569", font=font)

    _draw_sequence_track(
        draw,
        title="Predicted assembly",
        sequence=comparison.predicted,
        circular=comparison.predicted_circular,
        features=comparison.predicted_features,
        y=180,
        width=width,
        font=font,
        empty_message=comparison.prediction_error or "No predicted assembly",
    )
    _draw_sequence_track(
        draw,
        title="Reference assembly",
        sequence=comparison.reference,
        circular=comparison.reference_circular,
        features=comparison.reference_features,
        y=365,
        width=width,
        font=font,
    )
    _draw_difference_track(draw, comparison, y=480, width=width, font=font)

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
    y: int,
    width: int,
    font: Any,
    empty_message: str = "",
) -> None:
    left, right = 70, width - 70
    draw.text((left, y - 95), title, fill="#0f172a", font=font)
    if sequence is None:
        draw.rounded_rectangle((left, y - 22, right, y + 28), 8, fill="#f8fafc")
        draw.text((left + 14, y - 6), empty_message[:150], fill="#b91c1c", font=font)
        return

    topology = "circular" if circular else "linear"
    draw.text(
        (left, y - 80),
        f"{len(sequence):,} bp, {topology}",
        fill="#64748b",
        font=font,
    )
    draw.line((left, y, right, y), fill="#334155", width=5)
    lane_ends = {
        1: [float(left - 1), float(left - 1), float(left - 1)],
        -1: [float(left - 1), float(left - 1), float(left - 1)],
    }
    scale = (right - left) / max(1, len(sequence))
    for feature in features:
        start_x = left + feature.start * scale
        end_x = max(start_x + 2, left + min(feature.end, len(sequence)) * scale)
        direction = 1 if feature.strand >= 0 else -1
        available_lanes = lane_ends[direction]
        lane = next(
            (
                index
                for index, lane_end in enumerate(available_lanes)
                if start_x > lane_end + 8
            ),
            None,
        )
        if lane is None:
            continue
        available_lanes[lane] = end_x
        feature_y = y - 23 - lane * 22 if feature.strand >= 0 else y + 9 + lane * 22
        color = _FEATURE_COLORS.get(feature.feature_type, "#64748b")
        draw.rounded_rectangle(
            (start_x, feature_y, end_x, feature_y + 14), 3, fill=color
        )
        if (
            lane < _MAX_LABELED_FEATURE_LANE
            and end_x - start_x >= _MIN_FEATURE_LABEL_WIDTH
        ):
            draw.text(
                (start_x, feature_y - 15),
                feature.label[:24],
                fill="#334155",
                font=font,
            )


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


def _comparison_markdown(comparison: SequenceComparison, encoded_png: str) -> str:
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
