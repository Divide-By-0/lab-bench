#!/usr/bin/env python3
"""Generate multi-fragment, inventory-first CloningQA questions."""

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

from lab_bench_2.cloning_simulators import execute_cloning_protocol_v2
from lab_bench_2.prompt_composer import CLONING_PROTOCOL_SUFFIX

VERSION = "inventory-hard-1.0"
OUTPUT_DEFAULT = Path("experiments/cloning_inventory_hard_v1")
OVERLAP_LENGTH = 24
ANNEAL_LENGTH = 24
MIN_FEATURE_LENGTH = 10

ADDGENE_NAMES = {
    1864: "pLKO.1 scrambled shRNA",
    8449: "pUMVC",
    10878: "pLKO.1",
    12253: "pRSV-Rev",
    12259: "pMD2.G",
    12260: "psPAX2",
    12456: "M50 Super 8x TOPFlash",
    13031: "pcDNA3-EGFP",
    13770: "pCALNL-GFP",
    19319: "pLJM1-EGFP",
    21915: "Tet-pLKO-puro",
    27705: "pmCherry-N1",
    37237: "pET MBP-6xHis",
    40315: "pET OmpA-6xHis",
    42230: "pX330",
    48138: "pSpCas9(BB)-2A-GFP (PX458)",
    52961: "lentiCRISPR v2",
    54856: "pBAD 6xHis-TEV-tdTomato",
    69929: "pET His-MBP-TEV",
    112867: "pAdDeltaF6",
    181752: "pCMV-MMLVgag-3xNES-Cas9",
}

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


@dataclass(frozen=True)
class Segment:
    """A directed interval copied from one circular inventory plasmid."""

    source_id: int
    start: int
    end: int
    strand: int = 1


@dataclass(frozen=True)
class Component:
    """One PCR-derived assembly component and optional primer-added prefix."""

    label: str
    template: Segment
    role: str
    prefix: Segment | None = None


@dataclass(frozen=True)
class ManualFeature:
    source: Segment
    feature_type: str
    label: str


@dataclass(frozen=True)
class HardTask:
    slug: str
    title: str
    goal: str
    requirements: tuple[str, ...]
    components: tuple[Component, ...]
    inventory_ids: tuple[int, ...]
    manual_features: tuple[ManualFeature, ...] = ()


