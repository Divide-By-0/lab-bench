"""Build provenance-preserving inventories for cloning sequence attachments."""

from __future__ import annotations

import hashlib
import re
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SEQUENCE_FORMATS = {
    ".fa": "fasta",
    ".fasta": "fasta",
    ".fna": "fasta",
    ".gb": "genbank",
    ".gbff": "genbank",
    ".gbk": "genbank",
}
LABEL_QUALIFIERS = ("label", "gene", "locus_tag", "product", "standard_name")
TEXT_QUALIFIERS = (*LABEL_QUALIFIERS, "note", "function", "regulatory_class")
PRIMER_TYPES = {"primer", "primer_bind"}
SOURCE_TYPES = {"source"}
SHORT_TERM_MAX_LENGTH = 4

ROLE_DESCRIPTIONS = {
    "affinity_tag": "affinity or purification tag",
    "coding_sequence": "protein-coding sequence",
    "enhancer": "transcriptional enhancer",
    "epitope_tag": "epitope or detection tag",
    "genome_editor": "genome-editing effector",
    "intron_or_splicing": "intron or RNA-splicing element",
    "localization_signal": "subcellular localization signal",
    "origin_of_replication": "replication origin",
    "primer_binding_site": "primer binding site",
    "promoter": "transcriptional promoter",
    "protein_binding_site": "protein binding site",
    "recombination_site": "recombination site",
    "reporter": "reporter or detectable output",
    "selection_marker": "selectable marker",
    "terminator_or_polya": "transcription terminator or polyadenylation signal",
    "translation_control": "translation-control element",
    "viral_packaging_or_expression": "viral packaging or expression element",
}

ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "localization_signal",
        ("nls", "nuclear localization", "nes", "localization signal", "signal peptide"),
    ),
    ("epitope_tag", ("flag", "ha tag", "myc tag", "v5 tag", "epitope tag")),
    (
        "affinity_tag",
        (
            "his tag",
            "histidine tag",
            "his6",
            "6xhis",
            "strep tag",
            "maltose binding protein",
            "mbp tag",
            "gst tag",
        ),
    ),
    (
        "selection_marker",
        (
            "ampr",
            "kanr",
            "camr",
            "chloramphenicol resistance",
            "ampicillin resistance",
            "kanamycin resistance",
            "puromycin resistance",
            "hygromycin resistance",
            "blasticidin resistance",
            "selectable marker",
        ),
    ),
    (
        "reporter",
        ("gfp", "mcherry", "tdtomato", "luciferase", "fluorescent protein", "reporter"),
    ),
    ("genome_editor", ("cas9", "cas12", "cpf1", "base editor", "prime editor")),
    (
        "origin_of_replication",
        (
            "origin of replication",
            "replication origin",
            "cole1",
            "pmb1 ori",
            "f1 ori",
            "sv40 ori",
        ),
    ),
    (
        "terminator_or_polya",
        ("terminator", "polyadenylation", "poly(a)", "polya signal", "poly a signal"),
    ),
    ("promoter", ("promoter",)),
    ("enhancer", ("enhancer",)),
    ("translation_control", ("ires", "ribosome binding site", "rbs", "kozak")),
    (
        "viral_packaging_or_expression",
        (
            "woodchuck",
            "wpre",
            "ltr",
            "packaging signal",
            "rev response",
            "posttranscriptional regulatory",
        ),
    ),
    ("recombination_site", ("loxp", "frt", "attb", "attp", "recombination site")),
    ("intron_or_splicing", ("intron", "splice donor", "splice acceptor")),
)


def discover_sequence_files(inputs: Sequence[Path]) -> list[Path]:
    """Return supported sequence files under explicit files or directories."""
    paths: set[Path] = set()
    for input_path in inputs:
        path = input_path.expanduser().resolve()
        if path.is_file() and path.suffix.lower() in SEQUENCE_FORMATS:
            paths.add(path)
        elif path.is_dir():
            paths.update(
                candidate.resolve()
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() in SEQUENCE_FORMATS
            )
    return sorted(paths)


