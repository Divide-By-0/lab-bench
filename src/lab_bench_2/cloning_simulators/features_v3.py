"""Feature annotation and circular architecture checks for cloning verifier v3.

The verifier combines two independent sources of evidence:

* annotations transferred from the task's input GenBank files; and
* optional pLannotate calls made with a pinned external installation.

pLannotate is deliberately invoked through its CLI.  It is GPL-licensed and
depends on BLAST/DIAMOND/Infernal plus a separately versioned database bundle,
so it cannot be a silent, in-process dependency of this MIT evaluation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DNA_COMPLEMENT = str.maketrans("ACGTRYMKBDHVN", "TGCAYRKMVHDBN")
_GENBANK_SUFFIXES = {".gb", ".gbk", ".genbank", ".gbff"}
_STRUCTURAL_TYPES = {
    "cds",
    "enhancer",
    "gene",
    "misc_rna",
    "ncrna",
    "polya_signal",
    "promoter",
    "protein_bind",
    "regulatory",
    "rep_origin",
    "rrna",
    "terminator",
    "trna",
}
_TYPE_ALIASES = {
    "origin_of_replication": "rep_origin",
    "origin of replication": "rep_origin",
    "ori": "rep_origin",
    "poly_a_signal": "polya_signal",
    "polyadenylation_signal": "polya_signal",
    "polyadenylation signal": "polya_signal",
}
_CODING_TYPES = {"cds", "gene"}
_TERMINAL_TYPES = {"terminator", "polya_signal"}
_MIN_FEATURE_LENGTH = 12
_MIN_APPROXIMATE_LENGTH = 120
_MIN_APPROXIMATE_IDENTITY = 0.95
_MIN_PLANNOTATE_IDENTITY = 0.9
_MIN_PLANNOTATE_COVERAGE = 0.8
_MAX_OCCURRENCES = 8
_MAX_CASSETTE_DISTANCE = 2_000
_FEATURE_IDENTITY_TOLERANCE = 0.001
_DEFAULT_REPEAT_LENGTH = 50
_MIN_REPEAT_OCCURRENCES = 2


class FeatureAnnotationError(RuntimeError):
    """An annotation backend was requested but could not produce evidence."""


@dataclass(frozen=True)
class FeatureTemplate:
    """One useful feature extracted in genomic orientation from an input file."""

    key: str
    label: str
    feature_type: str
    sequence: str
    strand: int
    source: str


@dataclass(frozen=True)
class FeatureCall:
    """One normalized annotation on a candidate or reference molecule."""

    key: str
    label: str
    feature_type: str
    start: int
    end: int
    span: int
    strand: int
    identity: float
    coverage: float
    source: str

    @property
    def token(self) -> tuple[str, str, int]:
        """Return the identity, type, and orientation used by graph matching."""
        return self.key, self.feature_type, _strand_sign(self.strand)


@dataclass(frozen=True)
class FeatureArchitectureAssessment:
    """Comparison of one candidate feature graph with the reference graph."""

    backend: str
    expected_count: int
    observed_count: int
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    damaged: tuple[str, ...]
    order_matches: bool
    expected_cassettes: tuple[str, ...]
    observed_cassettes: tuple[str, ...]
    minimum_expected: int = 0

    @property
    def evidence_available(self) -> bool:
        """Whether the reference contained enough features for this backend."""
        return self.expected_count >= self.minimum_expected

    @property
    def passes(self) -> bool:
        """Require the same feature multiset, circular order, and cassettes."""
        return bool(
            self.evidence_available
            and not self.missing
            and not self.unexpected
            and not self.damaged
            and self.order_matches
            and self.expected_cassettes == self.observed_cassettes
        )

    @property
    def summary(self) -> str:
        """Return a compact reviewer-facing explanation."""
        if not self.evidence_available:
            return (
                f"{self.backend}: only {self.expected_count} reference features "
                f"(minimum {self.minimum_expected})"
            )
        problems: list[str] = []
        if self.missing:
            problems.append(f"missing reference features {list(self.missing)}")
        if self.unexpected:
            problems.append(f"unexpected features {list(self.unexpected)}")
        if self.damaged:
            problems.append(f"lower-identity/coverage features {list(self.damaged)}")
        if not self.order_matches:
            problems.append(
                "circular order/orientation differs from the reference "
                "(after allowing rotation and whole-molecule reverse complement)"
            )
        if self.expected_cassettes != self.observed_cassettes:
            problems.append(
                "inferred promoter-CDS-terminator/poly(A) relationships differ"
            )
        if problems:
            return f"{self.backend}: " + "; ".join(problems)
        return (
            f"{self.backend} gate passed: {self.observed_count}/"
            f"{self.expected_count} reference features with matching copy count "
            "and circular order/orientation"
        )


@dataclass(frozen=True)
class RepeatAssessment:
    """Whether a candidate introduces a new long direct or inverted repeat."""

    repeat_length: int
    reference_repeat_kmers: int
    observed_repeat_kmers: int
    new_repeat_hashes: tuple[str, ...]

    @property
    def passes(self) -> bool:
        return not self.new_repeat_hashes

    @property
    def summary(self) -> str:
        if self.passes:
            return (
                f"repeat gate passed: 0 new canonical {self.repeat_length}-bp "
                "direct/inverted repeat motifs "
                f"(candidate total {self.observed_repeat_kmers}; "
                f"reference total {self.reference_repeat_kmers})"
            )
        return (
            f"repeat gate failed: {len(self.new_repeat_hashes)} new canonical "
            f"{self.repeat_length}-bp direct/inverted repeat motifs "
            f"(candidate total {self.observed_repeat_kmers}; "
            f"reference total {self.reference_repeat_kmers})"
        )


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def _canonical_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _TYPE_ALIASES.get(normalized, normalized)


def _strand_sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(_DNA_COMPLEMENT)[::-1]


def _feature_label(qualifiers: Mapping[str, Any], fallback: str) -> str:
    for key in ("label", "gene", "product", "note"):
        value = qualifiers.get(key)
        if isinstance(value, list) and value:
            return str(value[0])[:120]
        if isinstance(value, str) and value:
            return value[:120]
    return fallback


def load_feature_templates(base_dir: Path) -> tuple[FeatureTemplate, ...]:
    """Load structural feature sequences from every input GenBank record."""
    from Bio import SeqIO

    templates: dict[tuple[str, str, int], FeatureTemplate] = {}
    for path in sorted(base_dir.iterdir()):
        if path.suffix.lower() not in _GENBANK_SUFFIXES:
            continue
        try:
            records = list(SeqIO.parse(path, "genbank"))  # type: ignore[no-untyped-call]
        except Exception:
            continue
        for record in records:
            for feature in record.features:
                feature_type = _canonical_type(feature.type)
                if feature_type not in _STRUCTURAL_TYPES:
                    continue
                extracted = str(feature.extract(record.seq)).upper()
                if len(extracted) < _MIN_FEATURE_LENGTH:
                    continue
                strand = _strand_sign(feature.location.strand or 0)
                # SeqFeature.extract returns negative-strand features in biological
                # orientation.  Convert them back to the record's genomic orientation
                # so a direct match retains the original strand annotation.
                genomic = _reverse_complement(extracted) if strand < 0 else extracted
                label = _feature_label(feature.qualifiers, feature.type)
                key = f"{feature_type}:{_normalize_text(label)}:{len(genomic)}"
                template = FeatureTemplate(
                    key=key,
                    label=label,
                    feature_type=feature_type,
                    sequence=genomic,
                    strand=strand,
                    source=path.name,
                )
                templates.setdefault((key, genomic, strand), template)
    return tuple(templates.values())


def _exact_locations(sequence: str, query: str, circular: bool) -> list[int]:
    if not sequence or not query or len(query) > len(sequence):
        return []
    search = sequence + sequence[: max(0, len(query) - 1)] if circular else sequence
    locations: list[int] = []
    start = search.find(query)
    while 0 <= start < len(sequence) and len(locations) < _MAX_OCCURRENCES:
        locations.append(start)
        start = search.find(query, start + 1)
    return locations


def _approximate_locations(
    sequence: str, query: str, circular: bool
) -> list[tuple[int, float]]:
    if len(query) < _MIN_APPROXIMATE_LENGTH or len(query) > len(sequence):
        return []
    import edlib  # type: ignore[import-not-found]

    target = sequence + sequence if circular else sequence
    max_edits = max(1, int((1.0 - _MIN_APPROXIMATE_IDENTITY) * len(query)))
    result = edlib.align(query, target, mode="HW", task="locations", k=max_edits)
    distance = int(result.get("editDistance", -1))
    if distance < 0:
        return []
    identity = max(0.0, 1.0 - distance / len(query))
    if identity < _MIN_APPROXIMATE_IDENTITY:
        return []
    locations: list[tuple[int, float]] = []
    for start, end in result.get("locations") or []:
        aligned_length = int(end) - int(start) + 1
        if (
            0 <= int(start) < len(sequence)
            and abs(aligned_length - len(query)) <= max_edits
        ):
            locations.append((int(start), identity))
    return locations[:_MAX_OCCURRENCES]


def map_feature_templates(
    sequence: str,
    templates: Iterable[FeatureTemplate],
    *,
    circular: bool,
) -> tuple[FeatureCall, ...]:
    """Map inherited annotations onto a product, including across its origin."""
    normalized = sequence.upper()
    calls: dict[tuple[str, int, int, int], FeatureCall] = {}
    for template in templates:
        orientations = (
            (template.sequence, template.strand),
            (_reverse_complement(template.sequence), -template.strand),
        )
        for query, strand in dict.fromkeys(orientations):
            exact = _exact_locations(normalized, query, circular)
            approximate = (
                [] if exact else _approximate_locations(normalized, query, circular)
            )
            locations = [(value, 1.0) for value in exact] + approximate
            for start, identity in locations:
                span = len(query)
                end = (start + span) % len(normalized) if circular else start + span
                call = FeatureCall(
                    key=template.key,
                    label=template.label,
                    feature_type=template.feature_type,
                    start=start,
                    end=end,
                    span=span,
                    strand=_strand_sign(strand),
                    identity=identity,
                    coverage=1.0,
                    source=f"input:{template.source}",
                )
                calls.setdefault((call.key, start, end, call.strand), call)
    return tuple(sorted(calls.values(), key=_feature_sort_key))


def _feature_sort_key(feature: FeatureCall) -> tuple[int, int, str, int]:
    return feature.start, -feature.span, feature.key, feature.strand


def _counter_labels(counter: Counter[str]) -> tuple[str, ...]:
    return tuple(
        value if count == 1 else f"{value} x{count}"
        for value, count in sorted(counter.items())
    )


def _damaged_features(
    expected: tuple[FeatureCall, ...], observed: tuple[FeatureCall, ...]
) -> tuple[str, ...]:
    expected_by_key: dict[str, list[FeatureCall]] = {}
    observed_by_key: dict[str, list[FeatureCall]] = {}
    for value in expected:
        expected_by_key.setdefault(value.key, []).append(value)
    for value in observed:
        observed_by_key.setdefault(value.key, []).append(value)
    damaged: Counter[str] = Counter()
    for key in expected_by_key.keys() & observed_by_key.keys():
        expected_calls = sorted(
            expected_by_key[key],
            key=lambda value: (value.identity, value.coverage),
            reverse=True,
        )
        observed_calls = sorted(
            observed_by_key[key],
            key=lambda value: (value.identity, value.coverage),
            reverse=True,
        )
        for expected_call, observed_call in zip(expected_calls, observed_calls):
            if (
                observed_call.identity + _FEATURE_IDENTITY_TOLERANCE
                < expected_call.identity
                or observed_call.coverage + _FEATURE_IDENTITY_TOLERANCE
                < expected_call.coverage
            ):
                damaged[key] += 1
    return _counter_labels(damaged)


def _is_rotation(first: tuple[Any, ...], second: tuple[Any, ...]) -> bool:
    if len(first) != len(second):
        return False
    if not first:
        return True
    return any(
        first == second[offset:] + second[:offset] for offset in range(len(second))
    )


def _order_matches(
    expected: tuple[FeatureCall, ...], observed: tuple[FeatureCall, ...]
) -> bool:
    expected_tokens = tuple(
        feature.token for feature in sorted(expected, key=_feature_sort_key)
    )
    observed_tokens = tuple(
        feature.token for feature in sorted(observed, key=_feature_sort_key)
    )
    if _is_rotation(observed_tokens, expected_tokens):
        return True
    reverse_expected = tuple(
        (key, feature_type, -strand)
        for key, feature_type, strand in reversed(expected_tokens)
    )
    return _is_rotation(observed_tokens, reverse_expected)


def _directional_distance(
    first: FeatureCall, second: FeatureCall, sequence_length: int
) -> int:
    if first.strand < 0:
        return (first.start - (second.start + second.span)) % sequence_length
    return (second.start - (first.start + first.span)) % sequence_length


def _cassette_signatures(
    calls: tuple[FeatureCall, ...], sequence_length: int
) -> tuple[str, ...]:
    if sequence_length <= 0:
        return ()
    signatures: list[str] = []
    for promoter in (value for value in calls if value.feature_type == "promoter"):
        coding = [
            value
            for value in calls
            if value.feature_type in _CODING_TYPES
            and value.strand == promoter.strand
            and 0
            < _directional_distance(promoter, value, sequence_length)
            <= _MAX_CASSETTE_DISTANCE
        ]
        if not coding:
            continue
        cds = min(
            coding,
            key=lambda value: _directional_distance(promoter, value, sequence_length),
        )
        terminals = [
            value
            for value in calls
            if value.feature_type in _TERMINAL_TYPES
            and value.strand == cds.strand
            and 0
            < _directional_distance(cds, value, sequence_length)
            <= _MAX_CASSETTE_DISTANCE
        ]
        if not terminals:
            continue
        terminal = min(
            terminals,
            key=lambda value: _directional_distance(cds, value, sequence_length),
        )
        signatures.append(f"{promoter.key}->{cds.key}->{terminal.key}")
    return tuple(sorted(signatures))


def compare_feature_architecture(
    expected: Iterable[FeatureCall],
    observed: Iterable[FeatureCall],
    *,
    backend: str,
    sequence_length: int,
    minimum_expected: int = 0,
) -> FeatureArchitectureAssessment:
    """Compare feature identity, copy count, circular order, and cassettes."""
    expected_tuple = tuple(sorted(expected, key=_feature_sort_key))
    observed_tuple = tuple(sorted(observed, key=_feature_sort_key))
    expected_counter = Counter(value.key for value in expected_tuple)
    observed_counter = Counter(value.key for value in observed_tuple)
    missing = expected_counter - observed_counter
    unexpected = observed_counter - expected_counter
    return FeatureArchitectureAssessment(
        backend=backend,
        expected_count=len(expected_tuple),
        observed_count=len(observed_tuple),
        missing=_counter_labels(missing),
        unexpected=_counter_labels(unexpected),
        damaged=_damaged_features(expected_tuple, observed_tuple),
        order_matches=(
            _order_matches(expected_tuple, observed_tuple)
            if expected_counter == observed_counter
            else False
        ),
        expected_cassettes=_cassette_signatures(expected_tuple, sequence_length),
        observed_cassettes=_cassette_signatures(observed_tuple, sequence_length),
        minimum_expected=minimum_expected,
    )


def _circular_kmers(sequence: str, length: int) -> tuple[str, ...]:
    normalized = sequence.upper()
    if length <= 0 or len(normalized) < length:
        return ()
    search = normalized + normalized[: length - 1]
    return tuple(search[index : index + length] for index in range(len(normalized)))


def _repeated_kmers(sequence: str, length: int) -> set[str]:
    positions: dict[str, list[int]] = {}
    for index, kmer in enumerate(_circular_kmers(sequence, length)):
        if set(kmer) - set("ACGT"):
            continue
        reverse = _reverse_complement(kmer)
        canonical = min(kmer, reverse)
        positions.setdefault(canonical, []).append(index)
    return {
        kmer
        for kmer, starts in positions.items()
        if len(starts) >= _MIN_REPEAT_OCCURRENCES
        and len(set(starts)) >= _MIN_REPEAT_OCCURRENCES
    }


def compare_repeat_burden(
    candidate: Any,
    reference: Any,
    *,
    repeat_length: int = _DEFAULT_REPEAT_LENGTH,
) -> RepeatAssessment:
    """Reject only long exact repeats not already present in the reference."""
    expected = _repeated_kmers(str(reference.sequence), repeat_length)
    observed = _repeated_kmers(str(candidate.sequence), repeat_length)
    new = observed - expected
    return RepeatAssessment(
        repeat_length=repeat_length,
        reference_repeat_kmers=len(expected),
        observed_repeat_kmers=len(observed),
        new_repeat_hashes=tuple(
            sorted(
                hashlib.sha256(value.encode("ascii")).hexdigest()[:12] for value in new
            )
        ),
    )


def source_feature_assessment(
    candidate: Any, reference: Any, base_dir: Path
) -> FeatureArchitectureAssessment:
    """Compare features inherited from the task's provided GenBank records."""
    templates = load_feature_templates(base_dir)
    expected = map_feature_templates(
        str(reference.sequence), templates, circular=bool(reference.is_circular)
    )
    observed = map_feature_templates(
        str(candidate.sequence), templates, circular=bool(candidate.is_circular)
    )
    return compare_feature_architecture(
        expected,
        observed,
        backend="input GenBank",
        sequence_length=len(str(reference.sequence)),
        minimum_expected=0,
    )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_plannotate_csv(path: Path) -> tuple[FeatureCall, ...]:
    """Normalize pLannotate's public CSV output into verifier feature calls."""
    calls: dict[tuple[str, int, int, int], FeatureCall] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if _parse_bool(row.get("fragment", "")):
                continue
            feature_type = _canonical_type(row.get("Type", ""))
            if feature_type not in _STRUCTURAL_TYPES:
                continue
            span = int(_parse_float(row.get("length of found feature", "0")))
            identity = _parse_float(row.get("percent identity", "0")) / 100.0
            coverage = _parse_float(row.get("percent match length", "0")) / 100.0
            if (
                span < _MIN_FEATURE_LENGTH
                or identity < _MIN_PLANNOTATE_IDENTITY
                or coverage < _MIN_PLANNOTATE_COVERAGE
            ):
                continue
            start = int(_parse_float(row.get("start location", "0")))
            end = int(_parse_float(row.get("end location", "0")))
            strand = _strand_sign(int(_parse_float(row.get("strand", "0"))))
            database = row.get("database", "unknown")
            identifier = row.get("sseqid", "unknown")
            label = row.get("Feature", "") or identifier
            key = (
                f"{feature_type}:{_normalize_text(database)}:"
                f"{_normalize_text(identifier)}"
            )
            call = FeatureCall(
                key=key,
                label=label,
                feature_type=feature_type,
                start=start,
                end=end,
                span=span,
                strand=strand,
                identity=identity,
                coverage=coverage,
                source=f"pLannotate:{database}",
            )
            calls.setdefault((key, start, end, strand), call)
    return tuple(sorted(calls.values(), key=_feature_sort_key))


