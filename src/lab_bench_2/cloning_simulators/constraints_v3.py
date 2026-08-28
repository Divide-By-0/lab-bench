"""Deterministic construct constraints for cloning verifier v3.

The reference sequence is one possible construct, not the definition of a valid
answer.  This module evaluates scorer-owned constraints describing required
modules, copy ranges, meaningful order, and explicitly requested fusions.
Annotations are evidence providers: direct DNA/protein matches from input
GenBank features take priority, with pLannotate calls used as a deterministic
fallback when a module has no sequence template.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from lab_bench_2.cloning_simulators.features_v3 import (
    FeatureCall,
    FeatureTemplate,
    map_feature_templates,
)

MatchMode = Literal["dna", "protein", "either", "annotation"]
TopologyConstraint = Literal["circular", "linear", "any"]

_GENBANK_SUFFIXES = {".gb", ".gbk", ".genbank", ".gbff"}
_DNA_COMPLEMENT = str.maketrans("ACGTRYMKBDHVN", "TGCAYRKMVHDBN")
_MAX_MODULE_OCCURRENCES = 32
_MIN_ORDERED_MODULES = 2
_MIN_SEQUENCE_LENGTH = 3
_PLACEMENT_START_TOLERANCE = 3
_PLACEMENT_OVERLAP_THRESHOLD = 0.8


class ConstraintSpecError(ValueError):
    """A scorer-owned construct specification is invalid."""


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def _reverse_complement(sequence: str) -> str:
    return sequence.upper().translate(_DNA_COMPLEMENT)[::-1]


def _tuple_of_strings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return tuple(str(item) for item in value)
    raise ConstraintSpecError(f"Expected a string or list of strings, got {value!r}")


@dataclass(frozen=True)
class SourceFeatureSelector:
    """Select one or more annotated features from task input GenBank files."""

    files: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    feature_types: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceFeatureSelector:
        return cls(
            files=_tuple_of_strings(value.get("files") or value.get("file")),
            labels=_tuple_of_strings(value.get("labels") or value.get("label")),
            feature_types=tuple(
                item.lower()
                for item in _tuple_of_strings(
                    value.get("feature_types") or value.get("feature_type")
                )
            ),
        )

    def matches(self, template: ConstraintTemplate) -> bool:
        normalized_files = {_normalize(Path(value).stem) for value in self.files}
        normalized_labels = {_normalize(value) for value in self.labels}
        return bool(
            (
                not normalized_files
                or _normalize(Path(template.source).stem) in normalized_files
            )
            and (
                not normalized_labels or _normalize(template.label) in normalized_labels
            )
            and (
                not self.feature_types
                or template.feature_type.lower() in self.feature_types
            )
        )


@dataclass(frozen=True)
class ModuleConstraint:
    """One functional module and its permitted copy range."""

    id: str
    description: str
    source_features: tuple[SourceFeatureSelector, ...] = ()
    annotation_aliases: tuple[str, ...] = ()
    feature_types: tuple[str, ...] = ()
    dna_sequences: tuple[str, ...] = ()
    protein_sequences: tuple[str, ...] = ()
    match: MatchMode = "either"
    allow_missing_initial_methionine: bool = False
    min_copies: int = 1
    max_copies: int | None = 1

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ModuleConstraint:
        identifier = str(value.get("id") or "").strip()
        if not identifier:
            raise ConstraintSpecError("Every module needs a non-empty id")
        match = str(value.get("match", "either")).lower()
        if match not in {"dna", "protein", "either", "annotation"}:
            raise ConstraintSpecError(
                f"Module {identifier!r} has unsupported match mode {match!r}"
            )
        minimum = int(value.get("min_copies", value.get("copies", 1)))
        raw_maximum = value.get("max_copies", value.get("copies", 1))
        maximum = None if raw_maximum is None else int(raw_maximum)
        if minimum < 0 or (maximum is not None and maximum < minimum):
            raise ConstraintSpecError(
                f"Module {identifier!r} has invalid copy range {minimum}..{maximum}"
            )
        selectors = value.get("source_features") or ()
        if isinstance(selectors, Mapping):
            selectors = (selectors,)
        return cls(
            id=identifier,
            description=str(value.get("description") or identifier),
            source_features=tuple(
                SourceFeatureSelector.from_mapping(item) for item in selectors
            ),
            annotation_aliases=_tuple_of_strings(value.get("annotation_aliases")),
            feature_types=tuple(
                item.lower() for item in _tuple_of_strings(value.get("feature_types"))
            ),
            dna_sequences=tuple(
                re.sub(r"\s+", "", item).upper()
                for item in _tuple_of_strings(value.get("dna_sequences"))
            ),
            protein_sequences=tuple(
                re.sub(r"\s+", "", item).upper().rstrip("*")
                for item in _tuple_of_strings(value.get("protein_sequences"))
            ),
            match=match,  # type: ignore[arg-type]
            allow_missing_initial_methionine=bool(
                value.get("allow_missing_initial_methionine", False)
            ),
            min_copies=minimum,
            max_copies=maximum,
        )


@dataclass(frozen=True)
class OrderConstraint:
    """A meaningful partial order; unrelated modules are deliberately absent."""

    modules: tuple[str, ...]
    same_strand: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | Iterable[str]) -> OrderConstraint:
        if isinstance(value, Mapping):
            modules = _tuple_of_strings(value.get("modules"))
            same_strand = bool(value.get("same_strand", True))
        else:
            modules = _tuple_of_strings(value)
            same_strand = True
        if len(modules) < _MIN_ORDERED_MODULES:
            raise ConstraintSpecError("An ordered chain needs at least two modules")
        return cls(modules=modules, same_strand=same_strand)


@dataclass(frozen=True)
class FusionConstraint:
    """An explicitly requested in-frame fusion between two modules."""

    left: str
    right: str
    max_linker_bp: int = 30
    require_in_frame: bool = True
    no_internal_stops: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FusionConstraint:
        left = str(value.get("left") or "")
        right = str(value.get("right") or "")
        if not left or not right:
            raise ConstraintSpecError("A fusion needs left and right module ids")
        return cls(
            left=left,
            right=right,
            max_linker_bp=int(value.get("max_linker_bp", 30)),
            require_in_frame=bool(value.get("require_in_frame", True)),
            no_internal_stops=bool(value.get("no_internal_stops", True)),
        )


@dataclass(frozen=True)
class ConstructSpec:
    """Complete deterministic truth for one acceptable construct family."""

    name: str
    topology: TopologyConstraint
    modules: tuple[ModuleConstraint, ...]
    ordered: tuple[OrderConstraint, ...] = ()
    fusions: tuple[FusionConstraint, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ConstructSpec:
        topology = str(value.get("topology", "circular")).lower()
        if topology not in {"circular", "linear", "any"}:
            raise ConstraintSpecError(f"Unsupported topology {topology!r}")
        modules = tuple(
            ModuleConstraint.from_mapping(item) for item in value.get("modules", ())
        )
        if not modules:
            raise ConstraintSpecError("A construct specification needs modules")
        identifiers = [module.id for module in modules]
        if len(set(identifiers)) != len(identifiers):
            raise ConstraintSpecError("Module ids must be unique")
        ordered = tuple(
            OrderConstraint.from_mapping(item) for item in value.get("ordered", ())
        )
        fusions = tuple(
            FusionConstraint.from_mapping(item) for item in value.get("fusions", ())
        )
        referenced = {module for relation in ordered for module in relation.modules} | {
            module for fusion in fusions for module in (fusion.left, fusion.right)
        }
        missing = referenced - set(identifiers)
        if missing:
            raise ConstraintSpecError(
                f"Relationships reference unknown modules: {sorted(missing)}"
            )
        return cls(
            name=str(value.get("name") or "construct constraints"),
            topology=topology,  # type: ignore[arg-type]
            modules=modules,
            ordered=ordered,
            fusions=fusions,
        )

    def metadata(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConstraintTemplate:
    """Sequence evidence extracted from one annotated input feature."""

    label: str
    feature_type: str
    dna: str
    protein: str | None
    source: str


@dataclass(frozen=True)
class ModuleAssessment:
    id: str
    description: str
    observed_copies: int
    min_copies: int
    max_copies: int | None
    calls: tuple[FeatureCall, ...]
    evidence: str

    @property
    def passes(self) -> bool:
        return bool(
            self.observed_copies >= self.min_copies
            and (self.max_copies is None or self.observed_copies <= self.max_copies)
        )

    @property
    def summary(self) -> str:
        expected = (
            f">={self.min_copies}"
            if self.max_copies is None
            else str(self.min_copies)
            if self.min_copies == self.max_copies
            else f"{self.min_copies}..{self.max_copies}"
        )
        state = "pass" if self.passes else "FAIL"
        return (
            f"{self.description}: {self.observed_copies} complete copies "
            f"(expected {expected}; {self.evidence}; {state})"
        )


@dataclass(frozen=True)
class RelationshipAssessment:
    kind: str
    modules: tuple[str, ...]
    passes: bool
    detail: str


@dataclass(frozen=True)
class ConstructConstraintAssessment:
    name: str
    topology: str
    topology_pass: bool
    modules: tuple[ModuleAssessment, ...]
    relationships: tuple[RelationshipAssessment, ...]

    @property
    def passes(self) -> bool:
        return bool(
            self.topology_pass
            and all(module.passes for module in self.modules)
            and all(relation.passes for relation in self.relationships)
        )

    @property
    def summary(self) -> str:
        if self.passes:
            return (
                f"construct constraints passed: {len(self.modules)} module copy "
                f"constraints and {len(self.relationships)} explicit relationships"
            )
        problems = [module.summary for module in self.modules if not module.passes]
        problems.extend(
            relation.detail for relation in self.relationships if not relation.passes
        )
        if not self.topology_pass:
            problems.insert(0, f"required {self.topology} topology")
        return "construct constraints failed: " + "; ".join(problems)

    def metadata(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "passes": self.passes,
            "modules": [
                {
                    **asdict(module),
                    "passes": module.passes,
                    "calls": [asdict(call) for call in module.calls],
                }
                for module in self.modules
            ],
        }


def _feature_label(feature: Any) -> str:
    for key in ("label", "gene", "product", "note"):
        value = feature.qualifiers.get(key)
        if isinstance(value, list) and value:
            return str(value[0])[:120]
        if isinstance(value, str) and value:
            return value[:120]
    return str(feature.type)


def _translated_feature(feature: Any, biological_dna: str) -> str | None:
    if str(feature.type).lower() != "cds":
        return None
    translation = feature.qualifiers.get("translation")
    if isinstance(translation, list) and translation:
        return re.sub(r"\s+", "", str(translation[0])).upper().rstrip("*")
    if isinstance(translation, str) and translation:
        return re.sub(r"\s+", "", translation).upper().rstrip("*")
    from Bio.Seq import Seq

    codon_start = int((feature.qualifiers.get("codon_start") or [1])[0]) - 1
    dna = biological_dna[codon_start:]
    dna = dna[: len(dna) - len(dna) % 3]
    if not dna:
        return None
    return str(Seq(dna).translate()).upper().rstrip("*")  # type: ignore[no-untyped-call]


def load_constraint_templates(base_dir: Path) -> tuple[ConstraintTemplate, ...]:
    """Load all annotated features, including IRES/misc features, from inputs."""
    from Bio import SeqIO

    templates: dict[tuple[str, str, str, str], ConstraintTemplate] = {}
    for path in sorted(base_dir.iterdir()):
        if path.suffix.lower() not in _GENBANK_SUFFIXES:
            continue
        try:
            records = list(SeqIO.parse(path, "genbank"))  # type: ignore[no-untyped-call]
        except Exception:
            continue
        for record in records:
            for feature in record.features:
                biological_dna = str(feature.extract(record.seq)).upper()
                if len(biological_dna) < _MIN_SEQUENCE_LENGTH:
                    continue
                label = _feature_label(feature)
                template = ConstraintTemplate(
                    label=label,
                    feature_type=str(feature.type).lower(),
                    dna=biological_dna,
                    protein=_translated_feature(feature, biological_dna),
                    source=path.name,
                )
                templates.setdefault(
                    (
                        template.label,
                        template.feature_type,
                        template.dna,
                        template.source,
                    ),
                    template,
                )
    return tuple(templates.values())


def _protein_calls(
    sequence: str,
    peptide: str,
    *,
    circular: bool,
    label: str,
    feature_type: str,
    source: str,
) -> tuple[FeatureCall, ...]:
    """Find exact translated peptide occurrences on both DNA strands."""
    from Bio.Seq import Seq

    normalized = sequence.upper()
    peptide = peptide.upper().rstrip("*")
    if not peptide or len(normalized) < len(peptide) * 3:
        return ()
    span = len(peptide) * 3
    calls: dict[tuple[int, int], FeatureCall] = {}
    for strand, oriented in ((1, normalized), (-1, _reverse_complement(normalized))):
        search = oriented + oriented[: span + 2] if circular else oriented
        for frame in range(3):
            coding = search[frame:]
            coding = coding[: len(coding) - len(coding) % 3]
            translated = str(Seq(coding).translate()).upper()  # type: ignore[no-untyped-call]
            offset = translated.find(peptide)
            found = 0
            while offset >= 0 and found < _MAX_MODULE_OCCURRENCES:
                oriented_start = frame + offset * 3
                if oriented_start >= len(normalized):
                    break
                start = (
                    oriented_start
                    if strand > 0
                    else (len(normalized) - oriented_start - span) % len(normalized)
                )
                end = (start + span) % len(normalized) if circular else start + span
                calls[(start, strand)] = FeatureCall(
                    key=f"constraint:{_normalize(label)}",
                    label=label,
                    feature_type=feature_type,
                    start=start,
                    end=end,
                    span=span,
                    strand=strand,
                    identity=1.0,
                    coverage=1.0,
                    source=source,
                )
                found += 1
                offset = translated.find(peptide, offset + 1)
    return tuple(calls.values())


def _dna_calls(
    sequence: str,
    dna: str,
    *,
    circular: bool,
    label: str,
    feature_type: str,
    source: str,
) -> tuple[FeatureCall, ...]:
    template = FeatureTemplate(
        key=f"constraint:{_normalize(label)}:{len(dna)}",
        label=label,
        feature_type=feature_type,
        sequence=dna.upper(),
        strand=1,
        source=source,
    )
    return map_feature_templates(sequence, (template,), circular=circular)


def _overlap_fraction(first: FeatureCall, second: FeatureCall) -> float:
    if first.strand != second.strand:
        return 0.0
    first_end = first.start + first.span
    second_end = second.start + second.span
    overlap = max(0, min(first_end, second_end) - max(first.start, second.start))
    return overlap / max(1, min(first.span, second.span))


def _deduplicate_calls(calls: Iterable[FeatureCall]) -> tuple[FeatureCall, ...]:
    selected: list[FeatureCall] = []
    for call in sorted(
        calls,
        key=lambda value: (
            value.start,
            -value.identity,
            -value.coverage,
            -value.span,
        ),
    ):
        duplicate = next(
            (
                existing
                for existing in selected
                if abs(existing.start - call.start) <= _PLACEMENT_START_TOLERANCE
                or _overlap_fraction(existing, call) >= _PLACEMENT_OVERLAP_THRESHOLD
            ),
            None,
        )
        if duplicate is None:
            selected.append(call)
    return tuple(sorted(selected, key=lambda value: (value.start, value.strand)))


def _annotation_matches(call: FeatureCall, module: ModuleConstraint) -> bool:
    aliases = {_normalize(value) for value in module.annotation_aliases}
    if not aliases:
        return False
    normalized_label = _normalize(call.label)
    normalized_key = _normalize(call.key)
    return bool(
        (not module.feature_types or call.feature_type.lower() in module.feature_types)
        and (
            normalized_label in aliases
            or any(alias in normalized_key for alias in aliases)
        )
    )


def _module_assessment(
    module: ModuleConstraint,
    templates: tuple[ConstraintTemplate, ...],
    sequence: str,
    circular: bool,
    annotation_calls: tuple[FeatureCall, ...],
) -> ModuleAssessment:
    # GenBank files often contain several nested annotations with the same
    # label (for example a full IRES plus 3-bp boundary fragments). For each
    # accepted selector/feature identity, use only the longest annotation as
    # the module template; short nested annotations are not extra copies.
    selected_by_identity: dict[tuple[str, str, str], ConstraintTemplate] = {}
    for selector in module.source_features:
        for template in templates:
            if not selector.matches(template):
                continue
            identity = (
                _normalize(Path(template.source).stem),
                _normalize(template.label),
                template.feature_type,
            )
            previous = selected_by_identity.get(identity)
            if previous is None or len(template.dna) > len(previous.dna):
                selected_by_identity[identity] = template
    selected_templates = tuple(selected_by_identity.values())
    direct: list[FeatureCall] = []
    for template in selected_templates:
        if module.match in {"protein", "either"} and template.protein:
            peptides = [template.protein]
            if (
                module.allow_missing_initial_methionine
                and template.protein.startswith("M")
                and len(template.protein) > 1
            ):
                peptides.append(template.protein[1:])
            for peptide_index, peptide in enumerate(peptides):
                suffix = ":without-initial-methionine" if peptide_index else ""
                direct.extend(
                    _protein_calls(
                        sequence,
                        peptide,
                        circular=circular,
                        label=template.label,
                        feature_type=template.feature_type,
                        source=f"protein:{template.source}{suffix}",
                    )
                )
        elif module.match in {"dna", "either"}:
            direct.extend(
                _dna_calls(
                    sequence,
                    template.dna,
                    circular=circular,
                    label=template.label,
                    feature_type=template.feature_type,
                    source=f"dna:{template.source}",
                )
            )
    for index, dna in enumerate(module.dna_sequences, start=1):
        direct.extend(
            _dna_calls(
                sequence,
                dna,
                circular=circular,
                label=module.description,
                feature_type=module.feature_types[0]
                if module.feature_types
                else "sequence",
                source=f"inline-dna:{module.id}:{index}",
            )
        )
    for index, peptide in enumerate(module.protein_sequences, start=1):
        peptides = [peptide]
        if (
            module.allow_missing_initial_methionine
            and peptide.startswith("M")
            and len(peptide) > 1
        ):
            peptides.append(peptide[1:])
        for peptide_index, accepted_peptide in enumerate(peptides):
            suffix = ":without-initial-methionine" if peptide_index else ""
            direct.extend(
                _protein_calls(
                    sequence,
                    accepted_peptide,
                    circular=circular,
                    label=module.description,
                    feature_type=(
                        module.feature_types[0] if module.feature_types else "cds"
                    ),
                    source=f"inline-protein:{module.id}:{index}{suffix}",
                )
            )
    direct_calls = _deduplicate_calls(direct)
    if direct_calls:
        calls = direct_calls
        evidence = "direct DNA/protein sequence evidence"
    else:
        calls = _deduplicate_calls(
            call for call in annotation_calls if _annotation_matches(call, module)
        )
        evidence = "pLannotate evidence" if calls else "no matching evidence"
    return ModuleAssessment(
        id=module.id,
        description=module.description,
        observed_copies=len(calls),
        min_copies=module.min_copies,
        max_copies=module.max_copies,
        calls=calls,
        evidence=evidence,
    )


def _directional_offset(anchor: FeatureCall, value: FeatureCall, length: int) -> int:
    if anchor.strand < 0:
        return (anchor.start - value.start) % length
    return (value.start - anchor.start) % length


def _assess_order(
    constraint: OrderConstraint,
    modules: Mapping[str, ModuleAssessment],
    sequence_length: int,
) -> RelationshipAssessment:
    call_sets = [modules[module].calls for module in constraint.modules]
    if any(not calls for calls in call_sets):
        return RelationshipAssessment(
            kind="ordered",
            modules=constraint.modules,
            passes=False,
            detail=(
                "ordered relationship could not be checked because a module is "
                f"missing: {' -> '.join(constraint.modules)}"
            ),
        )
    passes = False
    for calls in itertools.product(*call_sets):
        if constraint.same_strand and len({call.strand for call in calls}) != 1:
            continue
        offsets = tuple(
            _directional_offset(calls[0], call, sequence_length) for call in calls
        )
        if offsets[0] == 0 and all(
            first < second for first, second in itertools.pairwise(offsets)
        ):
            passes = True
            break
    detail = (
        f"ordered modules {' -> '.join(constraint.modules)}"
        if passes
        else f"required module order not found: {' -> '.join(constraint.modules)}"
    )
    return RelationshipAssessment("ordered", constraint.modules, passes, detail)


def _gap(left: FeatureCall, right: FeatureCall, length: int) -> int:
    if left.strand < 0:
        return (left.start - (right.start + right.span)) % length
    return (right.start - (left.start + left.span)) % length


def _oriented_region(
    sequence: str, left: FeatureCall, right: FeatureCall, gap: int
) -> str:
    span = left.span + gap + right.span
    if left.strand < 0:
        start = right.start
        raw = (sequence + sequence)[start : start + span]
        return _reverse_complement(raw)
    raw = (sequence + sequence)[left.start : left.start + span]
    return raw


def _assess_fusion(
    constraint: FusionConstraint,
    modules: Mapping[str, ModuleAssessment],
    sequence: str,
) -> RelationshipAssessment:
    from Bio.Seq import Seq

    left_calls = modules[constraint.left].calls
    right_calls = modules[constraint.right].calls
    passes = False
    for left, right in itertools.product(left_calls, right_calls):
        if left.strand != right.strand:
            continue
        gap = _gap(left, right, len(sequence))
        if gap > constraint.max_linker_bp:
            continue
        if constraint.require_in_frame and gap % 3:
            continue
        if constraint.no_internal_stops:
            region = _oriented_region(sequence, left, right, gap)
            region = region[: len(region) - len(region) % 3]
            protein = str(Seq(region).translate())  # type: ignore[no-untyped-call]
            if "*" in protein[:-1]:
                continue
        passes = True
        break
    modules_tuple = (constraint.left, constraint.right)
    detail = (
        f"in-frame fusion {constraint.left} -> {constraint.right}"
        if passes
        else (
            f"required in-frame fusion not found: {constraint.left} -> "
            f"{constraint.right} (maximum linker {constraint.max_linker_bp} bp)"
        )
    )
    return RelationshipAssessment("fusion", modules_tuple, passes, detail)


def evaluate_construct_constraints(
    sequence: str,
    *,
    circular: bool,
    spec: ConstructSpec,
    base_dir: Path,
    annotation_calls: Iterable[FeatureCall] = (),
) -> ConstructConstraintAssessment:
    """Evaluate one physical product against deterministic scorer constraints."""
    templates = load_constraint_templates(base_dir)
    annotations = tuple(annotation_calls)
    module_results = tuple(
        _module_assessment(module, templates, sequence, circular, annotations)
        for module in spec.modules
    )
    by_id = {module.id: module for module in module_results}
    topology_pass = bool(
        spec.topology == "any"
        or (spec.topology == "circular" and circular)
        or (spec.topology == "linear" and not circular)
    )
    relationships = tuple(
        _assess_order(constraint, by_id, len(sequence)) for constraint in spec.ordered
    ) + tuple(
        _assess_fusion(constraint, by_id, sequence) for constraint in spec.fusions
    )
    return ConstructConstraintAssessment(
        name=spec.name,
        topology=spec.topology,
        topology_pass=topology_pass,
        modules=module_results,
        relationships=relationships,
    )
