from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from lab_bench_2.cloning_inventory import (
    build_cloning_inventory,
    classify_feature_roles,
    feature_signature,
)


def _write_genbank(path: Path) -> None:
    record = SeqRecord(
        Seq("AAAAGGTCTCAAAAAAAAAAAAAAAAAAAAAA"),
        id="plasmid",
        name="plasmid",
        description="synthetic fixture",
    )
    record.annotations = {"molecule_type": "DNA", "topology": "linear"}
    record.features = [
        SeqFeature(FeatureLocation(0, 34), type="source"),
        SeqFeature(
            FeatureLocation(10, 19),
            type="CDS",
            qualifiers={"label": ["SV40 NLS"]},
        ),
        SeqFeature(
            FeatureLocation(19, 28),
            type="CDS",
            qualifiers={"label": ["AmpR"]},
        ),
        SeqFeature(
            FeatureLocation(0, 4, strand=-1),
            type="primer_bind",
            qualifiers={"label": ["Reverse primer"]},
        ),
        SeqFeature(
            FeatureLocation(4, 10),
            type="promoter",
            qualifiers={"label": ["CMV promoter"]},
        ),
    ]
    SeqIO.write(record, path, "genbank")


def test_builds_feature_primer_duplicate_and_missing_indexes(tmp_path: Path) -> None:
    gbk = tmp_path / "plasmid.gbk"
    duplicate = tmp_path / "duplicate.gb"
    fasta = tmp_path / "bare.fa"
    _write_genbank(gbk)
    duplicate.write_bytes(gbk.read_bytes())
    SeqIO.write(SeqRecord(Seq("ACGT"), id="bare", description=""), fasta, "fasta")

    inventory = build_cloning_inventory(
        [tmp_path], root=tmp_path, include_enzymes=False
    )

    summary = inventory["summary"]
    assert summary["discovered_file_count"] == 3
    assert summary["files_with_no_part_features"] == ["bare.fa"]
    assert summary["files_with_no_primers"] == ["bare.fa"]
    assert inventory["indexes"]["feature_label_to_files"]["sv40 nls"] == [
        "duplicate.gb",
        "plasmid.gbk",
    ]
    assert inventory["indexes"]["functional_role_to_files"]["localization_signal"] == [
        "duplicate.gb",
        "plasmid.gbk",
    ]
    assert inventory["indexes"]["primer_label_to_files"]["reverse primer"] == [
        "duplicate.gb",
        "plasmid.gbk",
    ]
    assert summary["duplicate_sequence_group_count"] == 1

    plasmid = next(
        entry for entry in inventory["files"] if entry["path"] == "plasmid.gbk"
    )
    assert plasmid["records"][0]["primers"][0]["binding_sequence_5to3"] == "TTTT"
    nls = next(
        feature
        for feature in plasmid["records"][0]["features"]
        if feature["label"] == "SV40 NLS"
    )
    assert nls["functional_roles"] == ["coding_sequence", "localization_signal"]
    assert "subcellular localization signal" in nls["functional_description"]


def test_inventory_includes_neb_catalog_and_cut_counts(tmp_path: Path) -> None:
    gbk = tmp_path / "plasmid.gbk"
    _write_genbank(gbk)

    inventory = build_cloning_inventory([gbk], root=tmp_path)

    bsa_i = next(
        enzyme for enzyme in inventory["neb_enzyme_catalog"] if enzyme["name"] == "BsaI"
    )
    assert bsa_i["recognition_site"] == "GGTCTC"
    assert inventory["files"][0]["records"][0]["neb_restriction_sites"]["BsaI"] == 1
    assert inventory["indexes"]["neb_enzyme_to_files"]["BsaI"]["single_cutters"] == [
        "plasmid.gbk"
    ]


def test_feature_type_and_function_are_separate() -> None:
    roles = classify_feature_roles("CDS", {"label": ["FLAG-NLS"]})
    assert roles == ["coding_sequence", "epitope_tag", "localization_signal"]


def test_external_igem_specific_match_preserves_evidence_and_indexes(
    tmp_path: Path,
) -> None:
    record = SeqRecord(Seq("ATG" * 30), id="record", name="record")
    record.annotations["molecule_type"] = "DNA"
    record.features = [
        SeqFeature(
            FeatureLocation(0, 30),
            type="CDS",
            qualifiers={"label": ["Cas9"]},
        )
    ]
    gbk = tmp_path / "cas9.gbk"
    SeqIO.write(record, gbk, "genbank")
    signature = feature_signature("Cas9", "ATG" * 10)
    source_data = {
        "sources": {
            "igem_registry": {
                "source": {
                    "api_version": "1.0",
                    "openapi": {"sha256": "openapi-digest"},
                },
                "summary": {"role_count": 1, "category_count": 1},
                "indexes": {
                    "role_alias_to_terms": {
                        "cds": [
                            {
                                "accession": "SO:0000316",
                                "label": "CDS",
                                "definition": "coding region",
                                "source": "SO",
                            }
                        ]
                    },
                    "category_alias_to_terms": {
                        "cas9": [
                            {
                                "uuid": "category-cas9",
                                "path": "//function/crispr/cas9",
                                "description": "",
                            }
                        ]
                    },
                    "feature_signature_to_part_matches": {
                        signature: [
                            {
                                "name": "BBa_TEST_CAS9",
                                "url": "https://registry.igem.org/parts/bba-test-cas9",
                                "title": "Cas9",
                                "description": "RNA-guided nuclease.",
                                "role": {
                                    "accession": "SO:0000316",
                                    "label": "CDS",
                                },
                                "selected": True,
                                "evidence": {"nucleotide_exact": True},
                            }
                        ]
                    },
                },
            }
        }
    }

    inventory = build_cloning_inventory(
        [gbk], include_enzymes=False, external_sources=source_data
    )
    candidates = inventory["files"][0]["records"][0]["features"][0][
        "external_function_candidates"
    ]["igem_registry"]

    assert candidates["nucleotide_sequence_verified"] is True
    assert candidates["translated_peptide_verified"] is False
    assert candidates["review_required"] is False
    assert candidates["roles"] == []
    assert candidates["categories"][0]["path"] == "//function/crispr/cas9"
    assert candidates["specific_parts"][0]["name"] == "BBa_TEST_CAS9"
    assert inventory["indexes"]["igem_category_to_files"] == {
        "//function/crispr/cas9": ["cas9.gbk"]
    }
    assert inventory["indexes"]["igem_part_to_files"] == {"BBa_TEST_CAS9": ["cas9.gbk"]}
    enrichment = inventory["provenance"]["external_enrichment"]
    assert enrichment["specific_part_candidate_count"] == 1
    assert enrichment["selected_specific_part_count"] == 1