class PlannotateAnnotator:
    """Batch and cache pLannotate annotations through a configured executable."""

    def __init__(
        self,
        executable: Path | str,
        *,
        fast: bool = True,
        cores: int = 2,
        timeout_seconds: float = 180.0,
    ) -> None:
        self.executable = Path(executable).expanduser().resolve()
        self.fast = fast
        self.cores = cores
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, tuple[FeatureCall, ...]] = {}
        if not self.executable.is_file():
            raise FeatureAnnotationError(
                f"pLannotate executable not found: {self.executable}"
            )

    @staticmethod
    def _cache_key(sequence: str, circular: bool) -> str:
        digest = hashlib.sha256(sequence.upper().encode("ascii")).hexdigest()
        return f"{'circular' if circular else 'linear'}:{digest}"

    def manifest(self) -> dict[str, Any]:
        """Return pLannotate and database provenance reported by the executable."""
        environment = self._environment()
        version = self._run((str(self.executable), "--version"), environment)
        databases = self._run(
            (str(self.executable), "databases"), environment, check=False
        )
        try:
            database_manifest: Any = json.loads(databases.stdout)
        except json.JSONDecodeError:
            database_manifest = {"unparsed": databases.stdout.strip()}
        return {
            "executable": str(self.executable),
            "version": version.stdout.strip(),
            "databases": database_manifest,
            "fast": self.fast,
            "cores": self.cores,
        }

    def annotate_many(
        self, records: Mapping[str, tuple[str, bool]]
    ) -> dict[str, tuple[FeatureCall, ...]]:
        """Annotate all cache misses in one pLannotate batch invocation."""
        output: dict[str, tuple[FeatureCall, ...]] = {}
        misses: dict[str, tuple[str, bool]] = {}
        keys: dict[str, str] = {}
        for name, (sequence, circular) in records.items():
            cache_key = self._cache_key(sequence, circular)
            keys[name] = cache_key
            if cache_key in self._cache:
                output[name] = self._cache[cache_key]
            else:
                misses[name] = (sequence, circular)
        if not misses:
            return output
        if len({circular for _, circular in misses.values()}) != 1:
            raise FeatureAnnotationError(
                "pLannotate batches cannot mix circular and linear molecules"
            )

        with tempfile.TemporaryDirectory(prefix="labbench-plannotate-") as raw_dir:
            work_dir = Path(raw_dir)
            fasta = work_dir / "sequences.fa"
            with fasta.open("w", encoding="utf-8") as handle:
                for index, (name, (sequence, _)) in enumerate(misses.items()):
                    handle.write(
                        f">seq_{index}_{_normalize_text(name)}\n{sequence.upper()}\n"
                    )
            command = [
                str(self.executable),
                "batch",
                "--input",
                str(fasta),
                "--output",
                str(work_dir),
                "--file-name",
                "hybrid",
                "--suffix",
                "",
                "--csv",
                "--no-gbk",
                "--cores",
                str(self.cores),
            ]
            if self.fast:
                command.append("--fast")
            if not next(iter(misses.values()))[1]:
                command.append("--linear")
            result = self._run(tuple(command), self._environment(), check=False)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()[-2_000:]
                raise FeatureAnnotationError(
                    f"pLannotate failed with exit {result.returncode}: {detail}"
                )
            csv_outputs = sorted(work_dir.glob("*.csv"))
            for index, name in enumerate(misses):
                csv_path = work_dir / f"hybrid_seq_{index}_{_normalize_text(name)}.csv"
                # pLannotate emits ``hybrid.csv`` for a single-record GenBank
                # input, while multi-record FASTA batches use per-record
                # filenames. Accept both output shapes.
                if not csv_path.is_file() and len(misses) == 1 and csv_outputs:
                    csv_path = csv_outputs[0]
                if not csv_path.is_file():
                    raise FeatureAnnotationError(
                        f"pLannotate did not create expected output: {csv_path.name}"
                    )
                calls = parse_plannotate_csv(csv_path)
                self._cache[keys[name]] = calls
                output[name] = calls
        return output

    def _environment(self) -> dict[str, str]:
        executable_dir = str(self.executable.parent)
        return {
            **os.environ,
            "PATH": executable_dir + os.pathsep + os.environ.get("PATH", ""),
        }

    def _run(
        self,
        command: tuple[str, ...],
        environment: Mapping[str, str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                check=check,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=dict(environment),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise FeatureAnnotationError(f"Could not run pLannotate: {exc}") from exc


def plannotate_assessments(
    candidates: Iterable[Any],
    reference: Any,
    annotator: PlannotateAnnotator,
) -> tuple[FeatureArchitectureAssessment, ...]:
    """Annotate the reference and candidates once, then compare each graph."""
    candidate_tuple = tuple(candidates)
    records = {
        "reference": (str(reference.sequence), bool(reference.is_circular)),
        **{
            f"candidate_{index}": (
                str(candidate.sequence),
                bool(candidate.is_circular),
            )
            for index, candidate in enumerate(candidate_tuple)
        },
    }
    annotations = annotator.annotate_many(records)
    expected = annotations["reference"]
    return tuple(
        compare_feature_architecture(
            expected,
            annotations[f"candidate_{index}"],
            backend="pLannotate",
            sequence_length=len(str(reference.sequence)),
            minimum_expected=1,
        )
        for index in range(len(candidate_tuple))
    )
