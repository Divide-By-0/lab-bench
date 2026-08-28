"""Build provenance-preserving inventories for cloning sequence attachments."""

from __future__ import annotations

import hashlib
import os
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
    external_sources: Mapping[str, Any] | None = None,
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
    external_role_index: defaultdict[str, set[str]] = defaultdict(set)
    external_category_index: defaultdict[str, set[str]] = defaultdict(set)
    external_part_index: defaultdict[str, set[str]] = defaultdict(set)
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

    external_enrichment = _apply_external_enrichment(entries, external_sources)
    for entry in entries:
        for record in entry["records"]:
            for feature in record["features"]:
                igem = feature.get("external_function_candidates", {}).get(
                    "igem_registry", {}
                )
                for role in igem.get("roles", []):
                    external_role_index[str(role["accession"])].add(entry["path"])
                for category in igem.get("categories", []):
                    external_category_index[str(category["path"])].add(entry["path"])
                for part in igem.get("specific_parts", []):
                    if not part.get("selected"):
                        continue
                    external_part_index[str(part["name"])].add(entry["path"])
                    part_role = part.get("role")
                    if isinstance(part_role, Mapping) and part_role.get("accession"):
                        external_role_index[str(part_role["accession"])].add(
                            entry["path"]
                        )

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
            "features_with_external_candidates": external_enrichment[
                "matched_feature_count"
            ],
        },
        "files": entries,
        "indexes": {
            "feature_label_to_files": _sorted_set_mapping(feature_index),
            "functional_role_to_files": _sorted_set_mapping(role_index),
            "primer_label_to_files": _sorted_set_mapping(primer_index),
            "sequence_sha256_to_files": _sorted_set_mapping(sequence_index),
            "duplicate_sequences": duplicate_sequences,
            "neb_enzyme_to_files": dict(sorted(enzyme_index.items())),
            "igem_role_to_files": _sorted_set_mapping(external_role_index),
            "igem_category_to_files": _sorted_set_mapping(external_category_index),
            "igem_part_to_files": _sorted_set_mapping(external_part_index),
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
            "external_enrichment": external_enrichment,
        },
    }


def _apply_external_enrichment(
    entries: Sequence[dict[str, Any]], external_sources: Mapping[str, Any] | None
) -> dict[str, Any]:
    if not external_sources:
        return {
            "status": "not provided",
            "matched_feature_count": 0,
            "method": "none",
        }
    sources = external_sources.get("sources")
    if not isinstance(sources, Mapping):
        raise ValueError("External source data has no sources mapping")
    igem = sources.get("igem_registry")
    if not isinstance(igem, Mapping):
        return {
            "status": "iGEM vocabulary absent",
            "matched_feature_count": 0,
            "method": "none",
        }
    indexes = igem.get("indexes")
    if not isinstance(indexes, Mapping):
        raise ValueError("iGEM source data has no indexes mapping")
    role_index = indexes.get("role_alias_to_terms")
    category_index = indexes.get("category_alias_to_terms")
    part_index = indexes.get("feature_signature_to_part_matches", {})
    if not isinstance(role_index, Mapping) or not isinstance(category_index, Mapping):
        raise ValueError("iGEM source data has invalid alias indexes")
    if not isinstance(part_index, Mapping):
        raise ValueError("iGEM source data has invalid specific-part index")

    matched_count = 0
    specific_part_candidate_count = 0
    selected_specific_part_count = 0
    for entry in entries:
        for record in entry["records"]:
            for feature in record["features"]:
                match_keys = [str(feature.get("normalized_label") or "")]
                match_keys = [key for key in match_keys if key]
                roles = _external_terms_for_aliases(role_index, match_keys, "accession")
                categories = _external_terms_for_aliases(
                    category_index, match_keys, "uuid"
                )
                signature = str(feature.get("feature_signature") or "")
                raw_parts = part_index.get(signature, [])
                specific_parts = [
                    {str(key): value for key, value in part.items()}
                    for part in raw_parts
                    if isinstance(part, Mapping)
                ]
                selected_parts = [
                    part for part in specific_parts if part.get("selected")
                ]
                if not roles and not categories and not specific_parts:
                    continue
                feature["external_function_candidates"] = {
                    "igem_registry": {
                        "match_keys": match_keys,
                        "match_method": (
                            "specific part search by source label, sequence length, "
                            "functional-role filter, and sequence/translation evidence; "
                            "vocabulary lookup by source label only"
                        ),
                        "nucleotide_sequence_verified": any(
                            bool(part.get("evidence", {}).get("nucleotide_exact"))
                            for part in selected_parts
                        ),
                        "translated_peptide_verified": any(
                            bool(
                                part.get("evidence", {}).get("translated_peptide_exact")
                            )
                            for part in selected_parts
                        ),
                        "review_required": not selected_parts
                        or any(
                            bool(part.get("review_required")) for part in selected_parts
                        ),
                        "roles": roles,
                        "categories": categories,
                        "specific_parts": specific_parts,
                    }
                }
                matched_count += 1
                specific_part_candidate_count += bool(specific_parts)
                selected_specific_part_count += bool(selected_parts)

    source = igem.get("source")
    summary = igem.get("summary")
    source_mapping = source if isinstance(source, Mapping) else {}
    summary_mapping = summary if isinstance(summary, Mapping) else {}
    openapi = source_mapping.get("openapi")
    openapi_mapping = openapi if isinstance(openapi, Mapping) else {}
    return {
        "status": "applied",
        "matched_feature_count": matched_count,
        "specific_part_candidate_count": specific_part_candidate_count,
        "specific_part_match_count": selected_specific_part_count,
        "selected_specific_part_count": selected_specific_part_count,
        "method": (
            "source-label vocabulary lookup plus provenance-preserving specific-part "
            "matches; GenBank structural types are never treated as iGEM roles"
        ),
        "igem_api_version": str(source_mapping.get("api_version") or ""),
        "igem_openapi_sha256": str(openapi_mapping.get("sha256") or ""),
        "igem_role_count": int(summary_mapping.get("role_count") or 0),
        "igem_category_count": int(summary_mapping.get("category_count") or 0),
    }


