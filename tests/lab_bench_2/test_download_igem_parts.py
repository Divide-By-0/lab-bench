import io
import sys
from pathlib import Path

import pytest
from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

import download_igem_parts  # noqa: E402, I001


GENBANK = """LOCUS       BBa_B0015                129 bp    DNA     linear   SYN 08-SEP-2021
DEFINITION  double terminator.
ACCESSION   BBa_B0015
VERSION     BBa_B0015
KEYWORDS    .
FEATURES             Location/Qualifiers
     source          1..129
                     /mol_type="genomic DNA"
     terminator      1..129
                     /label="Terminator"
                     /note="SO:0000141 Terminator"
ORIGIN
        1 ccaggcatca aataaaacga aaggctcagt cgaaagactg ggcctttcgt tttatctgtt
       61 gtttgtcggt gaacgctctc tactagagtc acactggctc accttcgggt gggcctttct
      121 gcgtttata
//
"""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("BBa_J23100", "bba-j23100"),
        ("Part:BBa_B0015", "bba-b0015"),
        ("bba-k863006", "bba-k863006"),
        ("https://registry.igem.org/parts/bba-j23100", "bba-j23100"),
        ("https://parts.igem.org/Part:BBa_J23100", "bba-j23100"),
        ("pSB1C3", "psb1c3"),
    ],
)
def test_normalize_part_identifier(value: str, expected: str) -> None:
    assert download_igem_parts.normalize_part_identifier(value) == expected


def test_normalize_part_identifier_rejects_non_registry_url() -> None:
    with pytest.raises(ValueError, match="Not an iGEM Registry URL"):
        download_igem_parts.normalize_part_identifier("https://example.com/parts/bba-j23100")


def test_enrich_genbank_adds_composition_and_sequence_features() -> None:
    enriched, count, warnings = download_igem_parts.enrich_genbank(
        GENBANK,
        sequence_length=129,
        sequence_features=[
            {
                "uuid": "sequence-feature-uuid",
                "label": "Operator site",
                "role": {"label": "Operator", "accession": "SO:0000057"},
                "locations": [{"start": 10, "end": 20}],
                "strand": "reverse",
            }
        ],
        composition=[
            {
                "componentUUID": "component-uuid",
                "componentName": "BBa_B0010",
                "role": {"label": "Terminator", "accession": "SO:0000141"},
                "start": 1,
                "end": 80,
                "strand": "forward",
            }
        ],
    )

    assert count == 2
    assert warnings == ()
    assert 'regulatory      complement(10..20)' in enriched
    assert '/label="Operator site"' in enriched
    assert 'terminator      1..80' in enriched
    assert '/label="BBa_B0010"' in enriched

    record = SeqIO.read(io.StringIO(enriched), "genbank")
    labels = {
        feature.qualifiers["label"][0]
        for feature in record.features
        if "label" in feature.qualifiers
    }
    assert {"Terminator", "Operator site", "BBa_B0010"} <= labels


def test_enrich_genbank_does_not_duplicate_native_feature_label() -> None:
    enriched, count, warnings = download_igem_parts.enrich_genbank(
        GENBANK,
        sequence_length=129,
        sequence_features=[
            {
                "uuid": "duplicate",
                "label": "Terminator",
                "role": {"label": "Terminator", "accession": "SO:0000141"},
                "locations": [{"start": 1, "end": 129}],
                "strand": "forward",
            }
        ],
        composition=[],
    )

    assert enriched == GENBANK
    assert count == 0
    assert warnings == ()


def test_enrich_genbank_skips_out_of_bounds_annotation() -> None:
    enriched, count, warnings = download_igem_parts.enrich_genbank(
        GENBANK,
        sequence_length=129,
        sequence_features=[],
        composition=[
            {
                "componentName": "broken",
                "start": 100,
                "end": 140,
                "strand": "forward",
            }
        ],
    )

    assert enriched == GENBANK
    assert count == 0
    assert warnings == ("Skipped component 'broken': feature location 100..140 is outside 1..129",)


def test_validate_genbank_rejects_html_error_page() -> None:
    with pytest.raises(download_igem_parts.IGEMError, match="LOCUS"):
        download_igem_parts.validate_genbank("<html>blocked</html>")
