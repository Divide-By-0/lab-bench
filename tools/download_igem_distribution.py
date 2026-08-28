#!/usr/bin/env python3
"""Download every physical plasmid in an iGEM Distribution Kit.

The Registry distribution page embeds WellRead, whose public dataset is the
authoritative plate/well inventory and includes the sequenced physical plasmid
for every occupied well. This tool snapshots that dataset and writes one
annotated, circular GenBank file per well, optional FASTA files, and manifests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import download_igem_parts as igem

DISTRIBUTION_PAGE = "https://registry.igem.org/distribution"
WELLREAD_APP = "https://wellreadbio.vercel.app"
PAGE_SIZE = 1000
_ENV_RE = re.compile(r'"(PUBLIC_SUPABASE_(?:URL|KEY))":"([^"]+)"')
_WELL_RE = re.compile(r"^([A-Z]+)(\d+)$")
_SEQUENCE_RE = re.compile(r"^[ACGTN]+$")


@dataclass(frozen=True)
class DistributionResult:
    output_dir: Path
    year: int
    records: int
    total_bp: int
    qc_counts: dict[str, int]
    invalid_records: int
    length_mismatches: int


def discover_data_source(client: igem.IGEMClient | None = None) -> tuple[str, str]:
    """Read the public Supabase URL and publishable key embedded by WellRead."""
    app_client = client or igem.IGEMClient(
        api_base=WELLREAD_APP,
        request_delay=0,
    )
    response = app_client.request("", accept="text/html")
    try:
        html = response.body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise igem.IGEMError("The distribution application returned invalid HTML") from error
    environment = dict(_ENV_RE.findall(html))
    url = environment.get("PUBLIC_SUPABASE_URL")
    key = environment.get("PUBLIC_SUPABASE_KEY")
    if not url or not key:
        raise igem.IGEMError("Could not find the public kit data source in WellRead")
    return url, key


def fetch_distribution_records(
    year: int,
    *,
    data_source: tuple[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch all occupied wells for one distribution-kit year."""
    database_url, publishable_key = data_source or discover_data_source()
    client = igem.IGEMClient(
        api_base=f"{database_url.rstrip('/')}/rest/v1",
        request_delay=0.1,
    )
    headers = {
        "apikey": publishable_key,
        "Authorization": f"Bearer {publishable_key}",
    }
    records: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = client.request(
            "parts_full",
            params={
                "select": "*",
                "kit_year": f"eq.{year}",
                "order": "kit_plate.asc,well.asc",
                "offset": offset,
                "limit": PAGE_SIZE,
            },
            extra_headers=headers,
        )
        try:
            page = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise igem.IGEMError("The public kit database returned invalid JSON") from error
        if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
            raise igem.IGEMError("The public kit database returned an unexpected payload")
        records.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    if not records:
        raise igem.IGEMError(f"The public kit database has no records for {year}")
    records.sort(key=_record_sort_key)
    return records


def _record_sort_key(record: dict[str, Any]) -> tuple[int, str, int]:
    plate = record.get("kit_plate")
    well = str(record.get("well", "")).upper()
    match = _WELL_RE.fullmatch(well)
    if not isinstance(plate, int) or match is None:
        raise igem.IGEMError(f"Invalid plate/well in kit record: {plate!r}/{well!r}")
    return plate, match.group(1), int(match.group(2))


def _record_sequence(record: dict[str, Any]) -> str:
    raw = record.get("sequence")
    if not isinstance(raw, str):
        raise igem.IGEMError(f"Kit record {record.get('plate_well')!r} has no sequence")
    sequence = re.sub(r"\s+", "", raw).upper()
    if not sequence or _SEQUENCE_RE.fullmatch(sequence) is None:
        raise igem.IGEMError(
            f"Kit record {record.get('plate_well')!r} contains an invalid DNA sequence"
        )
    return sequence


def _record_name(record: dict[str, Any]) -> str:
    plate_well = igem._safe_filename(str(record.get("plate_well", "unknown-well")))
    plasmid = igem._safe_filename(str(record.get("plasmid_id", "unknown-plasmid")))
    return f"{plate_well}_{plasmid}"


def _genbank_date(record: dict[str, Any]) -> str:
    for field in ("updated_at", "created_at"):
        value = record.get(field)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).strftime("%d-%b-%Y").upper()
            except ValueError:
                pass
    return "01-JAN-1980"


def _origin(sequence: str) -> str:
    lines = ["ORIGIN\n"]
    for start in range(0, len(sequence), 60):
        segment = sequence[start : start + 60].lower()
        groups = " ".join(segment[index : index + 10] for index in range(0, len(segment), 10))
        lines.append(f"{start + 1:>9} {groups}\n")
    lines.append("//\n")
    return "".join(lines)