def _external_terms_for_aliases(
    index: Mapping[str, Any], aliases: Sequence[str], identity_key: str
) -> list[dict[str, Any]]:
    terms: dict[str, dict[str, Any]] = {}
    for alias in aliases:
        candidates = index.get(alias, [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            identity = str(candidate.get(identity_key) or "")
            if identity:
                terms[identity] = {str(key): value for key, value in candidate.items()}
    return sorted(terms.values(), key=lambda term: str(term.get(identity_key) or ""))


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
        _inventory_feature(record, feature)
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


def _inventory_feature(record: Any, feature: Any) -> dict[str, Any]:
    qualifiers = _clean_qualifiers(feature.qualifiers)
    label = _first_qualifier(qualifiers, LABEL_QUALIFIERS)
    roles = classify_feature_roles(feature.type, qualifiers)
    sequence = str(feature.extract(record.seq)).upper()
    return {
        "feature_type": str(feature.type),
        "location": str(feature.location),
        "start_0_based": int(feature.location.start),
        "end_0_based_exclusive": int(feature.location.end),
        "strand": feature.location.strand,
        "label": label,
        "normalized_label": normalize_label(label),
        "feature_sequence_length": len(sequence),
        "feature_sequence_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        "feature_signature": feature_signature(label, sequence),
        "functional_roles": roles,
        "functional_description": describe_feature(label, roles),
        "qualifiers": qualifiers,
    }


def collect_feature_queries(inputs: Sequence[Path]) -> list[dict[str, Any]]:
    """Extract deduplicated, sequence-bearing feature queries for external search."""
    from Bio import SeqIO

    queries: dict[str, dict[str, Any]] = {}
    for path in discover_sequence_files(inputs):
        file_format = SEQUENCE_FORMATS[path.suffix.lower()]
        with path.open(encoding="utf-8") as handle:
            records = SeqIO.parse(handle, file_format)  # type: ignore[no-untyped-call]
            for record in records:
                for feature in record.features:
                    if feature.type.casefold() in SOURCE_TYPES | PRIMER_TYPES:
                        continue
                    qualifiers = _clean_qualifiers(feature.qualifiers)
                    label = _first_qualifier(qualifiers, LABEL_QUALIFIERS)
                    if not label:
                        continue
                    sequence = str(feature.extract(record.seq)).upper()
                    signature = feature_signature(label, sequence)
                    queries.setdefault(
                        signature,
                        {
                            "feature_signature": signature,
                            "label": label,
                            "normalized_label": normalize_label(label),
                            "feature_type": str(feature.type),
                            "functional_roles": classify_feature_roles(
                                feature.type, qualifiers
                            ),
                            "nucleotide_sequence": sequence,
                            "nucleotide_length": len(sequence),
                            "translation": _first_qualifier(
                                qualifiers, ("translation",)
                            ),
                            "source_description": _first_qualifier(
                                qualifiers, ("function", "product", "note")
                            ),
                        },
                    )
    return [queries[key] for key in sorted(queries)]


def feature_signature(label: str, sequence: str) -> str:
    """Return a stable identity for one labeled feature sequence."""
    sequence_digest = hashlib.sha256(sequence.upper().encode("ascii")).hexdigest()
    return f"{normalize_label(label)}:{sequence_digest}"


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
        return os.fspath(path.relative_to(root))
    except ValueError:
        return str(path)


def _common_parent(files: Sequence[Path], inputs: Sequence[Path]) -> Path:
    if files:
        return Path(os.path.commonpath([str(path.parent) for path in files]))
    if inputs:
        first = inputs[0].expanduser().resolve()
        return first if first.is_dir() else first.parent
    return Path.cwd()


def _sorted_set_mapping(mapping: Mapping[str, set[str]]) -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in sorted(mapping.items())}