TASKS = (
    HardTask(
        slug="wnt-egfp-p2a-puro",
        title="TCF/LEF EGFP-P2A-PuroR reporter",
        goal=(
            "Build a beta-catenin/TCF-responsive mammalian reporter that produces "
            "EGFP and puromycin resistance as separate proteins from one transcript"
        ),
        requirements=(
            "retain an eight-site TCF/LEF response array, its minimal promoter, and its native translation-initiation context",
            "replace firefly luciferase with one continuous EGFP-P2A-PuroR open reading frame",
            "omit the EGFP stop codon, preserve the P2A reading frame, and place the only coding-region stop after PuroR",
            "retain the response vector's SV40 polyadenylation signal and bacterial propagation elements",
            "use sequence present in the inventory and no more than three PCR-derived assembly components",
        ),
        components=(
            Component(
                "native TOPFlash initiation context plus EGFP without stop",
                Segment(13031, 742, 1459),
                "reporter",
                prefix=Segment(12456, 380, 395),
            ),
            Component(
                "P2A-PuroR with terminal stop",
                Segment(52961, 8677, 9331),
                "linked selection cassette",
            ),
            Component(
                "retained TOPFlash backbone",
                Segment(12456, 2048, 380),
                "backbone",
            ),
        ),
        inventory_ids=(
            12456,
            13031,
            13770,
            19319,
            21915,
            27705,
            42230,
            48138,
            52961,
            54856,
            69929,
            1864,
        ),
        manual_features=(
            ManualFeature(
                Segment(12456, 154, 265),
                "protein_bind",
                "TCF/LEF response-site array",
            ),
        ),
    ),
    HardTask(
        slug="lenti-mcherry-neor-two-locus",
        title="Lentiviral mCherry with G418 selection",
        goal=(
            "Build a third-generation lentiviral transfer vector that expresses "
            "mCherry and uses independent G418/neomycin selection"
        ),
        requirements=(
            "start from an inventory transfer vector that already contains the required LTR, Psi, RRE, and cPPT/CTS elements",
            "replace its green reporter with mCherry while preserving the existing downstream fusion/stop context",
            "independently replace its hPGK-driven puromycin-resistance coding region with a complete NeoR/KanR coding region",
            "remove all EGFP and PuroR coding sequence while retaining the original promoters, lentiviral cis elements, and bacterial propagation elements",
            "make exactly the two local coding-region edits and use no more than four PCR-derived assembly components",
        ),
        components=(
            Component(
                "mCherry without terminal stop",
                Segment(27705, 1228, 1936),
                "reporter",
            ),
            Component(
                "retained reporter-to-marker interval",
                Segment(19319, 1254, 2022),
                "backbone",
            ),
            Component(
                "complete NeoR/KanR CDS",
                Segment(13031, 2629, 3424),
                "mammalian selection marker",
            ),
            Component(
                "retained lentiviral backbone",
                Segment(19319, 2622, 537),
                "backbone",
            ),
        ),
        inventory_ids=(
            1864,
            10878,
            12259,
            12260,
            12456,
            13031,
            13770,
            19319,
            21915,
            27705,
            48138,
            52961,
        ),
    ),
    HardTask(
        slug="cre-tdtomato-p2a-puro",
        title="Cre-dependent tdTomato-P2A-PuroR reporter",
        goal=(
            "Build a Cre-activated reporter that produces tdTomato and puromycin "
            "resistance as separate proteins from the activated transcript"
        ),
        requirements=(
            "retain both loxP sites and the complete intervening transcriptional-stop/selection architecture of an inventory conditional-expression backbone",
            "replace the original green reporter with a continuous tdTomato-P2A-PuroR open reading frame",
            "omit the tdTomato stop, preserve the P2A frame, and retain a single terminal stop after PuroR",
            "retain the CAG expression context, mammalian polyadenylation signal, and bacterial propagation elements, with no EGFP coding sequence remaining",
            "use sequence present in the inventory and no more than three PCR-derived assembly components",
        ),
        components=(
            Component(
                "tdTomato without terminal stop",
                Segment(54856, 1888, 3316),
                "reporter",
            ),
            Component(
                "P2A-PuroR with terminal stop",
                Segment(52961, 8677, 9331),
                "linked selection cassette",
            ),
            Component(
                "retained Cre-dependent backbone",
                Segment(13770, 3781, 3061),
                "backbone",
            ),
        ),
        inventory_ids=(
            12456,
            13031,
            13770,
            19319,
            21915,
            27705,
            37237,
            42230,
            48138,
            52961,
            54856,
            69929,
        ),
    ),
    HardTask(
        slug="cas9-p2a-mcherry-kanr",
        title="Cas9-P2A-mCherry with kanamycin propagation",
        goal=(
            "Build a nonviral mammalian CRISPR plasmid that coexpresses Cas9 and "
            "mCherry as separate proteins and propagates under kanamycin selection"
        ),
        requirements=(
            "start from a CAG-Cas9 inventory backbone that initially has no linked fluorescent reporter or mammalian selectable marker",
            "retain its U6 guide-RNA cassette, 3xFLAG/SV40-NLS-Cas9-nucleoplasmin-NLS reading frame, and bGH polyadenylation signal",
            "append P2A followed by complete mCherry immediately after the terminal Cas9 NLS, with no stop before P2A and one stop after mCherry",
            "replace the bacterial AmpR coding region with a complete, correctly oriented KanR coding region while retaining the original bacterial promoter and origin",
            "use sequence present in the inventory and no more than five PCR-derived assembly components",
        ),
        components=(
            Component("P2A", Segment(52961, 8677, 8734), "linker"),
            Component(
                "complete mCherry CDS",
                Segment(27705, 1228, 1939),
                "reporter",
            ),
            Component(
                "retained Cas9-polyA-to-AmpR-promoter interval",
                Segment(42230, 5522, 6828),
                "backbone",
            ),
            Component(
                "complete KanR CDS in expression orientation",
                Segment(69929, 2821, 3637, strand=-1),
                "bacterial selection marker",
            ),
            Component(
                "retained origin-U6-CAG-Cas9 backbone",
                Segment(42230, 7689, 5522),
                "backbone",
            ),
        ),
        inventory_ids=(
            12456,
            13031,
            13770,
            19319,
            27705,
            37237,
            40315,
            42230,
            48138,
            52961,
            54856,
            69929,
        ),
    ),
    HardTask(
        slug="t7-histev-tdtomato-kanr",
        title="T7 6xHis-TEV-tdTomato with kanamycin propagation",
        goal=(
            "Build a T7 bacterial expression plasmid for N-terminally tagged, "
            "TEV-cleavable tdTomato that propagates under kanamycin selection"
        ),
        requirements=(
            "retain the T7 promoter, ribosome-binding context, T7 terminator, and origin of an inventory MBP expression backbone",
            "replace MBP and its original C-terminal affinity tag with an in-frame N-terminal 6xHis-tag/T7-tag/TEV-site/tdTomato segment and a terminal stop",
            "retain the original start codon immediately upstream of the replacement segment and remove all MBP coding sequence",
            "replace the bacterial AmpR coding region with a complete, correctly oriented KanR coding region while retaining the original resistance-gene promoter",
            "use sequence present in the inventory and no more than four PCR-derived assembly components",
        ),
        components=(
            Component(
                "complete KanR CDS in expression orientation",
                Segment(69929, 2821, 3637, strand=-1),
                "bacterial selection marker",
            ),
            Component(
                "retained origin-to-expression-start interval",
                Segment(37237, 1069, 4182),
                "backbone",
            ),
            Component(
                "6xHis-T7-tag-TEV-tdTomato with stop",
                Segment(54856, 1795, 3319),
                "protein coding region",
            ),
            Component(
                "retained terminator-to-AmpR-promoter interval",
                Segment(37237, 5307, 208),
                "backbone",
            ),
        ),
        inventory_ids=(
            12456,
            13031,
            19319,
            27705,
            37237,
            40315,
            42230,
            48138,
            52961,
            54856,
            69929,
            181752,
        ),
    ),
    HardTask(
        slug="lenti-guide-mcherry-p2a-neor",
        title="Guide-vector mCherry-P2A-NeoR replacement",
        goal=(
            "Build a compact third-generation lentiviral guide vector with "
            "mCherry expression and G418/neomycin selection"
        ),
        requirements=(
            "start from an inventory lentiviral CRISPR vector and retain its U6 guide-RNA cassette, EF-1-alpha expression context, LTRs, Psi, RRE, cPPT/CTS, and WPRE",
            "replace the complete Cas9-NLS-FLAG-P2A-PuroR coding region with one mCherry-P2A-NeoR open reading frame",
            "omit the mCherry stop codon, retain an in-frame P2A, and place the only coding-region stop after NeoR",
            "remove all Cas9 and PuroR coding sequence while retaining the downstream WPRE, polyadenylation signal, and bacterial propagation elements",
            "use sequence present in the inventory and no more than four PCR-derived assembly components",
        ),
        components=(
            Component(
                "mCherry without terminal stop",
                Segment(27705, 1228, 1936),
                "reporter",
            ),
            Component("P2A", Segment(52961, 8677, 8734), "linker"),
            Component(
                "complete NeoR/KanR CDS",
                Segment(13031, 2629, 3424),
                "mammalian selection marker",
            ),
            Component(
                "retained lentiviral guide-vector backbone",
                Segment(52961, 9331, 4492),
                "backbone",
            ),
        ),
        inventory_ids=(
            1864,
            10878,
            12253,
            12259,
            12260,
            12456,
            13031,
            13770,
            19319,
            21915,
            27705,
            52961,
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing addgene-plasmid-<id>-sequence-*.gbk files.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser.parse_args()


def _input_path(input_dir: Path, addgene_id: int) -> Path:
    paths = sorted(input_dir.glob(f"addgene-plasmid-{addgene_id}-sequence-*.gbk"))
    if len(paths) != 1:
        raise ValueError(
            f"Expected exactly one GenBank file for Addgene #{addgene_id}; "
            f"found {len(paths)}"
        )
    return paths[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reverse_complement(sequence: str) -> str:
    return str(Seq(sequence).reverse_complement())


def _segment_length(segment: Segment, record: SeqRecord) -> int:
    sequence_length = len(str(record.seq))
    length = (segment.end - segment.start) % sequence_length
    if length == 0:
        raise ValueError(f"A segment cannot span zero or one complete plasmid: {segment}")
    return length


def _segment_sequence(segment: Segment, record: SeqRecord) -> str:
    sequence = str(record.seq).upper()
    if segment.start < segment.end:
        result = sequence[segment.start : segment.end]
    else:
        result = sequence[segment.start :] + sequence[: segment.end]
    if segment.strand == -1:
        result = _reverse_complement(result)
    return result


def _component_parts(
    component: Component, records: dict[int, SeqRecord]
) -> tuple[str, str, str]:
    template = _segment_sequence(component.template, records[component.template.source_id])
    prefix = ""
    if component.prefix is not None:
        prefix = _segment_sequence(component.prefix, records[component.prefix.source_id])
    return prefix + template, prefix, template


def _canonical_protocol(
    task: HardTask,
    records: dict[int, SeqRecord],
) -> tuple[str, list[dict[str, str]]]:
    parts = [_component_parts(component, records) for component in task.components]
    final_sequences = [part[0] for part in parts]
    calls: list[str] = []
    primer_manifest: list[dict[str, str]] = []
    for index, (component, (_, prefix, template)) in enumerate(
        zip(task.components, parts, strict=True)
    ):
        forward = (
            final_sequences[index - 1][-OVERLAP_LENGTH:]
            + prefix
            + template[:ANNEAL_LENGTH]
        )
        reverse = _reverse_complement(template[-ANNEAL_LENGTH:])
        filename = f"addgene-{component.template.source_id}.gbk"
        calls.append(f'  pcr({filename}, "{forward}", "{reverse}")')
        primer_manifest.append(
            {
                "component": component.label,
                "template": filename,
                "forward_5_to_3": forward,
                "reverse_5_to_3": reverse,
            }
        )
    expression = "gibson(\n" + ",\n".join(calls) + "\n)"
    return f"<protocol>\n{expression}\n</protocol>", primer_manifest


def _circular_match(first: str, second: str) -> bool:
    first = first.upper()
    second = second.upper()
    if len(first) != len(second):
        return False
    doubled = second + second
    return first in doubled or _reverse_complement(first) in doubled


def _mapped_location(
    start: int, length: int, sequence_length: int, strand: int | None
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


def _map_features_from_segment(
    record: SeqRecord,
    segment: Segment,
    reference_offset: int,
    provenance: str,
    seen: set[tuple[str, str, int, int]],
) -> list[SeqFeature]:
    source_length = len(str(record.seq))
    segment_length = _segment_length(segment, record)
    transferred: list[SeqFeature] = []
    for feature in record.features:
        if feature.type not in FEATURE_TYPES:
            continue
        mapped_parts: list[SimpleLocation] = []
        for part in feature.location.parts:
            part_start = int(part.start)
            part_end = int(part.end)
            relative_start = (part_start - segment.start) % source_length
            relative_end = relative_start + part_end - part_start
            if relative_end > segment_length:
                mapped_parts = []
                break
            if segment.strand == 1:
                mapped_start = reference_offset + relative_start
                mapped_end = reference_offset + relative_end
                mapped_strand = part.strand
            else:
                mapped_start = reference_offset + segment_length - relative_end
                mapped_end = reference_offset + segment_length - relative_start
                mapped_strand = -part.strand if part.strand is not None else None
            mapped_parts.append(
                SimpleLocation(mapped_start, mapped_end, strand=mapped_strand)
            )
        if not mapped_parts:
            continue
        if segment.strand == -1:
            mapped_parts.reverse()
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


def _manual_feature(
    feature: ManualFeature,
    records: dict[int, SeqRecord],
    reference_sequence: str,
) -> SeqFeature:
    sequence = _segment_sequence(feature.source, records[feature.source.source_id])
    doubled = reference_sequence + reference_sequence[: len(sequence) - 1]
    starts: list[int] = []
    cursor = 0
    while True:
        start = doubled.find(sequence, cursor)
        if start < 0:
            break
        if start < len(reference_sequence):
            starts.append(start)
        cursor = start + 1
    if len(starts) != 1:
        raise ValueError(
            f"Manual feature {feature.label!r} has {len(starts)} reference matches"
        )
    return SeqFeature(
        _mapped_location(starts[0], len(sequence), len(reference_sequence), 1),
        type=feature.feature_type,
        qualifiers={
            "label": [feature.label],
            "note": [
                f"Manually identified sequence from Addgene "
                f"#{feature.source.source_id}"
            ],
        },
    )


def _reference_record(
    task: HardTask,
    task_id: str,
    records: dict[int, SeqRecord],
) -> tuple[SeqRecord, list[dict[str, Any]]]:
    components = [_component_parts(component, records) for component in task.components]
    reference_sequence = "".join(component[0] for component in components)
    record = SeqRecord(
        Seq(reference_sequence),
        id=task_id,
        name=task.slug[:16],
        description=f"{task.title}; circular multi-fragment reference assembly",
        annotations={"molecule_type": "DNA", "topology": "circular"},
    )
    record.features = [
        SeqFeature(SimpleLocation(0, len(reference_sequence)), type="source")
    ]
    seen: set[tuple[str, str, int, int]] = set()
    component_manifest: list[dict[str, Any]] = []
    offset = 0
    for component, (final_sequence, prefix, template) in zip(
        task.components, components, strict=True
    ):
        end = offset + len(final_sequence)
        sources = [component.template.source_id]
        if component.prefix is not None:
            sources.insert(0, component.prefix.source_id)
        record.features.append(
            SeqFeature(
                SimpleLocation(offset, end),
                type="misc_feature",
                qualifiers={
                    "label": [component.label],
                    "note": [
                        f"Assembly component role: {component.role}; sequence "
                        f"provenance Addgene #{', #'.join(map(str, sources))}"
                    ],
                },
            )
        )
        if component.prefix is not None:
            prefix_record = records[component.prefix.source_id]
            record.features.extend(
                _map_features_from_segment(
                    prefix_record,
                    component.prefix,
                    offset,
                    f"{ADDGENE_NAMES[component.prefix.source_id]} "
                    f"(Addgene #{component.prefix.source_id}; primer-added prefix)",
                    seen,
                )
            )
        template_record = records[component.template.source_id]
        record.features.extend(
            _map_features_from_segment(
                template_record,
                component.template,
                offset + len(prefix),
                f"{ADDGENE_NAMES[component.template.source_id]} "
                f"(Addgene #{component.template.source_id}; {component.role})",
                seen,
            )
        )
        component_manifest.append(
            {
                "label": component.label,
                "role": component.role,
                "reference_interval_zero_based_half_open": [offset, end],
                "template": {
                    "addgene_id": component.template.source_id,
                    "interval_zero_based_half_open": [
                        component.template.start,
                        component.template.end,
                    ],
                    "strand": component.template.strand,
                },
                "primer_added_prefix": (
                    {
                        "addgene_id": component.prefix.source_id,
                        "interval_zero_based_half_open": [
                            component.prefix.start,
                            component.prefix.end,
                        ],
                        "strand": component.prefix.strand,
                    }
                    if component.prefix is not None
                    else None
                ),
            }
        )
        offset = end
    record.features.extend(
        _manual_feature(feature, records, reference_sequence)
        for feature in task.manual_features
    )
    return record, component_manifest


def _question_text(task: HardTask) -> str:
    inventory = "\n".join(
        f"- `addgene-{addgene_id}.gbk`" for addgene_id in task.inventory_ids
    )
    requirements = "\n".join(
        f"- {requirement.rstrip('.')}." for requirement in task.requirements
    )
    return (
        f"{task.goal}. Select all starting molecules by inspecting the attached "
        "GenBank sequences and annotations; the inventory filenames deliberately "
        "provide only accession numbers.\n\n"
        f"Available inventory:\n{inventory}\n\n"
        f"Functional and construction constraints:\n{requirements}\n\n"
        "Do not synthesize a complete coding region in primer tails. Choose any "
        "supported assembly method, but preserve the selected backbone outside "
        "the required local edits. The final circular construct, including its "
        "junction sequences, reading frames, and retained architecture, will be "
        "assessed."
    )


def _question_record(task: HardTask, task_id: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "tag": "cloning",
        "version": VERSION,
        "type": "gibson",
        "question": _question_text(task),
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
        "difficulty": {
            "name": "hard_inventory_multifragment",
            "method": "model_chooses",
            "materials": "accession_only_inventory",
            "architecture": "functional_multifragment",
            "component_count": len(task.components),
        },
    }


def _write_fasta(record: SeqRecord, path: Path) -> None:
    sequence = str(record.seq).upper()
    lines = [
        f">{record.id}: {record.description} (circular)",
        *(sequence[index : index + 80] for index in range(0, len(sequence), 80)),
    ]
    path.write_text("\n".join(lines) + "\n")


def _write_readme(output: Path) -> None:
    rows = "\n".join(
        f"| {task.title} | {len(task.components)} | "
        f"{len(task.inventory_ids)} |"
        for task in TASKS
    )
    (output / "README.md").write_text(
        "# Hard Addgene cloning inventory pilot\n\n"
        "This package preserves the easier `cloning_inventory_pilot_v1` set and "
        "adds six genuinely harder underlying constructs. These are not merely "
        "prompt-redacted versions of two-fragment swaps.\n\n"
        "| Construct | Canonical components | Inventory files |\n"
        "| --- | ---: | ---: |\n"
        f"{rows}\n\n"
        "## What makes these harder\n\n"
        "- No assembly method, backbone, insert source, plasmid name, or exact "
        "coordinates are disclosed.\n"
        "- Each task supplies 12 accession-only GenBank files, including close "
        "architectural decoys.\n"
        "- The exact products require three to five PCR-derived components.\n"
        "- All six tasks require frame-sensitive coding or tag junctions; three require "
        "two coding changes, and two require reverse-orienting a bacterial marker.\n"
        "- The prompts impose retained-architecture and component-count constraints "
        "so whole-vector redesign is not an equivalent answer.\n\n"
        "The existing sequence verifier remains usable because every prompt still "
        "defines one smallest-change final construct. `validation/` contains exact "
        "circular FASTA references and annotated GenBank review references. Every "
        "base is covered by an assembly-component provenance annotation.\n\n"
        "## Regeneration\n\n"
        "```bash\n"
        "uv run --extra lab_bench_2 python "
        "tools/generate_cloning_inventory_hard_questions.py \\\n  --input-dir /path/to/addgene-genbank-files \\\n  --output experiments/cloning_inventory_hard_v1\n"
        "```\n\n"
        "## Running\n\n"
        "```bash\n"
        "inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \\\n  -T tags=cloning -T mode=file -T solver=agentic \\\n  -T dataset_path=\"$PWD/experiments/cloning_inventory_hard_v1/questions.jsonl\" \\\n  --model openai/gpt-5.6-sol --reasoning-effort max\n"
        "```\n"
    )


def _write_clean_readme(output: Path) -> None:
    rows = "\n".join(
        f"| {task.title} | {len(task.components)} | {len(task.inventory_ids)} |"
        for task in TASKS
    )
    lines = [
        "# Hard Addgene cloning inventory pilot",
        "",
        "This package preserves the easier `cloning_inventory_pilot_v1` set and "
        "adds six genuinely harder underlying constructs. These are not merely "
        "prompt-redacted versions of two-fragment swaps.",
        "",
        "| Construct | Canonical components | Inventory files |",
        "| --- | ---: | ---: |",
        rows,
        "",
        "## What makes these harder",
        "",
        "- No assembly method, backbone, insert source, plasmid name, or exact "
        "coordinates are disclosed.",
        "- Each task supplies 12 accession-only GenBank files, including close "
        "architectural decoys.",
        "- The exact products require three to five PCR-derived components.",
        "- All six tasks require frame-sensitive coding or tag junctions; three require "
        "two coding changes, and two require reverse-orienting a bacterial marker.",
        "- The prompts impose retained-architecture and component-count constraints "
        "so whole-vector redesign is not an equivalent answer.",
        "",
        "The existing sequence verifier remains usable because every prompt still "
        "defines one smallest-change final construct. `validation/` contains exact "
        "circular FASTA references and annotated GenBank review references. Every "
        "base is covered by an assembly-component provenance annotation.",
        "",
        "## Regeneration",
        "",
        "```bash",
        "uv run --extra lab_bench_2 python "
        "tools/generate_cloning_inventory_hard_questions.py \\",
        "  --input-dir /path/to/addgene-genbank-files \\",
        "  --output experiments/cloning_inventory_hard_v1",
        "```",
        "",
        "## Running",
        "",
        "```bash",
        "inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \\",
        "  -T tags=cloning -T mode=file -T solver=agentic \\",
        "  -T dataset_path=\"$PWD/experiments/cloning_inventory_hard_v1/questions.jsonl\" \\",
        "  --model openai/gpt-5.6-sol --reasoning-effort max",
        "```",
    ]
    (output / "README.md").write_text("\n".join(lines) + "\n")


async def generate(input_dir: Path, output: Path) -> None:
    used_ids = sorted({item for task in TASKS for item in task.inventory_ids})
    input_paths = {addgene_id: _input_path(input_dir, addgene_id) for addgene_id in used_ids}
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

    questions: list[dict[str, Any]] = []
    task_manifest: list[dict[str, Any]] = []
    for task in TASKS:
        task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"labbench2:{VERSION}:{task.slug}"))
        task_dir = output / "cloning" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        for addgene_id in task.inventory_ids:
            shutil.copy2(input_paths[addgene_id], task_dir / f"addgene-{addgene_id}.gbk")

        reference, components = _reference_record(task, task_id, records)
        protocol, primers = _canonical_protocol(task, records)
        fasta_path = output / "validation" / f"{task_id}_assembled.fa"
        genbank_path = output / "validation" / f"{task_id}_assembled.gbk"
        protocol_path = output / "canonical_protocols" / f"{task_id}.txt"
        _write_fasta(reference, fasta_path)
        SeqIO.write([reference], genbank_path, "genbank")
        protocol_path.write_text(protocol + "\n")

        expression = protocol.split("<protocol>", 1)[1].split("</protocol>", 1)[0]
        products = await execute_cloning_protocol_v2(expression, task_dir)
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

        questions.append(_question_record(task, task_id))
        task_manifest.append(
            {
                "id": task_id,
                "slug": task.slug,
                "title": task.title,
                "inventory_addgene_ids": list(task.inventory_ids),
                "reference_length_bp": len(str(reference.seq)),
                "reference_is_circular": True,
                "canonical_method": "Gibson",
                "canonical_component_count": len(task.components),
                "canonical_product_count": len(products),
                "canonical_exact_circular_match": True,
                "components": components,
                "primers_5_to_3": primers,
            }
        )

    (output / "questions.jsonl").write_text(
        "".join(json.dumps(question, sort_keys=True) + "\n" for question in questions)
    )
    manifest = {
        "version": VERSION,
        "generator": "tools/generate_cloning_inventory_hard_questions.py",
        "question_set": {
            "path": "questions.jsonl",
            "difficulty": "hard_inventory_multifragment",
        },
        "inventory": [
            {
                "addgene_id": addgene_id,
                "name": ADDGENE_NAMES[addgene_id],
                "input_filename": input_paths[addgene_id].name,
                "sha256": _sha256(input_paths[addgene_id]),
                "length_bp": len(records[addgene_id].seq),
                "topology": records[addgene_id].annotations.get("topology"),
            }
            for addgene_id in used_ids
        ],
        "tasks": task_manifest,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _write_clean_readme(output)


def main() -> None:
    args = parse_args()
    asyncio.run(generate(args.input_dir, args.output))


if __name__ == "__main__":
    main()