def _comment(record: dict[str, Any], sequence_length: int) -> str:
    reported = record.get("full_plasmid_seq_length")
    details = [
        f"iGEM Distribution Kit: {record.get('kit_year')}",
        f"Plate/well: {record.get('plate_well')}",
        f"Physical plasmid: {record.get('plasmid_id')}",
        f"Carried part: {record.get('part_id')}",
        f"Role: {record.get('part_role') or record.get('part_type')} ({record.get('so_id')})",
        f"Collection: {record.get('collection')}",
        f"Assembly format: {record.get('assembly_format')}",
        f"Backbone: {record.get('backbone_name')}",
        f"Resistance: {record.get('resistance')}",
        f"Copy number: {record.get('copy_number')}",
        f"Origin: {record.get('origin')}",
        f"QC: {record.get('qc_status')} (valid={record.get('is_valid')})",
        f"Sequence length: {sequence_length} bp (dataset reports {reported} bp)",
        f"Registry: {record.get('part_url')}",
        f"Inventory source: {DISTRIBUTION_PAGE}",
    ]
    optional_fields = [
        ("Flanking site", "flanking_site"),
        ("5' fusion", "flanking_5"),
        ("3' fusion", "flanking_3"),
        ("Assembly restriction site", "assembly_restriction_site"),
        ("Assembly 5' fusion", "assembly_5_fs"),
        ("Assembly 3' fusion", "assembly_3_fs"),
        ("Sequencing note", "sequencing_note"),
        ("SWAP", "swap"),
        ("SWAP note", "swap_note"),
    ]
    details.extend(
        f"{label}: {record[field]}"
        for label, field in optional_fields
        if record.get(field) not in (None, "")
    )
    return "COMMENT     " + "\n            ".join(igem._clean_qualifier(item) for item in details) + "\n"


def distribution_genbank(record: dict[str, Any]) -> str:
    """Create a circular GenBank record with all positional and kit metadata available."""
    sequence = _record_sequence(record)
    plasmid = igem._clean_qualifier(record.get("plasmid_id") or "distribution_plasmid")
    part = igem._clean_qualifier(record.get("part_id") or "unknown part")
    plate_well = igem._clean_qualifier(record.get("plate_well") or "unknown well")
    role = igem._clean_qualifier(record.get("part_role") or record.get("part_type") or "Part")
    accession = igem._clean_qualifier(record.get("so_id") or "")
    qc = igem._clean_qualifier(record.get("qc_status") or "Unknown")
    header = (
        f"LOCUS       {plasmid:<24}{len(sequence):>11} bp    DNA     circular SYN {_genbank_date(record)}\n"
        f"DEFINITION  {record.get('kit_year')} iGEM Distribution Kit plasmid {plasmid}, carrying {part}.\n"
        f"ACCESSION   {plasmid}\n"
        f"VERSION     {plasmid}\n"
        "KEYWORDS    iGEM; distribution kit; synthetic biology.\n"
        "SOURCE      synthetic DNA construct\n"
        "  ORGANISM  synthetic DNA construct\n"
        "            other sequences; artificial sequences.\n"
        + _comment(record, len(sequence))
        + "FEATURES             Location/Qualifiers\n"
        + f"     source          1..{len(sequence)}\n"
        + igem._qualifier("organism", "synthetic DNA construct")
        + igem._qualifier("mol_type", "other DNA")
        + igem._feature_block(
            key="misc_feature",
            location=f"1..{len(sequence)}",
            label=f"{plasmid} distribution plasmid",
            note=(
                f"{record.get('kit_year')} iGEM Distribution Kit {plate_well}; "
                f"carries {part}; {role}{f' ({accession})' if accession else ''}; QC {qc}"
            ),
        )
    )
    genbank = header + _origin(sequence)
    igem.validate_genbank(genbank)
    return genbank


def distribution_fasta(record: dict[str, Any]) -> str:
    sequence = _record_sequence(record)
    header = (
        f">{record.get('plate_well')}|{record.get('plasmid_id')} "
        f"part={record.get('part_id')} role={record.get('part_role') or record.get('part_type')} "
        f"qc={record.get('qc_status')} kit={record.get('kit_year')}"
    )
    lines = [sequence[index : index + 80] for index in range(0, len(sequence), 80)]
    return header + "\n" + "\n".join(lines) + "\n"


def _manifest_record(
    record: dict[str, Any],
    *,
    genbank_path: Path,
    fasta_path: Path | None,
) -> dict[str, Any]:
    sequence = _record_sequence(record)
    metadata = {key: value for key, value in record.items() if key != "sequence"}
    reported = record.get("full_plasmid_seq_length")
    return {
        **metadata,
        "actual_sequence_length": len(sequence),
        "length_matches_reported": reported == len(sequence),
        "sequence_sha256": hashlib.sha256(sequence.encode("ascii")).hexdigest(),
        "genbank_file": genbank_path.as_posix(),
        "fasta_file": fasta_path.as_posix() if fasta_path is not None else "",
    }


def _csv_bytes(records: list[dict[str, Any]]) -> bytes:
    fields: list[str] = []
    for record in records:
        for key in record:
            if key not in fields:
                fields.append(key)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue().encode("utf-8")


