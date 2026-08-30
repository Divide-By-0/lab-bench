#!/usr/bin/env python3
"""Build 55 CloningQA drafts from the tracked Addgene subset GBKs.

Each tracked GBK becomes one two-fragment CDS-swap task against a donor ORF
from another subset plasmid. Canonical protocols are Gibson (the same DSL as
the existing Gibson/Golden Gate CloningQA packs) and are executed with
cloning simulator v2. Shared inventory lives in cloning/shared/.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, SimpleLocation
from Bio.SeqRecord import SeqRecord

from lab_bench_2.addgene_inventory_subset import subset_gbk_dir, subset_plasmids
from lab_bench_2.cloning_simulators import execute_cloning_protocol_v2
from lab_bench_2.prompt_composer import CLONING_PROTOCOL_SUFFIX

VERSION = "addgene-subset-draft-1.0"
OVERLAP_LENGTH = 24
ANNEAL_LENGTHS = (18, 20, 22, 24, 28, 32, 36, 42)
STOPS = {"TAA", "TAG", "TGA"}
MIN_ORF = 90
MAX_ORF = 9000
MIN_PARTS_FOR_WRAP = 2
TINY_CDS_MAX = 120
SHORT_CARGO_MAX = 300
MIN_T7_PROMOTERS = 2
MAX_T7_MCS = 2000
MIN_CASSETTE = 300
MIN_INFERRED_ORF = 900
MAX_DONOR_LENGTH_DELTA = 8000
PAYLOAD_PATTERNS = (
    "cas9",
    "dcas9",
    "cre",
    "chr2",
    "hm3",
    "gaba",
    "luciferase",
    "tdtomato",
    "mcherry",
    "eyfp",
    "egfp",
    "gfp",
    "mbp",
    "vsug",
    "vsv-g",
    "vsv g",
    "puro",
    "neo",
    "kan",
    "amp",
    "cmr",
    "ha",
    "flag",
)
DONOR_PATTERNS = (
    "egfp",
    "gfp",
    "mcherry",
    "tdtomato",
    "eyfp",
)
TINY_LABELS = (
    "nls",
    "myc",
    "flag",
    "ha",
    "tev",
    "factor xa",
    "t2a",
    "p2a",
    "his6",
    "6xhis",
    "kozak",
    "wpre",
)
MARKER_LABELS = (
    "ampr",
    "ampicillin",
    "blar",
    "kanr",
    "neor",
    "puror",
    "cmr",
    "cat",
    "hygr",
    "blastr",
    "bleor",
    "bleo",
    "smr",
    "sacb",
    "ura3",
    "ccdb",
    "chloramphenicol",
    "spectinomycin",
    "his3",
)
PYDNA_ANNEAL_LIMIT = 15
ENZYMES = (
    "BamHI",
    "BbsI",
    "BsaI",
    "BsmBI",
    "EcoRI",
    "EcoRV",
    "HindIII",
    "KpnI",
    "NdeI",
    "NheI",
    "NotI",
    "PstI",
    "SacI",
    "SpeI",
    "XbaI",
    "XhoI",
)
GG_METHODS = frozenset({"golden_gate", "oligo_gg", "hierarchical_gg"})


@dataclass(frozen=True)
class OpenReadingFrame:
    """A coding interval copied from one circular inventory plasmid."""

    label: str
    start: int
    end: int
    sequence: str
    strand: int
    wrap: bool
    plasmid_id: int
    filename: str
    complete: bool
    source: str


@dataclass(frozen=True)
class DraftTask:
    """One CDS-swap cloning draft."""

    gbk_name: str
    plasmid_id: int
    backbone_name: str
    backbone_role: str
    catalog_method: str
    enzyme: str | None
    payload: OpenReadingFrame
    donor: OpenReadingFrame
    request: str
    solution: str
    gotchas: tuple[str, ...]
    map_note: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gbk-dir", type=Path, default=subset_gbk_dir())
    parser.add_argument(
        "--output", type=Path, default=Path("experiments/cloning_addgene_subset_v1")
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Write spliced references without executing cloning simulator v2",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reverse_complement(sequence: str) -> str:
    return str(Seq(sequence).reverse_complement())


def _feature_label(feature: SeqFeature) -> str:
    for key in ("label", "gene", "product", "note"):
        values = feature.qualifiers.get(key)
        if values:
            return re.sub(r"<[^>]+>", "", str(values[0])).strip()[:80]
    return ""


def _plasmid_id_from_name(name: str) -> int:
    match = re.search(r"addgene-plasmid-(\d+)-", name)
    if not match:
        raise ValueError(f"Cannot parse plasmid id from {name}")
    return int(match.group(1))


def _compact_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _same_protein(left: str, right: str) -> bool:
    a = _compact_label(left)
    b = _compact_label(right)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    aliases = (
        {"gfp", "egfp", "sfGFP", "superfoldergfp", "eyfp", "yfp"},
        {"mcherry", "tdtomato", "rfp"},
        {"cas9", "spcas9", "sacas9", "dcas9", "cas9d10a"},
        {"ampr", "ampicillin", "blar"},
        {"kanr", "neor", "neomycin", "kanamycin"},
    )
    compact_aliases = [{_compact_label(item) for item in group} for group in aliases]
    for group in compact_aliases:
        if any(token and token in a for token in group) and any(
            token and token in b for token in group
        ):
            return True
    return False


def _catalog_by_id() -> dict[int, Any]:
    return {entry.plasmid_id: entry for entry in subset_plasmids()}


def _task_id(filename: str, donor_filename: str, payload: str, donor: str) -> str:
    seed = f"{VERSION}:{filename}:{donor_filename}:{payload}:{donor}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _merged_interval(
    feature: SeqFeature, plasmid_length: int
) -> tuple[int, int, int, bool] | None:
    """Collapse SnapGene codon/site splits; keep origin-wrapping CDSs.

    SnapGene often stores a single CDS as adjacent CompoundLocation parts
    (AmpR split at a silent join, EGFP split codon-by-codon). Treating those
    as incomplete drops most cargo genes. A true origin wrap is a separate
    case used for some Cas9 annotations.
    """
    parts = [
        (int(part.start), int(part.end), int(part.strand or 1))
        for part in feature.location.parts
    ]
    if not parts:
        return None
    strands = {strand for _, _, strand in parts}
    if len(strands) != 1:
        return None
    strand = next(iter(strands))
    ordered = sorted(parts, key=lambda item: item[0])
    wrap = (
        len(ordered) >= MIN_PARTS_FOR_WRAP
        and ordered[0][0] == 0
        and ordered[-1][1] == plasmid_length
        and ordered[0][1] < ordered[-1][0]
    )
    if wrap:
        gap_ok = all(
            ordered[index][1] == ordered[index + 1][0]
            for index in range(len(ordered) - 2)
        )
        if not gap_ok:
            return None
        return ordered[-1][0], ordered[0][1], strand, True
    start, end, _ = ordered[0]
    for next_start, next_end, _ in ordered[1:]:
        if next_start != end:
            return None
        end = next_end
    return start, end, strand, False


def _is_complete(sequence: str) -> bool:
    return (
        sequence.startswith("ATG")
        and sequence[-3:] in STOPS
        and len(sequence) % 3 == 0
        and MIN_ORF <= len(sequence) <= MAX_ORF
    )


def _cds_from_feature(
    feature: SeqFeature, record: SeqRecord, plasmid_id: int, filename: str
) -> OpenReadingFrame | None:
    plasmid_length = len(record.seq)
    merged = _merged_interval(feature, plasmid_length)
    if merged is None:
        return None
    start, end, strand, wrap = merged
    sequence = str(feature.extract(record.seq)).upper()
    if len(sequence) % 3 != 0 or not (MIN_ORF <= len(sequence) <= MAX_ORF):
        return None
    label = _feature_label(feature) or f"CDS_{start}_{end}"
    if _contains_any(label.lower(), TINY_LABELS) and len(sequence) < TINY_CDS_MAX:
        return None
    return OpenReadingFrame(
        label,
        start,
        end,
        sequence,
        strand,
        wrap,
        plasmid_id,
        filename,
        _is_complete(sequence),
        "cds",
    )


def _orfs_from_sequence(
    sequence: str, plasmid_id: int, filename: str
) -> list[OpenReadingFrame]:
    found: list[OpenReadingFrame] = []
    rc_sequence = _reverse_complement(sequence)
    for strand, text in ((1, sequence), (-1, rc_sequence)):
        length = len(text)
        start_at = 0
        while True:
            start_at = text.find("ATG", start_at)
            if start_at < 0 or start_at > length - 6:
                break
            for stop_at in range(start_at + 3, length - 2, 3):
                codon = text[stop_at : stop_at + 3]
                if codon not in STOPS:
                    continue
                coding = text[start_at : stop_at + 3]
                if MIN_ORF <= len(coding) <= MAX_ORF:
                    if strand == 1:
                        start, end = start_at, stop_at + 3
                    else:
                        start, end = length - (stop_at + 3), length - start_at
                    found.append(
                        OpenReadingFrame(
                            f"unannotated CDS ({start}-{end})",
                            start,
                            end,
                            coding,
                            strand,
                            False,
                            plasmid_id,
                            filename,
                            True,
                            "orf",
                        )
                    )
                break
            start_at += 3
    return found


def _landmark_payloads(
    record: SeqRecord, plasmid_id: int, filename: str
) -> list[OpenReadingFrame]:
    t7: list[tuple[int, int, int]] = []
    for feature in record.features:
        if feature.type != "promoter":
            continue
        if "t7" not in _feature_label(feature).lower():
            continue
        start = int(feature.location.start)
        end = int(feature.location.end)
        strand = int(feature.location.strand or 1)
        t7.append((start, end, strand))
    if len(t7) < MIN_T7_PROMOTERS:
        return []
    plus = min((item for item in t7 if item[2] == 1), default=None)
    minus = min((item for item in t7 if item[2] == -1), default=None)
    if plus is None or minus is None or minus[0] <= plus[1]:
        return []
    start, end = plus[1], minus[0]
    interval = str(record.seq[start:end]).upper()
    if len(interval) >= MAX_T7_MCS:
        return []
    return [
        OpenReadingFrame(
            "region between the T7 promoters",
            start,
            end,
            interval,
            1,
            False,
            plasmid_id,
            filename,
            False,
            "landmark",
        )
    ]


def _cassette_payload(
    record: SeqRecord, plasmid_id: int, filename: str
) -> OpenReadingFrame | None:
    """Span Kozak/signal-peptide through the last plus-strand cargo CDS.

    iGABASnFR and similar sensors are split into leader/tag/TM CDS fragments,
    so replacing any one fragment is not the cargo swap a scientist expects.
    """
    starts: list[int] = []
    for feature in record.features:
        label = _feature_label(feature).lower()
        if feature.type in {"sig_peptide", "regulatory"} or "kozak" in label:
            starts.append(int(feature.location.start))
    if not starts:
        return None
    cds_ends: list[int] = []
    start = min(starts)
    for feature in record.features:
        if feature.type != "CDS":
            continue
        if int(feature.location.strand or 1) != 1:
            continue
        label = _feature_label(feature).lower()
        if _contains_any(label, MARKER_LABELS + TINY_LABELS):
            continue
        end = int(feature.location.end)
        feat_start = int(feature.location.start)
        if feat_start >= start - 50:
            cds_ends.append(end)
    if not cds_ends:
        return None
    end = max(cds_ends)
    if end - start < MIN_CASSETTE:
        return None
    interval = str(record.seq[start:end]).upper()
    return OpenReadingFrame(
        "primary cargo",
        start,
        end,
        interval,
        1,
        False,
        plasmid_id,
        filename,
        False,
        "landmark",
    )


def _collect_orfs(
    record: SeqRecord, plasmid_id: int, filename: str
) -> list[OpenReadingFrame]:
    found: list[OpenReadingFrame] = []
    seen: set[tuple[int, int, int]] = set()
    for feature in record.features:
        if feature.type != "CDS":
            continue
        orf = _cds_from_feature(feature, record, plasmid_id, filename)
        if orf is None:
            continue
        key = (orf.start, orf.end, orf.strand)
        if key in seen:
            continue
        seen.add(key)
        found.append(orf)
    for orf in _orfs_from_sequence(str(record.seq).upper(), plasmid_id, filename):
        key = (orf.start, orf.end, orf.strand)
        if key in seen or len(orf.sequence) < MIN_INFERRED_ORF:
            continue
        if any(_intervals_overlap(orf, other) for other in found):
            continue
        seen.add(key)
        found.append(orf)
    for orf in _landmark_payloads(record, plasmid_id, filename):
        key = (orf.start, orf.end, orf.strand)
        if key in seen:
            continue
        seen.add(key)
        found.append(orf)
    cassette = _cassette_payload(record, plasmid_id, filename)
    if cassette is not None:
        key = (cassette.start, cassette.end, cassette.strand)
        if key not in seen:
            seen.add(key)
            found.append(cassette)
    return found


def _intervals_overlap(left: OpenReadingFrame, right: OpenReadingFrame) -> bool:
    if left.wrap or right.wrap or left.strand != right.strand:
        return False
    return left.start < right.end and right.start < left.end


def _is_marker(orf: OpenReadingFrame) -> bool:
    return _contains_any(orf.label.lower(), MARKER_LABELS)


def _score_payload(orf: OpenReadingFrame) -> tuple[int, int, int]:
    text = orf.label.lower()
    if _contains_any(text, TINY_LABELS) and len(orf.sequence) < SHORT_CARGO_MAX:
        return (-50, 0, 0)
    if _is_marker(orf):
        return (-100, 1 if orf.complete else 0, len(orf.sequence))
    if len(orf.sequence) < SHORT_CARGO_MAX and orf.source == "cds":
        return (-40, 0, len(orf.sequence))
    rank = 10
    for index, pattern in enumerate(PAYLOAD_PATTERNS):
        if pattern in text:
            rank = 200 - index
            break
    if orf.source == "orf":
        rank = 40 + min(len(orf.sequence) // 50, 50)
    if orf.source == "landmark":
        rank = 90
    complete = 1 if orf.complete else 0
    return rank, complete, len(orf.sequence)


def _score_donor(orf: OpenReadingFrame) -> tuple[int, int, int]:
    text = orf.label.lower()
    rank = 0
    for index, pattern in enumerate(DONOR_PATTERNS):
        if pattern in text:
            rank = 100 - index
            break
    if _contains_any(text, MARKER_LABELS):
        rank -= 10
    if orf.source == "orf":
        rank -= 30
    return rank, 1 if orf.complete else 0, -len(orf.sequence)


def _remaining(destination: str, payload: OpenReadingFrame) -> str:
    if payload.wrap:
        return destination[payload.end : payload.start]
    return destination[payload.end :] + destination[: payload.start]


def _primers(backbone: str, insert: str, anneal: int) -> dict[str, str]:
    return {
        "backbone_forward": backbone[:anneal],
        "backbone_reverse": _reverse_complement(backbone[-anneal:]),
        "insert_forward": backbone[-OVERLAP_LENGTH:] + insert[:anneal],
        "insert_reverse": (
            _reverse_complement(backbone[:OVERLAP_LENGTH])
            + _reverse_complement(insert[-anneal:])
        ),
    }


def _primer_unique(template: str, primer_3p: str) -> bool:
    # REASON: pydna PCR uses limit=15, so a 24-mer whose 3' 15 bp occurs twice
    # is rejected as non-specific even if the full primer is unique.
    footprint = primer_3p[-PYDNA_ANNEAL_LIMIT:]
    rc_template = _reverse_complement(template)
    hits = template.count(footprint) + rc_template.count(footprint)
    return hits == 1


def _gibson_protocol(dest_file: str, source_file: str, primers: dict[str, str]) -> str:
    return (
        "<protocol>\n"
        "gibson(\n"
        f'    pcr({dest_file}, "{primers["backbone_forward"]}", '
        f'"{primers["backbone_reverse"]}"),\n'
        f'    pcr({source_file}, "{primers["insert_forward"]}", '
        f'"{primers["insert_reverse"]}")\n'
        ")\n"
        "</protocol>"
    )


def _protocol_expression(protocol: str) -> str:
    if "<protocol>" in protocol:
        return protocol.split("<protocol>", 1)[1].split("</protocol>", 1)[0]
    return protocol


def _circular_match(first: str, second: str) -> bool:
    if len(first) != len(second):
        return False
    doubled = second + second
    return first in doubled or _reverse_complement(first) in doubled


def _write_fasta(record: SeqRecord, path: Path) -> None:
    sequence = str(record.seq).upper()
    lines = [
        f">{record.id}: {record.description} (circular)",
        *(sequence[index : index + 80] for index in range(0, len(sequence), 80)),
    ]
    path.write_text("\n".join(lines) + "\n")


def _gg_enzyme(entry: Any | None) -> str | None:
    if entry is None or entry.assembly_method not in GG_METHODS:
        return None
    note = entry.assembly_note.lower()
    if "bbsi" in note or "bpi" in note:
        return "BbsI"
    if "bsmbi" in note or "esp3i" in note:
        return "BsmBI"
    if "sapi" in note:
        return "SapI"
    return "BsaI"


def _question_text(task: DraftTask) -> str:
    if task.catalog_method in GG_METHODS and task.enzyme:
        method = (
            f"Golden Gate assembly with {task.enzyme} or Gibson assembly "
            "(Type IIS enzymes are stocked)"
        )
    else:
        method = "Gibson assembly"
    inversion = ""
    if task.payload.strand == -1:
        inversion = (
            " The current coding sequence is inverted relative to the promoter; "
            "install the replacement in the same inverted orientation."
        )
    map_bit = f" ({task.map_note})" if task.map_note else ""
    role = task.backbone_role.split(";")[0].strip()
    keep = (
        "Keep the rest of the selected backbone, including its origin."
        if _is_marker(task.payload)
        else (
            "Keep the rest of the selected backbone, including its origin and "
            "selectable marker."
        )
    )
    target = (
        task.payload.label
        if task.payload.source == "landmark"
        else f"{task.payload.label} coding sequence"
    )
    return (
        f"Could you replace the {target} on one of our {role} plasmids{map_bit} "
        f"with {task.donor.label} from the attached inventory using {method}? "
        f"{keep}{inversion}\n\n"
        "All available Addgene plasmids and stocked enzymes are in the attached "
        "task inventory. Do not synthesize genes de novo; obtain the gene "
        "sequences you need from that inventory."
    )


def _write_shared_inventory(gbk_dir: Path, shared: Path) -> dict[str, str]:
    shared.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for path in sorted(gbk_dir.glob("addgene-plasmid-*.gbk")):
        dest = shared / path.name
        shutil.copy2(path, dest)
        hashes[path.name] = _sha256(dest)
    for index, enzyme in enumerate(ENZYMES, start=1):
        (shared / f"enzyme-{index:02d}.txt").write_text(enzyme + "\n")
    rows = ["filename\tenzyme"]
    rows.extend(
        f"enzyme-{index:02d}.txt\t{enzyme}"
        for index, enzyme in enumerate(ENZYMES, start=1)
    )
    (shared / "enzyme_inventory.tsv").write_text("\n".join(rows) + "\n")
    return hashes


def _map_note(filename: str, record: SeqRecord, catalog: dict[int, Any]) -> str:
    plasmid_id = _plasmid_id_from_name(filename)
    entry = catalog.get(plasmid_id)
    if entry is None or entry.sequence_source != "all":
        return ""
    return f"{len(record.seq)} bp map"


def _donor_pool(
    orfs_by_file: dict[str, list[OpenReadingFrame]],
) -> list[OpenReadingFrame]:
    donors = [
        orf
        for orfs in orfs_by_file.values()
        for orf in orfs
        if orf.complete
        and orf.source == "cds"
        and not _is_marker(orf)
        and _contains_any(orf.label.lower(), DONOR_PATTERNS)
        and not _contains_any(orf.label.lower(), TINY_LABELS)
    ]
    donors.sort(key=_score_donor, reverse=True)
    return donors


def _compatible_donors(
    filename: str,
    plasmid_id: int,
    payload: OpenReadingFrame,
    donor_pool: list[OpenReadingFrame],
) -> list[OpenReadingFrame]:
    compatible: list[OpenReadingFrame] = []
    seen: set[tuple[str, str]] = set()
    for candidate in donor_pool:
        if candidate.filename == filename or candidate.plasmid_id == plasmid_id:
            continue
        if _same_protein(candidate.label, payload.label):
            continue
        if (
            abs(len(candidate.sequence) - max(len(payload.sequence), 1))
            > MAX_DONOR_LENGTH_DELTA
        ):
            continue
        key = (candidate.filename, candidate.label)
        if key in seen:
            continue
        seen.add(key)
        compatible.append(candidate)
    return compatible


def _make_task(
    filename: str,
    records: dict[str, SeqRecord],
    catalog: dict[int, Any],
    payload: OpenReadingFrame,
    donor: OpenReadingFrame,
) -> DraftTask:
    plasmid_id = _plasmid_id_from_name(filename)
    entry = catalog.get(plasmid_id)
    request = (
        f"Replace {payload.label} on {filename} with {donor.label} from "
        f"{donor.filename}"
    )
    solution = (
        f"PCR-amplify the {filename} backbone outside {payload.label} "
        f"({payload.start}:{payload.end}"
        f"{', wrapping the origin' if payload.wrap else ''}) and Gibson-"
        f"assemble it to the complete {donor.label} CDS from {donor.filename}."
    )
    gotchas = tuple(gotcha.summary for gotcha in entry.gotchas) if entry else ()
    return DraftTask(
        filename,
        plasmid_id,
        entry.name if entry else filename,
        entry.role if entry else "plasmid",
        entry.assembly_method if entry else "gibson",
        _gg_enzyme(entry),
        payload,
        donor,
        request,
        solution,
        gotchas,
        _map_note(filename, records[filename], catalog),
    )


async def _verify_protocol(
    protocol: str, shared: Path, assembled: str
) -> tuple[list[Any], list[int]]:
    expression = _protocol_expression(protocol)
    products = await execute_cloning_protocol_v2(expression, shared)
    matches = [
        index
        for index, product in enumerate(products)
        if getattr(product, "is_circular", False)
        and _circular_match(str(product.sequence).upper(), assembled)
    ]
    return products, matches


def _choose_primers(
    remaining: str, insert: str, dest_seq: str, donor_seq: str
) -> dict[str, str] | None:
    for anneal in ANNEAL_LENGTHS:
        if len(remaining) < max(OVERLAP_LENGTH, anneal) * 2:
            continue
        if len(insert) < anneal:
            continue
        primers = _primers(remaining, insert, anneal)
        if not _primer_unique(dest_seq, primers["backbone_forward"]):
            continue
        if not _primer_unique(dest_seq, primers["backbone_reverse"]):
            continue
        if not _primer_unique(donor_seq, insert[:anneal]):
            continue
        if not _primer_unique(donor_seq, _reverse_complement(insert[-anneal:])):
            continue
        return primers
    return None


async def _verify_and_write(
    task: DraftTask,
    records: dict[str, SeqRecord],
    shared: Path,
    output: Path,
    *,
    skip_verify: bool,
) -> dict[str, Any] | None:
    destination = records[task.gbk_name]
    dest_seq = str(destination.seq).upper()
    remaining = _remaining(dest_seq, task.payload)
    insert = task.donor.sequence
    if task.payload.strand == -1:
        # REASON: FLEX/DIO cargos are antisense to the promoter. Replacing with
        # the plus-strand donor CDS would make a Cre-independent reporter.
        # Installing the reverse complement keeps the inversion the map encodes.
        insert = _reverse_complement(task.donor.sequence)
    if len(remaining) < OVERLAP_LENGTH * 2:
        return None
    donor_seq = str(records[task.donor.filename].seq).upper()
    primers = _choose_primers(remaining, insert, dest_seq, donor_seq)
    if primers is None:
        return None
    protocol = _gibson_protocol(task.gbk_name, task.donor.filename, primers)
    assembled = insert + remaining
    task_id = _task_id(
        task.gbk_name, task.donor.filename, task.payload.label, task.donor.label
    )
    products: list[Any] = []
    matches = [0]
    verified = False
    if skip_verify:
        verified = False
    else:
        try:
            products, matches = await _verify_protocol(protocol, shared, assembled)
        except Exception:
            return None
        if not matches:
            return None
        verified = True
    record = SeqRecord(
        Seq(assembled),
        id=task_id,
        name=f"swap-{task.plasmid_id}"[:16],
        description=(
            f"{task.gbk_name} CDS {task.payload.label!r} replaced with "
            f"{task.donor.label!r} from {task.donor.filename}"
        ),
    )
    record.annotations = {
        "molecule_type": "DNA",
        "topology": "circular",
        "comment": record.description,
    }
    record.features = [
        SeqFeature(SimpleLocation(0, len(assembled)), type="source"),
        SeqFeature(
            SimpleLocation(0, len(insert), strand=1),
            type="CDS",
            qualifiers={
                "label": [task.donor.label],
                "note": [f"from {task.donor.filename}"],
            },
        ),
    ]
    fasta_path = output / "validation" / f"{task_id}_assembled.fa"
    gbk_path = output / "validation" / f"{task_id}_assembled.gbk"
    protocol_path = output / "canonical_protocols" / f"{task_id}.txt"
    _write_fasta(record, fasta_path)
    SeqIO.write([record], gbk_path, "genbank")
    protocol_path.write_text(protocol + "\n")
    question = {
        "id": task_id,
        "tag": "cloning",
        "version": VERSION,
        "type": "gibson",
        "question": _question_text(task),
        "ideal": "",
        "files": "cloning/shared",
        "sources": [
            f"https://www.addgene.org/{task.plasmid_id}/",
            f"https://www.addgene.org/{task.donor.plasmid_id}/",
        ],
        "prompt_suffix": CLONING_PROTOCOL_SUFFIX,
        "validator_params": "{}",
        "answer_regex": "",
        "mode": {"inject": True, "file": True, "retrieve": True},
        "difficulty": {
            "name": "addgene_subset_cds_swap",
            "method": (
                "goldengate_or_gibson"
                if task.catalog_method in GG_METHODS
                else "gibson"
            ),
            "catalog_method": task.catalog_method,
            "component_count": 2,
            "backbone_file": task.gbk_name,
            "donor_file": task.donor.filename,
            "enzyme": task.enzyme,
        },
    }
    return {
        "question": question,
        "review": {
            "id": task_id,
            "backbone_file": task.gbk_name,
            "backbone_addgene_id": task.plasmid_id,
            "backbone_name": task.backbone_name,
            "backbone_role": task.backbone_role,
            "map_note": task.map_note,
            "catalog_method": task.catalog_method,
            "enzyme": task.enzyme,
            "replace_cds": task.payload.label,
            "replace_interval": [task.payload.start, task.payload.end],
            "replace_strand": task.payload.strand,
            "replace_wraps_origin": task.payload.wrap,
            "donor_file": task.donor.filename,
            "donor_addgene_id": task.donor.plasmid_id,
            "donor_cds": task.donor.label,
            "product_length_bp": len(assembled),
            "canonical_protocol": protocol,
            "solution": task.solution,
            "gotchas": list(task.gotchas),
            "simulator_match_index": matches[0] if matches else None,
            "simulator_product_count": len(products),
            "simulator_verified": verified,
        },
    }


def _write_answer_keys(output: Path, reviews: list[dict[str, Any]]) -> None:
    lines = [
        "# Scientist answer keys — Addgene subset cloning drafts",
        "",
        "Drop this file with the JSONL. Each row is a two-fragment CDS swap.",
        "Canonical protocols are Gibson and were checked with cloning simulator",
        "v2 against the exact circular FASTA in `validation/`. Another",
        "biologically valid architecture may still fail the exact-reference",
        "scorer. Golden Gate backbones are included as destinations; the",
        "verified key is still the Gibson product of the same CDS swap.",
        "",
        "| # | Addgene | Backbone | Replace | Donor CDS (file) | Catalog method | bp | Verified |",
        "| --- | ---: | --- | --- | --- | --- | ---: | --- |",
    ]
    for index, review in enumerate(reviews, start=1):
        verified = "yes" if review["simulator_verified"] else "spliced only"
        name = review["backbone_name"]
        if review["map_note"]:
            name = f"{name} ({review['map_note']})"
        lines.append(
            f"| {index} | {review['backbone_addgene_id']} | "
            f"{name} | {review['replace_cds']} | "
            f"{review['donor_cds']} (`{review['donor_file']}`) | "
            f"{review['catalog_method']} | {review['product_length_bp']} | "
            f"{verified} |"
        )
    lines.extend(["", "## Canonical protocols", ""])
    for review in reviews:
        gotcha_block = ""
        if review["gotchas"]:
            gotcha_block = "\n".join(f"- {item}" for item in review["gotchas"]) + "\n\n"
        orientation = (
            "Inverted cargo: replacement is reverse-complemented.\n\n"
            if review["replace_strand"] == -1
            else ""
        )
        lines.extend(
            [
                f"### {review['backbone_addgene_id']} `{review['id']}`",
                "",
                f"**File:** `{review['backbone_file']}`",
                "",
                review["solution"],
                "",
                orientation + gotcha_block,
                "```text",
                review["canonical_protocol"].strip(),
                "```",
                "",
            ]
        )
    (output / "ANSWER_KEYS.md").write_text("\n".join(lines) + "\n")
    tsv_path = output / "answer_keys.tsv"
    fieldnames = [
        "n",
        "id",
        "addgene_id",
        "backbone_name",
        "backbone_file",
        "map_note",
        "replace_cds",
        "replace_interval",
        "replace_strand",
        "donor_cds",
        "donor_file",
        "catalog_method",
        "enzyme",
        "product_length_bp",
        "simulator_verified",
        "gotchas",
        "solution",
    ]
    with tsv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for index, review in enumerate(reviews, start=1):
            writer.writerow(
                {
                    "n": index,
                    "id": review["id"],
                    "addgene_id": review["backbone_addgene_id"],
                    "backbone_name": review["backbone_name"],
                    "backbone_file": review["backbone_file"],
                    "map_note": review["map_note"],
                    "replace_cds": review["replace_cds"],
                    "replace_interval": (
                        f"{review['replace_interval'][0]}:{review['replace_interval'][1]}"
                    ),
                    "replace_strand": review["replace_strand"],
                    "donor_cds": review["donor_cds"],
                    "donor_file": review["donor_file"],
                    "catalog_method": review["catalog_method"],
                    "enzyme": review["enzyme"] or "",
                    "product_length_bp": review["product_length_bp"],
                    "simulator_verified": review["simulator_verified"],
                    "gotchas": " | ".join(review["gotchas"]),
                    "solution": review["solution"],
                }
            )


def _write_readme(
    output: Path, gbk_dir: Path, questions: list[dict[str, Any]], verified: int
) -> None:
    try:
        gbk_display = gbk_dir.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        gbk_display = "src/lab_bench_2/addgene_inventory_subset_gbk"
    (output / "README.md").write_text(
        "\n".join(
            [
                "# Addgene subset cloning drafts",
                "",
                f"{len(questions)} two-fragment CDS-swap CloningQA questions",
                f"generated from `{gbk_display}` ({verified} verified with cloning",
                "simulator v2 / pydna).",
                "",
                "Each record uses the shared inventory in `cloning/shared/`",
                "(all 55 tracked GBKs plus the 16-enzyme stock). Exact circular",
                "references live in `validation/<id>_assembled.fa`. Scientist",
                "keys: `ANSWER_KEYS.md` and `answer_keys.tsv`.",
                "",
                "Run with GPT-5.6-sol:",
                "",
                "```bash",
                "uv run inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \\",
                "  -T tags=cloning -T mode=file -T solver=agentic \\",
                f'  -T dataset_path="$PWD/{output.as_posix()}/questions.jsonl" \\',
                "  --model openai/gpt-5.6-sol --reasoning-effort max",
                "```",
                "",
                "Regenerate:",
                "",
                "```bash",
                "uv run --extra lab_bench_2 python tools/generate_addgene_subset_questions.py",
                "```",
                "",
            ]
        )
        + "\n"
    )


async def _generate(gbk_dir: Path, output: Path, limit: int, skip_verify: bool) -> None:
    catalog = _catalog_by_id()
    filenames = sorted(path.name for path in gbk_dir.glob("addgene-plasmid-*.gbk"))
    records = {name: SeqIO.read(gbk_dir / name, "genbank") for name in filenames}
    orfs_by_file = {
        name: _collect_orfs(record, _plasmid_id_from_name(name), name)
        for name, record in records.items()
    }
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "validation").mkdir()
    (output / "canonical_protocols").mkdir()
    shared = output / "cloning" / "shared"
    hashes = _write_shared_inventory(gbk_dir, shared)

    donor_pool = _donor_pool(orfs_by_file)
    questions: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    skipped: list[str] = []
    for filename in filenames:
        payloads = sorted(
            orfs_by_file.get(filename, []), key=_score_payload, reverse=True
        )
        if not payloads:
            skipped.append(filename)
            continue
        non_markers = [orf for orf in payloads if not _is_marker(orf)]
        markers = [orf for orf in payloads if _is_marker(orf)]
        preferred = [orf for orf in non_markers if orf.source in {"cds", "landmark"}]
        inferred = [orf for orf in non_markers if orf.source == "orf"]
        ordered_payloads = preferred + inferred[:3] + markers
        plasmid_id = _plasmid_id_from_name(filename)
        rotated_donors = (
            donor_pool[plasmid_id % len(donor_pool) :]
            + donor_pool[: plasmid_id % len(donor_pool)]
            if donor_pool
            else []
        )
        result = None
        for payload in ordered_payloads:
            for donor in _compatible_donors(
                filename, plasmid_id, payload, rotated_donors
            ):
                draft = _make_task(filename, records, catalog, payload, donor)
                result = await _verify_and_write(
                    draft, records, shared, output, skip_verify=skip_verify
                )
                if result is not None:
                    break
            if result is not None:
                break
        if result is None:
            skipped.append(filename)
            continue
        questions.append(result["question"])
        reviews.append(result["review"])
        if limit and len(questions) >= limit:
            break

    target = limit or 55
    if len(questions) < target:
        print(
            f"warning: wrote {len(questions)} / {target}; skipped {skipped}",
            flush=True,
        )
    (output / "questions.jsonl").write_text(
        "".join(json.dumps(question, sort_keys=True) + "\n" for question in questions)
    )
    (output / "reviews.json").write_text(json.dumps(reviews, indent=2) + "\n")
    _write_answer_keys(output, reviews)
    verified = sum(1 for review in reviews if review["simulator_verified"])
    _write_readme(output, gbk_dir, questions, verified)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "question_count": len(questions),
                "simulator_verified": verified,
                "skip_verify": skip_verify,
                "shared_inventory_sha256": hashes,
                "tasks": reviews,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {len(questions)} questions to {output} ({verified} verified)")
    if skipped:
        print(f"skipped {len(skipped)}: {skipped}")


def main() -> None:
    args = _parse_args()
    asyncio.run(_generate(args.gbk_dir, args.output, args.limit, args.skip_verify))


if __name__ == "__main__":
    main()