def build_cloning_inventory(
    inputs: Sequence[Path],
    *,
    root: Path | None = None,
    include_enzymes: bool = True,
) -> dict[str, Any]:
    """Parse sequence attachments and build file, feature, primer, and enzyme indexes."""
    files = discover_sequence_files(inputs)
    base = (root or _common_parent(files, inputs)).expanduser().resolve()
    feature_index: defaultdict[str, set[str]] = defaultdict(set)
    role_index: defaultdict[str, set[str]] = defaultdict(set)
    primer_index: defaultdict[str, set[str]] = defaultdict(set)
    sequence_index: defaultdict[str, set[str]] = defaultdict(set)
    enzyme_index: defaultdict[str, dict[str, list[str]]] = defaultdict(
        lambda: {"zero_cutters": [], "single_cutters": [], "multi_cutters": []}
    )
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    enzyme_catalog = _neb_enzyme_catalog() if include_enzymes else []

    for path in files:
        display_path = _display_path(path, base)
        try:
            entry = _inventory_file(path, display_path, include_enzymes)
        except Exception as exc:  # noqa: BLE001 - preserve per-file parse failures
            errors.append(
                {"path": display_path, "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        entries.append(entry)
        for record in entry["records"]:
            sequence_index[record["sequence_sha256"]].add(display_path)
            for feature in record["features"]:
                if feature["normalized_label"]:
                    feature_index[feature["normalized_label"]].add(display_path)
                for role in feature["functional_roles"]:
                    role_index[role].add(display_path)
            for primer in record["primers"]:
                if primer["normalized_label"]:
                    primer_index[primer["normalized_label"]].add(display_path)
            for name, cut_count in record.get("neb_restriction_sites", {}).items():
                category = (
                    "zero_cutters"
                    if cut_count == 0
                    else "single_cutters"
                    if cut_count == 1
                    else "multi_cutters"
                )
                enzyme_index[name][category].append(display_path)

    no_features = [
        entry["path"] for entry in entries if entry["part_feature_count"] == 0
    ]
    no_primers = [entry["path"] for entry in entries if entry["primer_count"] == 0]
    duplicate_sequences = {
        digest: sorted(paths)
        for digest, paths in sequence_index.items()
        if len(paths) > 1
    }
    files_with_parse_warnings = [
        entry["path"] for entry in entries if entry["parse_warnings"]
    ]
    return {
        "schema_version": 1,
        "root": str(base),
        "summary": {
            "discovered_file_count": len(files),
            "parsed_file_count": len(entries),
            "parse_error_count": len(errors),
            "parse_warning_count": sum(
                len(entry["parse_warnings"]) for entry in entries
            ),
            "files_with_parse_warnings": files_with_parse_warnings,
            "files_with_no_part_features": no_features,
            "files_with_no_primers": no_primers,
            "duplicate_sequence_group_count": len(duplicate_sequences),
        },
        "files": entries,
        "indexes": {
            "feature_label_to_files": _sorted_set_mapping(feature_index),
            "functional_role_to_files": _sorted_set_mapping(role_index),
            "primer_label_to_files": _sorted_set_mapping(primer_index),
            "sequence_sha256_to_files": _sorted_set_mapping(sequence_index),
            "duplicate_sequences": duplicate_sequences,
            "neb_enzyme_to_files": dict(sorted(enzyme_index.items())),
        },
        "neb_enzyme_catalog": enzyme_catalog,
        "errors": errors,
        "provenance": {
            "feature_annotations": "source GenBank qualifiers plus deterministic role rules",
            "primer_sequences": "5-prime-to-3-prime feature.extract(record.seq)",
            "neb_enzyme_catalog": (
                "Biopython Restriction_Dictionary supplier code N; verify live NEB availability"
                if include_enzymes
                else "not generated"
            ),
        },
    }


def _inventory_file(
    path: Path, display_path: str, include_enzymes: bool
) -> dict[str, Any]:
    from Bio import BiopythonParserWarning, SeqIO

    file_format = SEQUENCE_FORMATS[path.suffix.lower()]
    raw = path.read_bytes()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always", BiopythonParserWarning)
        with path.open(encoding="utf-8") as handle:
            parsed_records = SeqIO.parse(  # type: ignore[no-untyped-call]
                handle, file_format
            )
            records = list(parsed_records)
    if not records:
        raise ValueError("no sequence records")
    record_entries = [
        _inventory_record(record, include_enzymes=include_enzymes) for record in records
    ]
    return {
        "path": display_path,
        "format": file_format,
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": len(record_entries),
        "sequence_length": sum(record["sequence_length"] for record in record_entries),
        "feature_count": sum(record["feature_count"] for record in record_entries),
        "annotation_feature_count": sum(
            record["annotation_feature_count"] for record in record_entries
        ),
        "part_feature_count": sum(
            record["part_feature_count"] for record in record_entries
        ),
        "primer_count": sum(record["primer_count"] for record in record_entries),
        "parse_warnings": [
            {
                "category": warning.category.__name__,
                "message": str(warning.message),
            }
            for warning in caught_warnings
        ],
        "records": record_entries,
    }


def _inventory_record(record: Any, *, include_enzymes: bool) -> dict[str, Any]:
    sequence = str(record.seq).upper()
    feature_entries = [
        _inventory_feature(feature)
        for feature in record.features
        if feature.type.casefold() not in SOURCE_TYPES | PRIMER_TYPES
    ]
    primers = [
        _inventory_primer(record, feature)
        for feature in record.features
        if feature.type.lower() in PRIMER_TYPES
    ]
    result: dict[str, Any] = {
        "id": str(record.id),
        "name": str(record.name),
        "description": str(record.description),
        "sequence_length": len(sequence),
        "sequence_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        "topology": str(record.annotations.get("topology") or "unknown"),
        "feature_count": len(record.features),
        "annotation_feature_count": sum(
            feature.type.casefold() not in SOURCE_TYPES for feature in record.features
        ),
        "part_feature_count": len(feature_entries),
        "primer_count": len(primers),
        "features": feature_entries,
        "primers": primers,
    }
    if include_enzymes:
        result["neb_restriction_sites"] = _neb_restriction_sites(record)
    return result


def _inventory_feature(feature: Any) -> dict[str, Any]:
    qualifiers = _clean_qualifiers(feature.qualifiers)
    label = _first_qualifier(qualifiers, LABEL_QUALIFIERS)
    roles = classify_feature_roles(feature.type, qualifiers)
    return {
        "feature_type": str(feature.type),
        "location": str(feature.location),
        "start_0_based": int(feature.location.start),
        "end_0_based_exclusive": int(feature.location.end),
        "strand": feature.location.strand,
        "label": label,
        "normalized_label": normalize_label(label),
        "functional_roles": roles,
        "functional_description": describe_feature(label, roles),
        "qualifiers": qualifiers,
    }


def _inventory_primer(record: Any, feature: Any) -> dict[str, Any]:
    qualifiers = _clean_qualifiers(feature.qualifiers)
    label = _first_qualifier(qualifiers, LABEL_QUALIFIERS) or "unnamed primer"
    return {
        "label": label,
        "normalized_label": normalize_label(label),
        "location": str(feature.location),
        "start_0_based": int(feature.location.start),
        "end_0_based_exclusive": int(feature.location.end),
        "strand": feature.location.strand,
        "binding_sequence_5to3": str(feature.extract(record.seq)).upper(),
        "length": len(feature),
        "qualifiers": qualifiers,
    }


def classify_feature_roles(
    feature_type: str, qualifiers: Mapping[str, list[str]]
) -> list[str]:
    """Map a structural GenBank feature to zero or more functional roles."""
    feature_type_lower = feature_type.casefold()
    text = " ".join(
        value for key in TEXT_QUALIFIERS for value in qualifiers.get(key, [])
    ).casefold()
    roles: set[str] = set()
    if feature_type_lower == "cds":
        roles.add("coding_sequence")
    if feature_type_lower in PRIMER_TYPES:
        roles.add("primer_binding_site")
    structural_roles = {
        "promoter": "promoter",
        "enhancer": "enhancer",
        "terminator": "terminator_or_polya",
        "polya_signal": "terminator_or_polya",
        "rep_origin": "origin_of_replication",
        "protein_bind": "protein_binding_site",
        "intron": "intron_or_splicing",
    }
    role = structural_roles.get(feature_type_lower)
    if role:
        roles.add(role)
    for candidate, patterns in ROLE_PATTERNS:
        if any(_contains_term(text, pattern) for pattern in patterns):
            roles.add(candidate)
    return sorted(roles)


def describe_feature(label: str, roles: Sequence[str]) -> str:
    """Create a conservative prompt-ready function description."""
    descriptions = [
        ROLE_DESCRIPTIONS[role] for role in roles if role in ROLE_DESCRIPTIONS
    ]
    if label and descriptions:
        return f"{label}: {', '.join(descriptions)}"
    if label:
        return label
    return ", ".join(descriptions) or "unclassified sequence annotation"


def normalize_label(label: str) -> str:
    """Normalize a feature/primer label for cross-file indexing."""
    return re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()


def _contains_term(text: str, term: str) -> bool:
    if len(term) <= SHORT_TERM_MAX_LENGTH and term.replace(" ", "").isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
    return term in text


def _clean_qualifiers(qualifiers: Mapping[str, Any]) -> dict[str, list[str]]:
    cleaned: dict[str, list[str]] = {}
    for key, raw_values in qualifiers.items():
        values = raw_values if isinstance(raw_values, list) else [raw_values]
        cleaned[str(key)] = [str(value) for value in values]
    return cleaned


def _first_qualifier(qualifiers: Mapping[str, list[str]], keys: Iterable[str]) -> str:
    for key in keys:
        values = qualifiers.get(key, [])
        if values and values[0].strip():
            return values[0].strip()
    return ""


def _neb_enzyme_names() -> list[str]:
    from Bio.Restriction import Restriction_Dictionary

    supplier = Restriction_Dictionary.suppliers["N"]
    return sorted(str(name) for name in supplier[1])


def _neb_enzyme_catalog() -> list[dict[str, Any]]:
    from Bio import __version__ as biopython_version
    from Bio.Restriction import Restriction_Dictionary

    catalog = []
    for name in _neb_enzyme_names():
        data = Restriction_Dictionary.rest_dict[name]
        catalog.append(
            {
                "name": name,
                "recognition_site": data.get("site"),
                "cut_5prime": data.get("fst5"),
                "cut_3prime": data.get("fst3"),
                "second_cut_5prime": data.get("scd5"),
                "second_cut_3prime": data.get("scd3"),
                "overhang_length": data.get("ovhg"),
                "overhang_sequence": data.get("ovhgseq"),
                "optimal_temperature_c": data.get("opt_temp"),
                "inactivation_temperature_c": data.get("inact_temp"),
                "rebase_uri": data.get("uri"),
                "supplier_code": "N",
                "biopython_version": biopython_version,
            }
        )
    return catalog


def _neb_restriction_sites(record: Any) -> dict[str, int]:
    from Bio.Restriction.Restriction import RestrictionBatch

    batch = RestrictionBatch(_neb_enzyme_names())  # type: ignore[no-untyped-call]
    linear = str(record.annotations.get("topology") or "").casefold() != "circular"
    matches = batch.search(  # type: ignore[no-untyped-call]
        record.seq, linear=linear
    )
    return dict(
        sorted((str(enzyme), len(positions)) for enzyme, positions in matches.items())
    )


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _common_parent(files: Sequence[Path], inputs: Sequence[Path]) -> Path:
    if files:
        import os

        return Path(os.path.commonpath([str(path.parent) for path in files]))
    if inputs:
        first = inputs[0].expanduser().resolve()
        return first if first.is_dir() else first.parent
    return Path.cwd()


def _sorted_set_mapping(mapping: Mapping[str, set[str]]) -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in sorted(mapping.items())}
