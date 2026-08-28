import io
import sys
from pathlib import Path

from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

import download_igem_distribution  # noqa: E402, I001


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "record-uuid",
        "part_id": "BBa_B0012",
        "plasmid_id": "BBa_J428091",
        "part_type": "terminator",
        "part_role": "Terminator",
        "so_id": "SO:0000141",
        "collection": "Terminators",
        "kit_year": 2026,
        "kit_plate": 1,
        "well": "A1",
        "plate_well": "1-A1",
        "assembly_format": "Type IIS L0 Part",
        "flanking_site": "BsaI",
        "flanking_5": "GCTT",
        "flanking_3": "CGCT",
        "qc_status": "Correct",
        "is_valid": True,
        "sequence": "ACGT" * 20,
        "full_plasmid_seq_length": 80,
        "part_url": "https://registry.igem.org/parts/bba-j428091",
        "backbone_name": "pSB1C5SD",
        "resistance": "Chloramphenicol",
        "copy_number": "high",
        "origin": "ColE1",
        "created_at": "2026-05-16T03:25:44+00:00",
        "updated_at": "2026-05-17T03:25:44+00:00",
    }
    record.update(overrides)
    return record


def test_distribution_genbank_is_circular_and_parseable() -> None:
    genbank = download_igem_distribution.distribution_genbank(_record())

    parsed = SeqIO.read(io.StringIO(genbank), "genbank")
    assert len(parsed.seq) == 80
    assert parsed.annotations["topology"] == "circular"
    assert parsed.id == "BBa_J428091"
    assert parsed.features[1].qualifiers["label"] == [
        "BBa_J428091 distribution plasmid"
    ]
    assert "Plate/well: 1-A1" in genbank
    assert "QC: Correct (valid=True)" in genbank


def test_write_distribution_creates_manifests_and_sequence_files(tmp_path: Path) -> None:
    records = [_record(), _record(id="second", kit_plate=2, well="B2", plate_well="2-B2")]

    result = download_igem_distribution.write_distribution(
        records,
        tmp_path,
        year=2026,
        include_fasta=True,
        force=False,
    )

    assert result.records == 2
    assert result.total_bp == 160
    assert (tmp_path / "genbank/1-A1_BBa_J428091.gb").is_file()
    assert (tmp_path / "fasta/2-B2_BBa_J428091.fasta").is_file()
    assert (tmp_path / "manifest.csv").is_file()
    assert (tmp_path / "manifest.json").is_file()
    assert (tmp_path / "kit_inventory.raw.json").is_file()
    combined = list(SeqIO.parse(tmp_path / "all_plasmids.fasta", "fasta"))
    assert len(combined) == 2


def test_record_sort_key_sorts_wells_naturally() -> None:
    records = [
        _record(well="A10"),
        _record(well="B1"),
        _record(well="A2"),
    ]

    records.sort(key=download_igem_distribution._record_sort_key)

    assert [record["well"] for record in records] == ["A2", "A10", "B1"]
