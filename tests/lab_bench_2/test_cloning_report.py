from __future__ import annotations

from pathlib import Path

import pytest

from lab_bench_2.cloning_report import CloningReportError, render_cloning_report


def _inventory() -> dict[str, object]:
    return {
        "files": [
            {
                "path": "plasmid.gbk",
                "file_sha256": "file-digest",
                "parse_warnings": [],
                "records": [
                    {
                        "sequence_length": 100,
                        "sequence_sha256": "sequence-digest",
                        "topology": "circular",
                        "features": [
                            {
                                "label": "FLAG",
                                "feature_type": "CDS",
                                "location": "[10:34](+)",
                                "start_0_based": 10,
                                "end_0_based_exclusive": 34,
                                "strand": 1,
                                "functional_description": (
                                    "FLAG: protein-coding sequence, "
                                    "epitope or detection tag"
                                ),
                                "functional_role_evidence": [
                                    {
                                        "role": "coding_sequence",
                                        "evidence": [
                                            {
                                                "method": "genbank_feature_type",
                                                "feature_type": "CDS",
                                            }
                                        ],
                                    },
                                    {
                                        "role": "epitope_tag",
                                        "evidence": [
                                            {
                                                "method": "curated_qualifier_pattern",
                                                "qualifier": "label",
                                                "source_value": "FLAG",
                                                "matched_term": "flag",
                                            }
                                        ],
                                    },
                                ],
                                "qualifiers": {
                                    "label": ["FLAG"],
                                    "product": ["FLAG epitope tag"],
                                },
                                "external_function_candidates": {
                                    "igem_registry": {
                                        "specific_parts": [
                                            {
                                                "name": "BBa_K4587111",
                                                "title": "FLAG Tag",
                                                "url": (
                                                    "https://registry.igem.org/parts/"
                                                    "bba-k4587111"
                                                ),
                                                "description": "A detection tag.",
                                                "selected": True,
                                                "role": {
                                                    "label": "Tag",
                                                    "accession": "SO:0000324",
                                                },
                                                "evidence": {
                                                    "nucleotide_exact": False,
                                                    "same_length_nucleotide_identity_percent": 83.333,
                                                    "translated_peptide_exact": True,
                                                },
                                            }
                                        ]
                                    }
                                },
                            }
                        ],
                        "primers": [
                            {
                                "label": "Primer A",
                                "location": "[1:9](+)",
                                "start_0_based": 1,
                                "end_0_based_exclusive": 9,
                                "strand": 1,
                                "binding_sequence_5to3": "ATGCGTAA",
                                "qualifiers": {"note": ["source primer"]},
                            }
                        ],
                        "neb_restriction_sites": {"EcoRI": 1, "BamHI": 0},
                    }
                ],
            }
        ]
    }


def test_report_separates_source_rules_and_specific_igem_data(tmp_path: Path) -> None:
    source = tmp_path / "plasmid.gbk"
    source.write_text("source is represented by inventory fixture")
    manifest = {
        "tool": {"version": "2.0.0"},
        "summary": {"annotated_or_cached_count": 1, "error_count": 0},
        "results": [
            {
                "source_path": str(source),
                "annotation_summary": {
                    "annotations": [
                        {
                            "feature": "FLAG",
                            "feature_type": "CDS",
                            "description": "database candidate",
                            "database": "snapgene",
                            "fragment": False,
                            "percent_identity": 100.0,
                            "percent_match_length": 100.0,
                        }
                    ]
                },
            }
        ],
    }

    report = render_cloning_report(
        source,
        _inventory(),
        {"sources": {}},
        plannotate_manifest=manifest,
    )

    assert "Rule-derived functional summary" in report
    assert "epitope_tag" in report
    assert "matched <code>flag</code>" in report
    assert "BBa_K4587111: FLAG Tag" in report
    assert "Tag (SO:0000324)" in report
    assert "83.333% same-length DNA identity · exact translated peptide" in report
    assert "A detection tag." in report
    assert "Primer A" in report
    assert "EcoRI" in report
    assert "pLannotate 2.0.0; 1 annotated/cached; 0 errors" in report
    assert "background:var(--series-1)" in report
    assert "background:var(--series-2)" in report


def test_report_rejects_more_than_one_record(tmp_path: Path) -> None:
    inventory = _inventory()
    files = inventory["files"]
    assert isinstance(files, list)
    file_entry = files[0]
    assert isinstance(file_entry, dict)
    records = file_entry["records"]
    assert isinstance(records, list)
    records.append(dict(records[0]))

    with pytest.raises(CloningReportError, match="exactly one sequence record"):
        render_cloning_report(tmp_path / "multi.gbk", inventory, {"sources": {}})