def _readme(result: DistributionResult, *, include_fasta: bool) -> str:
    qc = ", ".join(f"{key}: {value}" for key, value in sorted(result.qc_counts.items()))
    fasta_line = "- `fasta/`: one full-plasmid FASTA file per occupied well.\n" if include_fasta else ""
    return f"""# {result.year} iGEM Distribution Kit sequence snapshot

Source: {DISTRIBUTION_PAGE}

- Occupied wells: {result.records}
- Total sequence: {result.total_bp:,} bp
- QC statuses: {qc}
- Records marked invalid: {result.invalid_records}
- Dataset length mismatches: {result.length_mismatches}

## Contents

- `genbank/`: one circular, annotated GenBank file per occupied well. These files
  open directly in SnapGene.
{fasta_line}- `manifest.csv` and `manifest.json`: plate, well, part, plasmid, assembly,
  backbone, resistance, QC, checksums, and output paths.
- `kit_inventory.raw.json`: lossless snapshot of the public kit records, including
  the full plasmid sequences.
- `all_plasmids.fasta`: multi-FASTA snapshot when FASTA output is enabled.

The kit dataset provides full plasmid sequences and extensive construct metadata,
but not nucleotide coordinates for backbone elements. The GenBank files therefore
include all supplied metadata and a whole-plasmid feature without inventing feature
positions. Records with sequence discrepancies or failed sequencing are retained
because this snapshot includes every occupied kit well; consult `qc_status` and
`is_valid` before experimental use.
"""


def write_distribution(
    records: list[dict[str, Any]],
    output_dir: Path,
    *,
    year: int,
    include_fasta: bool,
    force: bool,
) -> DistributionResult:
    """Write an inventory snapshot and one sequence record per occupied well."""
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(f"{output_dir} is not empty (pass --force to replace files)")
    genbank_dir = output_dir / "genbank"
    fasta_dir = output_dir / "fasta"
    manifests: list[dict[str, Any]] = []
    all_fasta: list[str] = []
    total_bp = 0
    for record in records:
        sequence = _record_sequence(record)
        total_bp += len(sequence)
        name = _record_name(record)
        genbank_path = genbank_dir / f"{name}.gb"
        fasta_path = fasta_dir / f"{name}.fasta" if include_fasta else None
        igem._write(genbank_path, distribution_genbank(record).encode("utf-8"), force=force)
        if fasta_path is not None:
            fasta = distribution_fasta(record)
            igem._write(fasta_path, fasta.encode("utf-8"), force=force)
            all_fasta.append(fasta)
        manifests.append(
            _manifest_record(
                record,
                genbank_path=genbank_path.relative_to(output_dir),
                fasta_path=fasta_path.relative_to(output_dir) if fasta_path is not None else None,
            )
        )

    qc_counts = Counter(str(record.get("qc_status") or "Unknown") for record in records)
    result = DistributionResult(
        output_dir=output_dir,
        year=year,
        records=len(records),
        total_bp=total_bp,
        qc_counts=dict(qc_counts),
        invalid_records=sum(record.get("is_valid") is not True for record in records),
        length_mismatches=sum(
            record.get("full_plasmid_seq_length") != len(_record_sequence(record))
            for record in records
        ),
    )
    manifest = {
        "schemaVersion": 1,
        "kitYear": year,
        "source": DISTRIBUTION_PAGE,
        "embeddedApplication": WELLREAD_APP,
        "retrievedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "records": result.records,
            "totalBp": result.total_bp,
            "qcCounts": result.qc_counts,
            "invalidRecords": result.invalid_records,
            "lengthMismatches": result.length_mismatches,
        },
        "records": manifests,
    }
    igem._write(
        output_dir / "manifest.json",
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        force=force,
    )
    igem._write(output_dir / "manifest.csv", _csv_bytes(manifests), force=force)
    igem._write(
        output_dir / "kit_inventory.raw.json",
        (json.dumps(records, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        force=force,
    )
    if include_fasta:
        igem._write(
            output_dir / "all_plasmids.fasta",
            "".join(all_fasta).encode("utf-8"),
            force=force,
        )
    igem._write(
        output_dir / "README.md",
        _readme(result, include_fasta=include_fasta).encode("utf-8"),
        force=force,
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download every full plasmid sequence in an iGEM Distribution Kit."
    )
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--fasta", action="store_true", help="Also write per-well and combined FASTA")
    parser.add_argument("--force", action="store_true", help="Replace known files in a non-empty output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = args.output or Path(f"igem-distribution-kit-{args.year}")
    try:
        records = fetch_distribution_records(args.year)
        result = write_distribution(
            records,
            output,
            year=args.year,
            include_fasta=args.fasta,
            force=args.force,
        )
    except (igem.IGEMError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"Downloaded {result.records} occupied wells ({result.total_bp:,} bp) to "
        f"{result.output_dir}; QC={result.qc_counts}; invalid={result.invalid_records}; "
        f"length mismatches={result.length_mismatches}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
