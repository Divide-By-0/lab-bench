#!/usr/bin/env python3
"""Generate six matched CloningQA task triplets from an Addgene inventory."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, SeqFeature, SimpleLocation
from Bio.SeqRecord import SeqRecord

from lab_bench_2.cloning_question_dials import (
    BASELINE,
    DIFFICULTY_PROFILES,
    INVENTORY_FUNCTIONAL,
    METHOD_BLIND,
    CloningQuestionSpec,
    DifficultyDials,
    InventoryItem,
    render_cloning_question,
)
from lab_bench_2.cloning_simulators import execute_cloning_protocol_v2
from lab_bench_2.prompt_composer import CLONING_PROTOCOL_SUFFIX

OVERLAP_LENGTH = 24
ANNEAL_LENGTH = 24
MIN_FEATURE_LENGTH = 10
VERSION = "inventory-pilot-1.0"
OUTPUT_DEFAULT = Path("experiments/cloning_inventory_pilot_v1")


@dataclass(frozen=True)
class PlasmidSpec:
    """One Addgene inventory entry exposed to the model."""

    addgene_id: int
    name: str
    description: str

    @property
    def filename(self) -> str:
        return f"addgene-{self.addgene_id}.gbk"


@dataclass(frozen=True)
class TaskSpec:
    """One deterministic replacement and its three prompt renderings."""

    slug: str
    title: str
    destination_id: int
    delete_start: int
    delete_end: int
    source_id: int
    source_start: int
    source_end: int
    inventory_ids: tuple[int, ...]
    goal: str
    exact_architecture: tuple[str, ...]
    functional_requirements: tuple[str, ...]
    preservation_rule: str
    inserted_label: str
    restored_destination_prefix: tuple[int, int] | None = None
    truncated_cds_label: str | None = None
    manual_destination_features: tuple[tuple[int, int, str, str], ...] = ()


PLASMIDS = {
    1864: PlasmidSpec(
        1864,
        "pLKO.1 scrambled shRNA",
        "a third-generation lentiviral U6 scrambled-shRNA control with "
        "puromycin selection",
    ),
    8449: PlasmidSpec(
        8449,
        "pUMVC",
        "a MuLV gag-pol packaging plasmid rather than a transfer vector",
    ),
    10878: PlasmidSpec(
        10878,
        "pLKO.1",
        "a third-generation lentiviral U6-shRNA transfer plasmid with "
        "puromycin selection",
    ),
    12253: PlasmidSpec(
        12253,
        "pRSV-Rev",
        "a lentiviral Rev packaging plasmid rather than a transfer vector",
    ),
    12259: PlasmidSpec(
        12259,
        "pMD2.G",
        "a CMV-driven VSV-G lentiviral envelope plasmid",
    ),
    12260: PlasmidSpec(
        12260,
        "psPAX2",
        "a second-generation lentiviral gag-pol packaging plasmid",
    ),
    12456: PlasmidSpec(
        12456,
        "M50 Super 8x TOPFlash",
        "a TCF/LEF minimal-promoter firefly-luciferase reporter plasmid",
    ),
    13031: PlasmidSpec(
        13031,
        "pcDNA3-EGFP",
        "a CMV-EGFP mammalian expression plasmid with neomycin selection",
    ),
    13770: PlasmidSpec(
        13770,
        "pCALNL-GFP",
        "a Cre-dependent GFP plasmid with a loxP-flanked transcriptional stop",
    ),
    19319: PlasmidSpec(
        19319,
        "pLJM1-EGFP",
        "a third-generation CMV-EGFP lentiviral transfer vector with an "
        "independent hPGK-puromycin cassette",
    ),
    21915: PlasmidSpec(
        21915,
        "Tet-pLKO-puro",
        "a Tet-inducible lentiviral shRNA plasmid with TetR-IRES-puromycin",
    ),
    27705: PlasmidSpec(
        27705,
        "pmCherry-N1",
        "a constitutive mammalian mCherry plasmid with neomycin selection",
    ),
    37237: PlasmidSpec(
        37237,
        "pET MBP-6xHis",
        "a T7 bacterial expression plasmid encoding MBP followed by a "
        "C-terminal 6xHis tag",
    ),
    40315: PlasmidSpec(
        40315,
        "pET OmpA-6xHis",
        "a T7 bacterial expression vector with an OmpA signal peptide and 6xHis tag",
    ),
    42230: PlasmidSpec(
        42230,
        "pX330",
        "a CAG-Cas9 and U6-guide-RNA plasmid without a linked reporter or "
        "mammalian selectable marker",
    ),
    48138: PlasmidSpec(
        48138,
        "pSpCas9(BB)-2A-GFP (PX458)",
        "a CAG-Cas9-T2A-EGFP plasmid with a U6 guide-RNA cassette",
    ),
    52961: PlasmidSpec(
        52961,
        "lentiCRISPR v2",
        "a third-generation lentiviral Cas9-P2A-puromycin plasmid with a U6 "
        "guide-RNA cassette",
    ),
    54856: PlasmidSpec(
        54856,
        "pBAD 6xHis-TEV-tdTomato",
        "an arabinose-inducible bacterial plasmid encoding 6xHis-TEV-tdTomato",
    ),
    69929: PlasmidSpec(
        69929,
        "pET His-MBP-TEV",
        "a T7 bacterial MBP-TEV N-terminal fusion vector with kanamycin selection",
    ),
    112867: PlasmidSpec(
        112867,
        "pAdDeltaF6",
        "a large AAV helper plasmid rather than an expression-vector backbone",
    ),
    181752: PlasmidSpec(
        181752,
        "pCMV-MMLVgag-3xNES-Cas9",
        "a CMV-driven MMLV-Gag-3xNES-Cas9 virus-like-particle cargo plasmid",
    ),
}

TASKS = (
    TaskSpec(
        slug="lenti-mcherry",
        title="Lentiviral mCherry reporter",
        destination_id=19319,
        delete_start=537,
        delete_end=1254,
        source_id=27705,
        source_start=1228,
        source_end=1936,
        inventory_ids=(19319, 27705, 13031, 1864, 12259, 12456),
        goal=(
            "I want to make a third-generation lentiviral transfer plasmid "
            "expressing mCherry while retaining independent puromycin selection"
        ),
        exact_architecture=(
            (
                "Replace the EGFP coding sequence in pLJM1-EGFP with the mCherry "
                "coding sequence from pmCherry-N1, omitting mCherry's terminal "
                "stop codon so the existing downstream fusion frame and stop "
                "context are retained"
            ),
            (
                "Preserve the CMV expression context, lentiviral LTR, Psi, RRE, "
                "and cPPT/CTS elements, the hPGK-puromycin cassette, and the "
                "bacterial propagation elements"
            ),
        ),
        functional_requirements=(
            "constitutive mammalian expression of a red fluorescent protein",
            "the cis elements required of a third-generation lentiviral transfer vector",
            "independent puromycin selection in mammalian cells",
            "a fusion-ready downstream reading frame and terminal stop context",
            "no remaining EGFP coding sequence",
        ),
        preservation_rule=(
            "Make the smallest coding-region substitution that satisfies these "
            "requirements and preserve the selected transfer-vector backbone "
            "outside its original fluorescent-protein coding region"
        ),
        inserted_label="mCherry without terminal stop",
        truncated_cds_label="mCherry",
    ),
    TaskSpec(
        slug="topflash-egfp",
        title="TCF/LEF-responsive EGFP reporter",
        destination_id=12456,
        delete_start=380,
        delete_end=2048,
        source_id=13031,
        source_start=742,
        source_end=1462,
        inventory_ids=(12456, 13031, 27705, 19319, 13770, 42230),
        goal=(
            "I want to convert a beta-catenin/TCF-responsive luciferase reporter "
            "into a beta-catenin/TCF-responsive EGFP reporter"
        ),
        exact_architecture=(
            (
                "Replace the complete firefly-luciferase coding sequence with the "
                "complete EGFP coding "
                "sequence from pcDNA3-EGFP, including EGFP's terminal stop codon"
            ),
            (
                "Retain the original sequence immediately upstream of luciferase, "
                "including its Kozak context, as well as the TCF/LEF response "
                "elements, minimal promoter, SV40 poly(A) signal, and bacterial "
                "propagation elements"
            ),
        ),
        functional_requirements=(
            "green fluorescence controlled by the existing TCF/LEF-responsive minimal promoter",
            "an intact translation-initiation context and reporter stop codon",
            "a mammalian polyadenylation signal",
            "bacterial replication and antibiotic selection",
            "no remaining firefly-luciferase coding sequence",
        ),
        preservation_rule=(
            "Preserve the selected response-vector backbone outside its original "
            "reporter coding region, including the native translation-initiation "
            "context"
        ),
        inserted_label="native Kozak context plus complete EGFP CDS",
        restored_destination_prefix=(380, 395),
        manual_destination_features=(
            (154, 265, "protein_bind", "TCF/LEF response-site array"),
        ),
    ),
    TaskSpec(
        slug="cre-mcherry",
        title="Cre-dependent mCherry reporter",
        destination_id=13770,
        delete_start=3061,
        delete_end=3781,
        source_id=27705,
        source_start=1228,
        source_end=1939,
        inventory_ids=(13770, 27705, 13031, 12456, 19319, 21915),
        goal="I want to make a Cre-activated red fluorescent reporter plasmid",
        exact_architecture=(
            (
                "Replace the complete EGFP coding sequence with the complete "
                "mCherry coding sequence from "
                "pmCherry-N1, including mCherry's native stop codon"
            ),
            (
                "Preserve the CAG expression context, both loxP sites and the "
                "intervening transcriptional-stop/selection cassette, the "
                "beta-globin poly(A) signal, and bacterial propagation elements"
            ),
        ),
        functional_requirements=(
            "red fluorescence only after Cre-dependent activation",
            "the existing loxP-flanked transcriptional stop and selection architecture",
            "an intact red-fluorescent-protein start and stop codon",
            "mammalian transcription termination and polyadenylation",
            "no remaining EGFP coding sequence",
        ),
        preservation_rule=(
            "Change only the reporter coding region of the selected conditional "
            "expression backbone and preserve all of its recombinase-control "
            "architecture"
        ),
        inserted_label="complete mCherry CDS",
    ),
    TaskSpec(
        slug="lenti-egfp-neor",
        title="Lentiviral EGFP with G418 selection",
        destination_id=19319,
        delete_start=2022,
        delete_end=2622,
        source_id=13031,
        source_start=2629,
        source_end=3424,
        inventory_ids=(19319, 13031, 27705, 13770, 1864, 52961),
        goal=(
            "I want a third-generation lentiviral EGFP transfer plasmid that uses "
            "G418/neomycin selection rather than puromycin selection"
        ),
        exact_architecture=(
            (
                "Replace the complete PuroR coding sequence with the complete "
                "NeoR/KanR coding sequence from "
                "pcDNA3-EGFP, including the replacement gene's start and stop codons"
            ),
            (
                "Preserve the existing hPGK promoter driving the selectable "
                "marker, the CMV-EGFP cassette, all lentiviral cis elements, and "
                "the bacterial propagation elements"
            ),
        ),
        functional_requirements=(
            "constitutive EGFP expression in mammalian cells",
            "the cis elements required of a third-generation lentiviral transfer vector",
            "independent G418/neomycin selection from the existing marker promoter",
            "bacterial replication and antibiotic selection",
            "no remaining puromycin-resistance coding sequence",
        ),
        preservation_rule=(
            "Replace only the mammalian selectable-marker coding region in the "
            "selected EGFP transfer vector and retain the rest of that backbone"
        ),
        inserted_label="complete NeoR/KanR CDS",
    ),
    TaskSpec(
        slug="cas9-p2a-puro",
        title="Cas9-P2A-puromycin plasmid",
        destination_id=48138,
        delete_start=889,
        delete_end=1657,
        source_id=52961,
        source_start=8677,
        source_end=9331,
        inventory_ids=(48138, 52961, 42230, 19319, 21915, 13031),
        goal=(
            "I want a plasmid that expresses Cas9 and puromycin resistance as "
            "separate proteins from one mammalian transcript and also retains a "
            "U6 guide-RNA cassette"
        ),
        exact_architecture=(
            (
                "Replace the T2A-EGFP segment with the complete P2A-PuroR segment from "
                "lentiCRISPR v2"
            ),
            (
                "Preserve the reading frame from Cas9 through the ribosome-skipping "
                "peptide, the upstream Cas9 tags and localization signals, the U6 "
                "guide-RNA cassette, the downstream bGH poly(A) signal, and the "
                "bacterial propagation elements"
            ),
        ),
        functional_requirements=(
            "Cas9 and puromycin resistance as separate proteins from one open reading frame",
            "a functional ribosome-skipping peptide between those proteins",
            "the existing U6 guide-RNA expression cassette",
            "correct reading frame and a terminal stop codon after the selectable marker",
            "no fluorescent-protein coding sequence",
        ),
        preservation_rule=(
            "Use an inventory-encoded peptide-marker segment and change only the "
            "linked reporter segment of the selected Cas9 backbone"
        ),
        inserted_label="P2A-PuroR segment",
    ),
    TaskSpec(
        slug="t7-tdtomato-his",
        title="T7 tdTomato-6xHis expression plasmid",
        destination_id=37237,
        delete_start=4179,
        delete_end=5280,
        source_id=54856,
        source_start=1888,
        source_end=3316,
        inventory_ids=(37237, 54856, 69929, 40315, 12456, 27705),
        goal=(
            "I want a T7-driven bacterial expression plasmid producing tdTomato "
            "with the existing C-terminal 6xHis affinity tag"
        ),
        exact_architecture=(
            (
                "Replace the MBP coding sequence with tdTomato from pBAD "
                "6xHis-TEV-tdTomato, "
                "omitting tdTomato's terminal stop codon"
            ),
            (
                "Preserve the existing short linker, downstream in-frame 6xHis "
                "tag and stop codon, T7 promoter and ribosome-binding site, T7 "
                "terminator, and bacterial propagation elements"
            ),
        ),
        functional_requirements=(
            "T7-driven expression of a red fluorescent protein in bacteria",
            "the existing in-frame C-terminal 6xHis affinity tag",
            "a terminal stop codon after the affinity tag",
            "the existing bacterial transcription terminator and propagation elements",
            "no remaining MBP coding sequence",
        ),
        preservation_rule=(
            "Change only the original protein-coding region upstream of the "
            "C-terminal affinity tag and retain the selected T7-expression backbone"
        ),
        inserted_label="tdTomato without terminal stop",
        truncated_cds_label="tdTomato",
    ),
)

FEATURE_TYPES = {
    "CDS",
    "enhancer",
    "LTR",
    "misc_feature",
    "polyA_signal",
    "promoter",
    "protein_bind",
    "regulatory",
    "rep_origin",
    "terminator",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing addgene-plasmid-<id>-sequence-*.gbk files.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser.parse_args()


def _input_path(input_dir: Path, addgene_id: int) -> Path:
    paths = sorted(input_dir.glob(f"addgene-plasmid-{addgene_id}-sequence-*.gbk"))
    if len(paths) != 1:
        raise ValueError(
            f"Expected exactly one GenBank file for Addgene #{addgene_id}, "
            f"found {len(paths)}"
        )
    return paths[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _task_id(slug: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"labbench2:{VERSION}:{slug}"))


def _reverse_complement(sequence: str) -> str:
    return str(Seq(sequence).reverse_complement())


def _insert_sequence(
    task: TaskSpec, destination: SeqRecord, source: SeqRecord
) -> tuple[str, str, str]:
    source_sequence = str(source.seq)
    destination_sequence = str(destination.seq)
    core = source_sequence[task.source_start : task.source_end].upper()
    prefix = ""
    if task.restored_destination_prefix is not None:
        start, end = task.restored_destination_prefix
        prefix = destination_sequence[start:end].upper()
    return prefix + core, prefix, core


def _primers(retained: str, prefix: str, core: str) -> dict[str, str]:
    return {
        "backbone_forward": retained[:ANNEAL_LENGTH],
        "backbone_reverse": _reverse_complement(retained[-ANNEAL_LENGTH:]),
        "insert_forward": (retained[-OVERLAP_LENGTH:] + prefix + core[:ANNEAL_LENGTH]),
        "insert_reverse": (
            _reverse_complement(retained[:OVERLAP_LENGTH])
            + _reverse_complement(core[-ANNEAL_LENGTH:])
        ),
    }


def _canonical_protocol(task: TaskSpec, primers: dict[str, str]) -> str:
    destination = PLASMIDS[task.destination_id].filename
    source = PLASMIDS[task.source_id].filename
    expression = (
        "gibson(\n"
        f'  pcr({destination}, "{primers["backbone_forward"]}", '
        f'"{primers["backbone_reverse"]}"),\n'
        f'  pcr({source}, "{primers["insert_forward"]}", '
        f'"{primers["insert_reverse"]}")\n'
        ")"
    )
    return f"<protocol>\n{expression}\n</protocol>"


def _circular_match(first: str, second: str) -> bool:
    first = first.upper()
    second = second.upper()
    if len(first) != len(second):
        return False
    doubled = second + second
    return first in doubled or _reverse_complement(first) in doubled


def _circular_occurrences(sequence: str, query: str) -> list[int]:
    if not query or len(query) > len(sequence):
        return []
    haystack = sequence + sequence[: len(query) - 1]
    starts: list[int] = []
    cursor = 0
    while True:
        position = haystack.find(query, cursor)
        if position < 0:
            return starts
        if position < len(sequence):
            starts.append(position)
        cursor = position + 1


def _mapped_location(
    start: int, length: int, sequence_length: int, strand: int
) -> SimpleLocation | CompoundLocation:
    end = start + length
    if end <= sequence_length:
        return SimpleLocation(start, end, strand=strand)
    return CompoundLocation(
        [
            SimpleLocation(start, sequence_length, strand=strand),
            SimpleLocation(0, end - sequence_length, strand=strand),
        ],
        operator="join",
    )


def _feature_label(feature: SeqFeature) -> str:
    for key in ("label", "gene", "product"):
        if values := feature.qualifiers.get(key):
            return str(values[0])
    return ""


def _direct_transfer_destination_features(
    task: TaskSpec,
    insert_length: int,
    destination: SeqRecord,
    provenance: str,
    seen: set[tuple[str, str, int, int]],
) -> list[SeqFeature]:
    """Map retained destination features without losing repeated annotations."""
    destination_length = len(str(destination.seq))
    retained_after_delete = destination_length - task.delete_end
    transferred: list[SeqFeature] = []
    for feature in destination.features:
        if feature.type not in FEATURE_TYPES:
            continue
        mapped_parts: list[SimpleLocation] = []
        for part in feature.location.parts:
            start = int(part.start)
            end = int(part.end)
            if end <= task.delete_start:
                mapped_start = insert_length + retained_after_delete + start
            elif start >= task.delete_end:
                mapped_start = insert_length + start - task.delete_end
            else:
                mapped_parts = []
                break
            mapped_parts.append(
                SimpleLocation(
                    mapped_start,
                    mapped_start + end - start,
                    strand=part.strand,
                )
            )
        if not mapped_parts:
            continue
        location: SimpleLocation | CompoundLocation
        if len(mapped_parts) == 1:
            location = mapped_parts[0]
        else:
            location = CompoundLocation(
                mapped_parts,
                operator=getattr(feature.location, "operator", "join"),
            )
        label = _feature_label(feature)
        key = (feature.type, label, int(location.start), len(location))
        if key in seen:
            continue
        seen.add(key)
        copied = copy.deepcopy(feature)
        copied.location = location
        copied.qualifiers = copy.deepcopy(feature.qualifiers)
        copied.qualifiers.setdefault("note", []).append(
            f"Sequence provenance: {provenance}"
        )
        transferred.append(copied)
    return transferred


def _transfer_features(
    reference_sequence: str,
    record: SeqRecord,
    provenance: str,
    seen: set[tuple[str, str, int, int]],
) -> list[SeqFeature]:
    transferred: list[SeqFeature] = []
    for feature in record.features:
        if feature.type not in FEATURE_TYPES:
            continue
        extracted = str(feature.extract(record.seq)).upper()
        if len(extracted) < MIN_FEATURE_LENGTH or len(extracted) > len(
            reference_sequence
        ):
            continue
        reverse = _reverse_complement(extracted)
        forward_starts = _circular_occurrences(reference_sequence, extracted)
        reverse_starts = (
            _circular_occurrences(reference_sequence, reverse)
            if reverse != extracted
            else []
        )
        locations = [(start, 1) for start in forward_starts] + [
            (start, -1) for start in reverse_starts
        ]
        if len(locations) != 1:
            continue
        start, strand = locations[0]
        label = _feature_label(feature)
        key = (feature.type, label, start, len(extracted))
        if key in seen:
            continue
        seen.add(key)
        copied = copy.deepcopy(feature)
        copied.location = _mapped_location(
            start, len(extracted), len(reference_sequence), strand
        )
        copied.qualifiers = copy.deepcopy(feature.qualifiers)
        copied.qualifiers.setdefault("note", []).append(
            f"Sequence provenance: {provenance}"
        )
        transferred.append(copied)
    return transferred


def _reference_record(
    task: TaskSpec,
    destination: SeqRecord,
    source: SeqRecord,
    insert: str,
    prefix_length: int,
    retained: str,
    task_id: str,
) -> SeqRecord:
    sequence = insert + retained
    record = SeqRecord(
        Seq(sequence),
        id=task_id,
        name=task.slug[:16],
        description=f"{task.title}; circular reference assembly",
        annotations={"molecule_type": "DNA", "topology": "circular"},
    )
    record.features = [
        SeqFeature(SimpleLocation(0, len(sequence)), type="source"),
        SeqFeature(
            SimpleLocation(0, len(insert)),
            type="misc_feature",
            qualifiers={
                "label": [task.inserted_label],
                "note": [
                    f"Insert core provenance: Addgene #{task.source_id}; "
                    f"source interval [{task.source_start}:{task.source_end})"
                ],
            },
        ),
        SeqFeature(
            SimpleLocation(len(insert), len(sequence)),
            type="misc_feature",
            qualifiers={
                "label": [f"retained {PLASMIDS[task.destination_id].name} backbone"],
                "note": [
                    f"Backbone provenance: Addgene #{task.destination_id}; "
                    f"destination interval [{task.delete_start}:{task.delete_end}) "
                    "replaced"
                ],
            },
        ),
    ]
    if task.truncated_cds_label is not None:
        record.features.append(
            SeqFeature(
                SimpleLocation(prefix_length, len(insert)),
                type="CDS",
                qualifiers={
                    "label": [task.truncated_cds_label],
                    "note": [
                        "Terminal stop codon intentionally omitted to retain the "
                        "destination's downstream in-frame fusion context"
                    ],
                },
            )
        )
    destination_length = len(str(destination.seq))
    for start, end, feature_type, label in task.manual_destination_features:
        if end <= task.delete_start:
            mapped_start = len(insert) + destination_length - task.delete_end + start
        elif start >= task.delete_end:
            mapped_start = len(insert) + start - task.delete_end
        else:
            raise ValueError(
                f"Manual feature {label!r} overlaps the deleted interval for "
                f"{task.slug}"
            )
        record.features.append(
            SeqFeature(
                SimpleLocation(mapped_start, mapped_start + end - start),
                type=feature_type,
                qualifiers={
                    "label": [label],
                    "note": [
                        f"Manually identified retained feature from Addgene "
                        f"#{task.destination_id}; original interval [{start}:{end})"
                    ],
                },
            )
        )
    seen: set[tuple[str, str, int, int]] = set()
    record.features.extend(
        _direct_transfer_destination_features(
            task,
            len(insert),
            destination,
            f"{PLASMIDS[task.destination_id].name} "
            f"(Addgene #{task.destination_id}; retained backbone)",
            seen,
        )
    )
    record.features.extend(
        _transfer_features(
            sequence,
            destination,
            f"{PLASMIDS[task.destination_id].name} "
            f"(Addgene #{task.destination_id}; restored or retained context)",
            seen,
        )
    )
    record.features.extend(
        _transfer_features(
            sequence,
            source,
            f"{PLASMIDS[task.source_id].name} "
            f"(Addgene #{task.source_id}; insert source)",
            seen,
        )
    )
    return record


def _question_spec(task: TaskSpec) -> CloningQuestionSpec:
    destination = PLASMIDS[task.destination_id]
    inventory = tuple(
        InventoryItem(
            name=PLASMIDS[addgene_id].name,
            accession=f"Addgene #{addgene_id}",
            filename=PLASMIDS[addgene_id].filename,
            description=PLASMIDS[addgene_id].description,
        )
        for addgene_id in task.inventory_ids
    )
    return CloningQuestionSpec(
        goal=task.goal,
        named_backbone_instruction=(
            f"Use {destination.name} (Addgene #{destination.addgene_id}) as the backbone"
        ),
        exact_architecture=task.exact_architecture,
        inventory=inventory,
        functional_requirements=task.functional_requirements,
        preservation_rule=task.preservation_rule,
        assembly_method="Gibson",
    )


def _question_record(
    task: TaskSpec, task_id: str, dials: DifficultyDials
) -> dict[str, Any]:
    return {
        "id": task_id,
        "tag": "cloning",
        "version": VERSION,
        "type": "gibson",
        "question": render_cloning_question(_question_spec(task), dials),
        "ideal": "",
        "files": f"cloning/{task_id}",
        "sources": [
            f"https://www.addgene.org/{addgene_id}/"
            for addgene_id in task.inventory_ids
        ],
        "prompt_suffix": CLONING_PROTOCOL_SUFFIX,
        "validator_params": "{}",
        "answer_regex": "",
        "mode": {"inject": True, "file": True, "retrieve": True},
        "difficulty": dials.metadata(),
    }


def _write_fasta(record: SeqRecord, path: Path) -> None:
    sequence = str(record.seq).upper()
    lines = [
        f">{record.id}: {record.description} (circular)",
        *(sequence[index : index + 80] for index in range(0, len(sequence), 80)),
    ]
    path.write_text("\n".join(lines) + "\n")


def _write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )


async def generate(input_dir: Path, output: Path) -> None:
    input_paths = {
        addgene_id: _input_path(input_dir, addgene_id) for addgene_id in PLASMIDS
    }
    records = {
        addgene_id: SeqIO.read(path, "genbank")
        for addgene_id, path in input_paths.items()
    }
    for addgene_id, record in records.items():
        if record.annotations.get("topology") != "circular":
            raise ValueError(f"Addgene #{addgene_id} is not annotated as circular")

    output.mkdir(parents=True, exist_ok=True)
    (output / "cloning").mkdir(exist_ok=True)
    (output / "validation").mkdir(exist_ok=True)
    (output / "canonical_protocols").mkdir(exist_ok=True)

    question_sets: dict[str, list[dict[str, Any]]] = {
        profile.name: [] for profile in DIFFICULTY_PROFILES
    }
    task_manifest: list[dict[str, Any]] = []
    for task in TASKS:
        task_id = _task_id(task.slug)
        task_dir = output / "cloning" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        for addgene_id in task.inventory_ids:
            shutil.copy2(
                input_paths[addgene_id], task_dir / PLASMIDS[addgene_id].filename
            )

        destination = records[task.destination_id]
        source = records[task.source_id]
        destination_sequence = str(destination.seq).upper()
        retained = (
            destination_sequence[task.delete_end :]
            + destination_sequence[: task.delete_start]
        )
        insert, prefix, core = _insert_sequence(task, destination, source)
        primers = _primers(retained, prefix, core)
        protocol = _canonical_protocol(task, primers)
        reference = _reference_record(
            task, destination, source, insert, len(prefix), retained, task_id
        )

        fasta_path = output / "validation" / f"{task_id}_assembled.fa"
        genbank_path = output / "validation" / f"{task_id}_assembled.gbk"
        protocol_path = output / "canonical_protocols" / f"{task_id}.txt"
        _write_fasta(reference, fasta_path)
        SeqIO.write([reference], genbank_path, "genbank")
        protocol_path.write_text(protocol + "\n")

        products = await execute_cloning_protocol_v2(
            protocol.split("<protocol>", 1)[1].split("</protocol>", 1)[0], task_dir
        )
        exact_products = [
            index
            for index, product in enumerate(products)
            if product.is_circular
            and _circular_match(str(product.sequence), str(reference.seq))
        ]
        if exact_products != [0]:
            raise ValueError(
                f"{task.slug}: expected one exact canonical product; got "
                f"{len(products)} products and exact matches {exact_products}"
            )

        for profile in DIFFICULTY_PROFILES:
            question_sets[profile.name].append(_question_record(task, task_id, profile))
        task_manifest.append(
            {
                "id": task_id,
                "slug": task.slug,
                "title": task.title,
                "destination_addgene_id": task.destination_id,
                "deleted_interval_zero_based_half_open": [
                    task.delete_start,
                    task.delete_end,
                ],
                "source_addgene_id": task.source_id,
                "source_interval_zero_based_half_open": [
                    task.source_start,
                    task.source_end,
                ],
                "restored_destination_prefix": (
                    list(task.restored_destination_prefix)
                    if task.restored_destination_prefix is not None
                    else None
                ),
                "inventory_addgene_ids": list(task.inventory_ids),
                "insert_length_bp": len(insert),
                "reference_length_bp": len(str(reference.seq)),
                "reference_is_circular": True,
                "canonical_method": "Gibson",
                "canonical_product_count": len(products),
                "canonical_exact_circular_match": True,
                "primers_5_to_3": primers,
            }
        )

    question_paths = {
        BASELINE.name: output / "questions.jsonl",
        METHOD_BLIND.name: output / "questions_method_blind.jsonl",
        INVENTORY_FUNCTIONAL.name: output / "questions_inventory_functional.jsonl",
    }
    for profile_name, path in question_paths.items():
        _write_jsonl(question_sets[profile_name], path)

    manifest = {
        "version": VERSION,
        "generator": "tools/generate_cloning_inventory_questions.py",
        "question_sets": {
            profile.name: {
                "path": question_paths[profile.name].name,
                "dials": profile.metadata(),
            }
            for profile in DIFFICULTY_PROFILES
        },
        "inventory": [
            {
                "addgene_id": addgene_id,
                "name": PLASMIDS[addgene_id].name,
                "description": PLASMIDS[addgene_id].description,
                "input_filename": input_paths[addgene_id].name,
                "sha256": _sha256(input_paths[addgene_id]),
                "length_bp": len(records[addgene_id].seq),
                "topology": records[addgene_id].annotations.get("topology"),
                "used_in_generated_tasks": any(
                    addgene_id in task.inventory_ids for task in TASKS
                ),
            }
            for addgene_id in sorted(PLASMIDS)
        ],
        "tasks": task_manifest,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    args = parse_args()
    asyncio.run(generate(args.input_dir, args.output))


if __name__ == "__main__":
    main()
