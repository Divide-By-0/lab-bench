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

VERSION = "inventory-hard-1.1"
INTENT_CHALLENGE_VERSION = "inventory-intent-challenge-1.0"
TASK_ID_SEED_VERSION = "inventory-hard-1.0"
OUTPUT_DEFAULT = Path("experiments/cloning_inventory_hard_v1")
IGEM_ELEMENTS_DEFAULT = OUTPUT_DEFAULT / "igem_element_sources"
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
    request: str
    solution_summary: str
    components: tuple[Component, ...]
    inventory_ids: tuple[int, ...]
    manual_features: tuple[ManualFeature, ...] = ()


@dataclass(frozen=True)
class IntentChallenge:
    """A matched, intent-level prompt plus reviewer-only difficulty rationale."""

    slug: str
    tier: int
    request: str
    intent_inferences: tuple[str, ...]
    sequence_traps: tuple[str, ...]
    fairness_note: str


TASKS = (
    HardTask(
        slug="wnt-egfp-p2a-puro",
        title="TCF/LEF EGFP-P2A-PuroR reporter",
        request=(
            "Could you turn one of our TCF/LEF-responsive mammalian reporters into "
            "an EGFP reporter with puromycin selection? I want EGFP and PuroR made "
            "as separate proteins from the same reporter transcript, using P2A"
        ),
        solution_summary=(
            "Identify the TOPFlash reporter backbone, replace luciferase with "
            "EGFP-P2A-PuroR, and assemble three PCR products while keeping the "
            "coding junction in frame"
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
        request=(
            "Could you modify one of our third-generation lentiviral transfer "
            "vectors so it expresses mCherry instead of its current fluorescent "
            "reporter and uses G418 rather than puromycin for mammalian selection? "
            "Keep reporter expression and drug selection independent"
        ),
        solution_summary=(
            "Identify the pLJM1 transfer vector, replace EGFP with mCherry and "
            "replace the independently expressed PuroR CDS with NeoR; the canonical "
            "build uses four PCR products"
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
        request=(
            "Could you modify one of our Cre-dependent mammalian reporters so that, "
            "after Cre activation, it produces tdTomato and puromycin resistance as "
            "separate proteins from one transcript? Please use P2A between them"
        ),
        solution_summary=(
            "Identify the lox-stop-lox conditional reporter, preserve its Cre-control "
            "architecture, and replace GFP with tdTomato-P2A-PuroR using three PCR "
            "products"
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
        request=(
            "Could you modify one of our CAG-Cas9/sgRNA plasmids so it also makes "
            "mCherry as a separate protein using P2A? I also need the finished "
            "plasmid to use kanamycin, rather than ampicillin, for bacterial "
            "selection"
        ),
        solution_summary=(
            "Identify the pX330 CAG-Cas9/sgRNA backbone, append P2A-mCherry to the "
            "Cas9 reading frame, and replace AmpR with the correctly oriented KanR "
            "CDS; the canonical build uses five PCR products"
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
        request=(
            "Could you repurpose one of our T7 MBP expression plasmids to express "
            "tdTomato instead of MBP? The protein should carry the available "
            "N-terminal 6xHis/T7-tag/TEV leader, and the finished plasmid should use "
            "kanamycin rather than ampicillin for bacterial selection"
        ),
        solution_summary=(
            "Identify the T7 MBP destination, replace MBP with the donor's "
            "6xHis/T7-tag/TEV-tdTomato segment, and replace AmpR with correctly "
            "oriented KanR using four PCR products"
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
        request=(
            "Could you convert one of our lentiviral Cas9/guide vectors into a "
            "guide-only vector that expresses mCherry and NeoR as separate proteins "
            "using P2A? The finished vector should use G418 for mammalian selection "
            "and should no longer contain Cas9"
        ),
        solution_summary=(
            "Identify lentiCRISPR v2 and replace its Cas9-P2A-PuroR coding region "
            "with mCherry-P2A-NeoR while retaining the guide and lentiviral "
            "architecture; the canonical build uses four PCR products"
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


INTENT_CHALLENGES = (
    IntentChallenge(
        slug="wnt-egfp-p2a-puro",
        tier=2,
        request=(
            "We need a live-cell construct for enriching and tracking mammalian "
            "cells only while canonical Wnt/beta-catenin transcription is active. "
            "Use a fluorescence-only readout rather than a luminescent one. The "
            "pathway-responsive transcript should provide green fluorescence and "
            "puromycin resistance from one compact open reading frame, but those "
            "activities must come from separate proteins"
        ),
        intent_inferences=(
            "select a pathway-responsive rather than constitutive backbone",
            "infer a green reporter and puromycin-resistance coding sequence",
            "choose an inventory-supported way to make two proteins from one transcript",
        ),
        sequence_traps=(
            "retain the TCF/LEF response array and its minimal promoter",
            "remove the original luciferase coding sequence",
            "omit the reporter stop at the linked coding junction and keep one frame",
        ),
        fairness_note=(
            "Every scored requirement follows from pathway dependence, the two "
            "requested phenotypes, or the one-transcript/separate-protein constraint."
        ),
    ),
    IntentChallenge(
        slug="lenti-mcherry-neor-two-locus",
        tier=2,
        request=(
            "We need a third-generation lentiviral transfer construct for stable "
            "labeling of mammalian cells with a monomeric red fluorescent protein "
            "and enrichment with G418. Reporter intensity must remain interpretable "
            "independently of selection-marker expression, so each should have its "
            "own transcription unit. The vector should add no other fluorescent or "
            "mammalian drug-selection phenotype"
        ),
        intent_inferences=(
            "identify a lentiviral transfer rather than packaging plasmid",
            "map monomeric red fluorescence and G418 resistance to inventory parts",
            "preserve independent reporter and selector expression cassettes",
        ),
        sequence_traps=(
            "retain the packaging signal, RRE, and self-inactivating LTR architecture",
            "distinguish a mammalian G418 cassette from bacterial kanamycin selection",
            "remove the displaced reporter and mammalian selector coding sequences",
        ),
        fairness_note=(
            "The viral architecture is inherent to a functional third-generation "
            "transfer vector; separate transcription units are requested explicitly."
        ),
    ),
    IntentChallenge(
        slug="cre-tdtomato-p2a-puro",
        tier=3,
        request=(
            "Build a ubiquitous mammalian lineage-tracing construct that remains "
            "off until Cre removes a transcriptional stop. Once activated, it "
            "should produce only a bright red signal and puromycin resistance from "
            "one compact open reading frame while leaving the two products "
            "physically separate"
        ),
        intent_inferences=(
            "identify a Cre-dependent lox-stop-lox reporter backbone",
            "choose the brighter available red reporter and a puromycin marker",
            "infer an inventory-supported polycistronic architecture",
        ),
        sequence_traps=(
            "retain both loxP sites and the intervening stop cassette in the right order",
            "remove the original post-recombination reporter",
            "preserve an uninterrupted reporter-to-cleavage-peptide-to-selector frame",
        ),
        fairness_note=(
            "Cre dependence, brightness, selection, and separate products are all "
            "experimental requirements; no arbitrary enzyme or junction is prescribed."
        ),
    ),
    IntentChallenge(
        slug="cas9-p2a-mcherry-kanr",
        tier=3,
        request=(
            "We need a single transient mammalian plasmid that accepts an sgRNA and "
            "expresses its nuclease, with monomeric red fluorescence reporting "
            "nuclease expression from the same transcript without making a "
            "fluorescent fusion protein. It must propagate under kanamycin, and our "
            "facility does not permit beta-lactam-resistance plasmids"
        ),
        intent_inferences=(
            "infer the nuclease and guide-expression architecture from the sgRNA use case",
            "choose a monomeric red reporter and a cotranslational separation strategy",
            "select bacterial kanamycin resistance and eliminate beta-lactam resistance",
        ),
        sequence_traps=(
            "retain both the U6 guide cassette and the mammalian nuclease cassette",
            "remove the nuclease stop before the linked peptide while preserving its frame",
            "install the bacterial marker in expression orientation without retaining AmpR",
        ),
        fairness_note=(
            "The negative resistance constraint models a plausible facility rule; "
            "all other checks are required by guide editing or expression coupling."
        ),
    ),
    IntentChallenge(
        slug="t7-histev-tdtomato-kanr",
        tier=3,
        request=(
            "We need an IPTG-inducible E. coli construct for high-level production "
            "of a bright red fluorescent protein. The product should support "
            "immobilized-metal affinity purification and clean protease removal of "
            "its N-terminal affinity/expression leader, without a bulky solubility-"
            "fusion partner. Maintain the plasmid under kanamycin; beta-lactam-"
            "resistance DNA cannot be used in this project"
        ),
        intent_inferences=(
            "select a T7 bacterial expression backbone rather than a mammalian vector",
            "infer the fluorescent protein, affinity handle, and protease-cleavage site",
            "choose bacterial kanamycin resistance and remove beta-lactam resistance",
        ),
        sequence_traps=(
            "retain the T7 promoter, gene-10 translation context, and T7 terminator",
            "transfer only the useful donor coding interval rather than its arabinose system",
            "keep the complete leader and reporter in frame while excluding MBP",
        ),
        fairness_note=(
            "The host, induction system, purification workflow, and antibiotic "
            "policy are ordinary experimental constraints and uniquely narrow the inventory."
        ),
    ),
    IntentChallenge(
        slug="lenti-guide-mcherry-p2a-neor",
        tier=3,
        request=(
            "Our mammalian cells already express the genome-editing nuclease. Build "
            "a third-generation lentiviral construct that delivers only an sgRNA, "
            "marks transduced cells with a monomeric red signal, and permits G418 "
            "selection. The two phenotypes should come from one compact open reading "
            "frame but separate proteins. No nuclease or second mammalian drug-"
            "selection phenotype may remain in the payload"
        ),
        intent_inferences=(
            "identify a guide-capable lentiviral transfer backbone",
            "map monomeric red fluorescence and G418 selection to inventory parts",
            "infer a linked-but-separated expression architecture while deleting nuclease",
        ),
        sequence_traps=(
            "retain the U6 guide cassette plus lentiviral packaging and SIN-LTR elements",
            "remove both the nuclease and the displaced mammalian selector",
            "preserve one coding frame across reporter, cleavage peptide, and G418 marker",
        ),
        fairness_note=(
            "The absence of nuclease follows from the pre-engineered cell line and is "
            "stated; the remaining checks are necessary for guide delivery and selection."
        ),
    ),
)

INTENT_CHALLENGE_BY_SLUG = {
    challenge.slug: challenge for challenge in INTENT_CHALLENGES
}

REAGENT_TASK_SLUGS = (
    "wnt-egfp-p2a-puro",
    "lenti-mcherry-neor-two-locus",
    "cas9-p2a-mcherry-kanr",
)

ENZYME_REAGENTS = (
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

IGEM_PLATE_WELLS = (
    "1-A1",  # BBa_B0012 terminator
    "1-A2",  # HapR CDS
    "1-A3",  # eCFP CDS
    "1-A4",  # SrpR CDS
    "1-A5",  # BBa_J23100 promoter
    "1-A7",  # BCD1 RBS
    "1-A12",  # pJUMP29-1A(lacZ) backbone
    "1-A21",  # LacI-AM CDS
)

TASK_INVENTORY_SUFFIX = (
    "All available Addgene plasmids, iGEM carrier plasmids and element records, "
    "and stocked enzymes are in the attached task inventory. Do not synthesize "
    "genes de novo; obtain the gene sequences you need from that inventory."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing addgene-plasmid-<id>-sequence-*.gbk files.",
    )
    parser.add_argument(
        "--igem-dir",
        required=True,
        type=Path,
        help="Root of the 2026 iGEM kit snapshot containing manifest.json.",
    )
    parser.add_argument(
        "--igem-elements-dir",
        type=Path,
        default=IGEM_ELEMENTS_DEFAULT,
        help="Directory containing the selected element-level iGEM GenBank files.",
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


def _load_igem_parts(
    igem_dir: Path,
    igem_elements_dir: Path,
) -> list[dict[str, Any]]:
    manifest_path = igem_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    by_well = {record["plate_well"]: record for record in payload["records"]}
    parts: list[dict[str, Any]] = []
    for plate_well in IGEM_PLATE_WELLS:
        source = by_well[plate_well]
        if not source["is_valid"] or source["qc_status"] != "Correct":
            raise ValueError(
                f"Selected iGEM part {plate_well} is not QC-valid: "
                f"{source['qc_status']}"
            )
        source_path = igem_dir / source["genbank_file"]
        record = SeqIO.read(source_path, "genbank")
        if record.annotations.get("topology") != "circular":
            raise ValueError(f"Selected iGEM part {plate_well} is not circular")
        if len(str(record.seq)) != source["actual_sequence_length"]:
            raise ValueError(f"Selected iGEM part {plate_well} has a length mismatch")
        element_source_path = igem_elements_dir / f"{source['plasmid_id']}.gbk"
        element_record = SeqIO.read(element_source_path, "genbank")
        if not str(element_record.seq):
            raise ValueError(f"Selected iGEM element {plate_well} has no sequence")
        parts.append(
            {
                "plate_well": plate_well,
                "part_id": source["part_id"],
                "plasmid_id": source["plasmid_id"],
                "part_type": source["part_type"],
                "part_role": source["part_role"],
                "assembly_format": source["assembly_format"],
                "flanking_site": source["flanking_site"],
                "flanking_5": source["flanking_5"],
                "flanking_3": source["flanking_3"],
                "resistance": source["resistance"],
                "qc_status": source["qc_status"],
                "is_valid": source["is_valid"],
                "part_url": source["part_url"],
                "plasmid_length_bp": len(str(record.seq)),
                "plasmid_sha256": _sha256(source_path),
                "plasmid_filename": f"igem-plasmid-{source_path.stem}.gbk",
                "plasmid_source_path": source_path,
                "element_length_bp": len(str(element_record.seq)),
                "element_topology": element_record.annotations.get("topology"),
                "element_sha256": _sha256(element_source_path),
                "element_filename": f"igem-element-{source['plasmid_id']}.gbk",
                "element_source_path": element_source_path,
            }
        )
    return parts


def _copy_igem_inventory(parts: list[dict[str, Any]], task_dir: Path) -> None:
    columns = (
        "plasmid_filename",
        "element_filename",
        "plate_well",
        "part_id",
        "plasmid_id",
        "part_type",
        "part_role",
        "assembly_format",
        "flanking_site",
        "flanking_5",
        "flanking_3",
        "resistance",
        "qc_status",
        "plasmid_length_bp",
        "element_length_bp",
    )
    rows = ["\t".join(columns)]
    for stale_path in task_dir.glob("igem-*.gbk"):
        stale_path.unlink()
    for part in parts:
        shutil.copy2(
            part["plasmid_source_path"],
            task_dir / part["plasmid_filename"],
        )
        shutil.copy2(
            part["element_source_path"],
            task_dir / part["element_filename"],
        )
        rows.append("\t".join(str(part[column] or "") for column in columns))
    (task_dir / "igem_inventory.tsv").write_text("\n".join(rows) + "\n")


def _public_igem_part(part: dict[str, Any]) -> dict[str, Any]:
    private_keys = {"plasmid_source_path", "element_source_path"}
    return {key: value for key, value in part.items() if key not in private_keys}


def _reverse_complement(sequence: str) -> str:
    return str(Seq(sequence).reverse_complement())


def _segment_length(segment: Segment, record: SeqRecord) -> int:
    sequence_length = len(str(record.seq))
    length = (segment.end - segment.start) % sequence_length
    if length == 0:
        raise ValueError(
            f"A segment cannot span zero or one complete plasmid: {segment}"
        )
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
    template = _segment_sequence(
        component.template, records[component.template.source_id]
    )
    prefix = ""
    if component.prefix is not None:
        prefix = _segment_sequence(
            component.prefix, records[component.prefix.source_id]
        )
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
                f"Manually identified sequence from Addgene #{feature.source.source_id}"
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
    return f"{task.request.rstrip('.')}.\n\n{TASK_INVENTORY_SUFFIX}"


def _question_record(
    task: HardTask,
    task_id: str,
    igem_parts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": task_id,
        "tag": "cloning",
        "version": VERSION,
        "type": "gibson",
        "question": _question_text(task),
        "ideal": "",
        "files": f"cloning/{task_id}",
        "sources": [
            *(
                f"https://www.addgene.org/{addgene_id}/"
                for addgene_id in task.inventory_ids
            ),
            *(part["part_url"] for part in igem_parts),
        ],
        "prompt_suffix": CLONING_PROTOCOL_SUFFIX,
        "validator_params": "{}",
        "answer_regex": "",
        "mode": {"inject": True, "file": True, "retrieve": True},
        "difficulty": {
            "name": "hard_inventory_multifragment",
            "method": "model_chooses",
            "materials": "addgene_and_igem_inventory",
            "architecture": "functional_multifragment",
            "component_count": len(task.components),
            "igem_plasmid_count": len(igem_parts),
            "igem_element_count": len(igem_parts),
            "enzyme_count": len(ENZYME_REAGENTS),
        },
    }


def _intent_challenge_record(
    task: HardTask,
    task_id: str,
    igem_parts: list[dict[str, Any]],
) -> dict[str, Any]:
    challenge = INTENT_CHALLENGE_BY_SLUG[task.slug]
    record = _question_record(task, task_id, igem_parts)
    record["version"] = INTENT_CHALLENGE_VERSION
    record["question"] = f"{challenge.request.rstrip('.')}.\n\n{TASK_INVENTORY_SUFFIX}"
    record["difficulty"] = {
        "name": "intent_driven_sequence_traps",
        "tier": challenge.tier,
        "method": "model_chooses",
        "materials": "addgene_and_igem_inventory",
        "backbone": "model_chooses",
        "architecture": "model_infers_from_experimental_intent",
        "component_count": len(task.components),
        "intent_inference_count": len(challenge.intent_inferences),
        "sequence_trap_count": len(challenge.sequence_traps),
        "igem_plasmid_count": len(igem_parts),
        "igem_element_count": len(igem_parts),
        "enzyme_count": len(ENZYME_REAGENTS),
    }
    return record


def _intent_challenge_review(
    task: HardTask,
    task_id: str,
) -> dict[str, Any]:
    challenge = INTENT_CHALLENGE_BY_SLUG[task.slug]
    return {
        "id": task_id,
        "slug": task.slug,
        "reviewer_title": task.title,
        "tier": challenge.tier,
        "question_before_shared_inventory_suffix": challenge.request.rstrip(".") + ".",
        "intent_inferences": list(challenge.intent_inferences),
        "sequence_traps": list(challenge.sequence_traps),
        "canonical_solution": task.solution_summary.rstrip(".") + ".",
        "fairness_note": challenge.fairness_note,
        "reference_and_functional_spec_reused_from": "questions.jsonl",
    }


def _reagent_question_record(
    task: HardTask,
    task_id: str,
    primer_count: int,
    igem_parts: list[dict[str, Any]],
) -> dict[str, Any]:
    record = _question_record(task, task_id, igem_parts)
    record["files"] = f"reagent_inventory/{task_id}"
    record["question"] = (
        _question_text(task)
        + "\n\nThis version also has a fixed primer stock. Use only the stocked "
        "primers; some of them will not be relevant to this build."
    )
    record["difficulty"] = {
        "name": "hard_reagent_inventory",
        "method": "model_chooses",
        "materials": "accession_only_plasmid_and_reagent_inventory",
        "architecture": "functional_multifragment",
        "component_count": len(task.components),
        "primer_count": primer_count,
        "enzyme_count": len(ENZYME_REAGENTS),
        "igem_plasmid_count": len(igem_parts),
        "igem_element_count": len(igem_parts),
        "novel_primers_allowed": False,
    }
    return record


def _primer_sort_key(task: HardTask, sequence: str) -> str:
    return hashlib.sha256(
        f"{TASK_ID_SEED_VERSION}:{task.slug}:{sequence}".encode()
    ).hexdigest()


def _primer_template_id(primer: dict[str, str]) -> int:
    return int(primer["template"].removeprefix("addgene-").removesuffix(".gbk"))


def _reagent_protocol(
    task: HardTask,
    primer_manifest: list[dict[str, str]],
    primer_filenames: dict[str, str],
) -> str:
    calls = []
    for component, primers in zip(task.components, primer_manifest, strict=True):
        calls.append(
            f"  pcr(addgene-{component.template.source_id}.gbk, "
            f"{primer_filenames[primers['forward_5_to_3']]}, "
            f"{primer_filenames[primers['reverse_5_to_3']]})"
        )
    return "<protocol>\ngibson(\n" + ",\n".join(calls) + "\n)\n</protocol>"


def _write_enzyme_inventory(task_dir: Path) -> list[dict[str, str]]:
    for stale_path in task_dir.glob("enzyme-*.txt"):
        stale_path.unlink()
    enzyme_rows = []
    for index, enzyme in enumerate(ENZYME_REAGENTS, start=1):
        filename = f"enzyme-{index:02d}.txt"
        (task_dir / filename).write_text(enzyme + "\n")
        enzyme_rows.append({"filename": filename, "enzyme": enzyme})
    index_lines = ["filename\tenzyme"]
    index_lines.extend(f"{row['filename']}\t{row['enzyme']}" for row in enzyme_rows)
    (task_dir / "enzyme_inventory.tsv").write_text("\n".join(index_lines) + "\n")
    return enzyme_rows


def _write_reagent_inventory(
    task: HardTask,
    task_dir: Path,
    task_primers: list[dict[str, str]],
    all_task_primers: dict[str, list[dict[str, str]]],
) -> tuple[str, dict[str, Any]]:
    canonical_uses: dict[str, list[str]] = {}
    for primers in task_primers:
        canonical_uses.setdefault(primers["forward_5_to_3"], []).append(
            f"{primers['component']}:forward"
        )
        canonical_uses.setdefault(primers["reverse_5_to_3"], []).append(
            f"{primers['component']}:reverse"
        )

    decoy_candidates: set[str] = set()
    for slug, primer_set in all_task_primers.items():
        if slug == task.slug:
            continue
        for primers in primer_set:
            if _primer_template_id(primers) not in task.inventory_ids:
                continue
            decoy_candidates.update(
                (primers["forward_5_to_3"], primers["reverse_5_to_3"])
            )
    decoy_candidates.difference_update(canonical_uses)
    ordered_decoys = sorted(
        decoy_candidates,
        key=lambda sequence: _primer_sort_key(task, sequence),
    )
    if len(ordered_decoys) < len(canonical_uses):
        raise ValueError(
            f"{task.slug}: only {len(ordered_decoys)} task-local decoy primers for "
            f"{len(canonical_uses)} canonical primers"
        )
    decoys = ordered_decoys[: len(canonical_uses)]
    stocked_sequences = sorted(
        [*canonical_uses, *decoys],
        key=lambda sequence: _primer_sort_key(task, sequence),
    )
    primer_filenames = {
        sequence: f"primer-{index:02d}.txt"
        for index, sequence in enumerate(stocked_sequences, start=1)
    }
    primer_rows: list[dict[str, Any]] = []
    for sequence in stocked_sequences:
        filename = primer_filenames[sequence]
        (task_dir / filename).write_text(sequence + "\n")
        primer_rows.append(
            {
                "filename": filename,
                "sequence_5_to_3": sequence,
                "canonical": sequence in canonical_uses,
                "canonical_uses": canonical_uses.get(sequence, []),
            }
        )

    enzyme_rows = _write_enzyme_inventory(task_dir)

    index_lines = ["filename\treagent_class\tvalue"]
    index_lines.extend(
        f"{row['filename']}\tprimer\t{row['sequence_5_to_3']}" for row in primer_rows
    )
    index_lines.extend(
        f"{row['filename']}\tenzyme\t{row['enzyme']}" for row in enzyme_rows
    )
    (task_dir / "reagent_inventory.tsv").write_text("\n".join(index_lines) + "\n")

    protocol = _reagent_protocol(task, task_primers, primer_filenames)
    return protocol, {
        "primer_count": len(primer_rows),
        "canonical_primer_count": len(canonical_uses),
        "decoy_primer_count": len(decoys),
        "primers": primer_rows,
        "enzymes": enzyme_rows,
    }


def _write_fasta(record: SeqRecord, path: Path) -> None:
    sequence = str(record.seq).upper()
    lines = [
        f">{record.id}: {record.description} (circular)",
        *(sequence[index : index + 80] for index in range(0, len(sequence), 80)),
    ]
    path.write_text("\n".join(lines) + "\n")


def _write_clean_readme(output: Path) -> None:
    question_rows = "\n".join(
        f"| {task.title} | {task.request.rstrip('.')}. | "
        f"{task.solution_summary.rstrip('.')}. |"
        for task in TASKS
    )
    reagent_rows = "\n".join(
        f"| {task.title} reagent variant | 1 | 12 | 8 | 8 | "
        f"{4 * len(task.components)} | {len(ENZYME_REAGENTS)} |"
        for task in TASKS
        if task.slug in REAGENT_TASK_SLUGS
    )
    intent_rows = "\n".join(
        "| "
        + " | ".join(
            (
                task.title,
                str(INTENT_CHALLENGE_BY_SLUG[task.slug].tier),
                INTENT_CHALLENGE_BY_SLUG[task.slug].request.rstrip(".") + ".",
                "; ".join(INTENT_CHALLENGE_BY_SLUG[task.slug].intent_inferences),
                "; ".join(INTENT_CHALLENGE_BY_SLUG[task.slug].sequence_traps),
            )
        )
        + " |"
        for task in TASKS
    )
    lines = [
        "# Hard mixed-inventory cloning pilot",
        "",
        "This package preserves the easier `cloning_inventory_pilot_v1` set and "
        "adds six genuinely harder underlying constructs. These are not merely "
        "prompt-redacted versions of two-fragment swaps.",
        "A separate matched set, `questions_intent_challenge.jsonl`, keeps those "
        "six constructs and inventories fixed while replacing the component-level "
        "requests with experimental-intent prompts.",
        "",
        "Each JSONL record points to its complete inventory through the `files` "
        "field. Base-task inventories are under `cloning/<task-id>/`; fixed-reagent "
        "inventories are under `reagent_inventory/<task-id>/`. The runner attaches "
        "or copies every file from that directory into the model's working directory.",
        "",
        "## Inventory supplied",
        "",
        "Each selected iGEM item is represented twice: once as the circular physical "
        "carrier plasmid from the 2026 kit snapshot and once as the actual "
        "element-level Registry sequence. Thus the inventory includes the promoter, "
        "RBS, terminator, CDS, and backbone/device elements themselves, not merely "
        "the plasmids carrying them.",
        "",
        "| Question set | Tasks | Addgene plasmids/task | iGEM carrier plasmids/task | iGEM element records/task | Primers/task | Enzymes/task |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Base questions | 6 | 12 | 8 | 8 | 0 | {len(ENZYME_REAGENTS)} |",
        f"| Matched intent challenge | 6 | 12 | 8 | 8 | 0 | {len(ENZYME_REAGENTS)} |",
        reagent_rows,
        "",
        "The enzyme stock is non-empty for every task and contains: "
        f"{', '.join(ENZYME_REAGENTS)}. The three reagent variants additionally "
        "contain equal numbers of useful and decoy primers.",
        "",
        "## What makes these harder",
        "",
        "- No assembly method, backbone, insert source, plasmid name, or exact "
        "coordinates are disclosed.",
        "- Each task supplies 12 accession-only Addgene plasmids, eight QC-valid "
        "iGEM carrier plasmids, the corresponding eight iGEM elements, and a "
        "stocked enzyme panel, including irrelevant alternatives.",
        "- The exact products require three to five PCR-derived components.",
        "- All six tasks require frame-sensitive coding or tag junctions; three require "
        "two coding changes, and two require reverse-orienting a bacterial marker.",
        "- The matched intent prompts additionally avoid naming the reporter genes, "
        "resistance genes, peptide mechanism, or displaced starting parts.",
        "",
        "The verifier still compares the assembled circular product with one exact "
        "reference. Because the prompts are now less prescriptive, that score should "
        "be interpreted alongside the sequence visualization: another biologically "
        "reasonable architecture may not be sequence-identical to the reference. "
        "`validation/` contains exact FASTA references and annotated GenBank review "
        "references with complete component provenance.",
        "",
        "## Which requirements are realistic?",
        "",
        "The expressed protein, regulatory context, linked-versus-independent "
        "expression, selectable marker, and removal of an unwanted gene are ordinary "
        "real-world design requirements. Requiring genes to come from the available "
        "inventory is also realistic when a lab wants to reuse material on hand.",
        "",
        "The fixed primer-only variant is benchmark scaffolding that represents a "
        "stockroom exercise, not a universal laboratory requirement. The previous "
        "component-count limits, explicit stop-codon and reading-frame instructions, "
        "long lists of elements to retain, and directions about exact local edits were "
        "removed. Those details made the intended reference easier to infer and were "
        "more useful for constraining the verifier than for stating a normal request.",
        "",
        "## Primer inventory subset",
        "",
        "`questions_reagent_inventory.jsonl` contains three representative tasks: "
        "the 3-component TCF/LEF reporter, 4-component two-locus lentiviral edit, "
        "and 5-component Cas9/marker edit. Each has an equal number of canonical "
        "and decoy primer stocks. Primer and enzyme filenames are opaque; the model "
        "must select them by inspecting "
        "`reagent_inventory.tsv` or the individual stock files. Novel primers are "
        "not permitted in these variants. Both canonical and decoy primer stocks "
        "are drawn deterministically from primer designs against the attached "
        "Addgene sequence inventory rather than random DNA strings.",
        "",
        "Every base task and reagent task includes eight QC-valid plasmids sampled from the "
        "2026 iGEM distribution kit: a promoter, RBS, terminator, three unrelated "
        "CDS parts, a fluorescent-protein decoy, and a Type IIS destination "
        "backbone/device. Each carrier is paired with its separate element-level "
        "GenBank record. `igem_inventory.tsv` maps the pair and preserves plate, "
        "role, assembly, flanking-overhang, resistance, QC, and length metadata.",
        "",
        "The reagent-inventory prompt adds only this rule:",
        "",
        "> This version also has a fixed primer stock. Use only the stocked primers; "
        "some of them will not be relevant to this build.",
        "",
        "## Shared inventory suffix used on all questions",
        "",
        f"> {TASK_INVENTORY_SUFFIX}",
        "",
        "The suffix is present in each JSONL question but is shown only once here.",
        "",
        "## All six questions and intended work",
        "",
        "The intended-work column is reviewer-only and is not shown to the model.",
        "",
        "| Name | Question shown before the shared suffix | Intended solution/work |",
        "| --- | --- | --- |",
        question_rows,
        "",
        "## Matched intent challenge",
        "",
        "This is a controlled prompt-hardening experiment, not six new gold "
        "constructs. Each record has the same task ID, files, sources, exact reference, "
        "and functional constraint specification as its base counterpart. Only the "
        "question and difficulty metadata change. This makes a base-versus-intent "
        "score comparison interpretable.",
        "",
        "The model must infer the backbone class, functional parts, expression "
        "architecture, and assembly method. The so-called traps are not secret wishes: "
        "they are sequence-level consequences of requirements stated in the prompt, "
        "such as preserving a transfer vector's packaging elements, removing an "
        "unwanted resistance gene, or avoiding a stop codon inside a linked ORF. "
        "Reviewer metadata is also saved in `intent_challenge_design_v1.json`.",
        "",
        "| Reviewer name | Tier | Question shown before the shared suffix | Inference required | Sequence-level traps |",
        "| --- | ---: | --- | --- | --- |",
        intent_rows,
        "",
        "## Regeneration",
        "",
        "```bash",
        "uv run --extra lab_bench_2 python "
        "tools/generate_cloning_inventory_hard_questions.py \\",
        "  --input-dir /path/to/addgene-genbank-files \\",
        "  --igem-dir /path/to/igem-distribution-kit-2026 \\",
        "  --igem-elements-dir experiments/cloning_inventory_hard_v1/igem_element_sources \\",
        "  --output experiments/cloning_inventory_hard_v1",
        "```",
        "",
        "## Running",
        "",
        "```bash",
        "inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \\",
        "  -T tags=cloning -T mode=file -T solver=agentic \\",
        '  -T dataset_path="$PWD/experiments/cloning_inventory_hard_v1/questions.jsonl" \\',
        "  --model openai/gpt-5.6-sol --reasoning-effort max",
        "```",
        "",
        "To run the three-task primer/enzyme inventory subset, replace "
        "`questions.jsonl` above with `questions_reagent_inventory.jsonl`.",
        "To run the matched intent set, use `questions_intent_challenge.jsonl` "
        "instead. Use a distinct Inspect log name when comparing the two sets because "
        "their deliberately matched sample IDs are the same.",
    ]
    (output / "README.md").write_text("\n".join(lines) + "\n")


async def generate(
    input_dir: Path,
    igem_dir: Path,
    igem_elements_dir: Path,
    output: Path,
) -> None:
    used_ids = sorted({item for task in TASKS for item in task.inventory_ids})
    input_paths = {
        addgene_id: _input_path(input_dir, addgene_id) for addgene_id in used_ids
    }
    records = {
        addgene_id: SeqIO.read(path, "genbank")
        for addgene_id, path in input_paths.items()
    }
    igem_parts = _load_igem_parts(igem_dir, igem_elements_dir)
    for addgene_id, record in records.items():
        if record.annotations.get("topology") != "circular":
            raise ValueError(f"Addgene #{addgene_id} is not annotated as circular")

    output.mkdir(parents=True, exist_ok=True)
    (output / "cloning").mkdir(exist_ok=True)
    (output / "reagent_inventory").mkdir(exist_ok=True)
    (output / "validation").mkdir(exist_ok=True)
    (output / "canonical_protocols").mkdir(exist_ok=True)
    (output / "canonical_reagent_protocols").mkdir(exist_ok=True)

    questions: list[dict[str, Any]] = []
    intent_questions: list[dict[str, Any]] = []
    intent_review: list[dict[str, Any]] = []
    reagent_questions: list[dict[str, Any]] = []
    task_manifest: list[dict[str, Any]] = []
    reagent_manifest: list[dict[str, Any]] = []
    all_task_primers = {
        task.slug: _canonical_protocol(task, records)[1] for task in TASKS
    }
    for task in TASKS:
        task_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"labbench2:{TASK_ID_SEED_VERSION}:{task.slug}",
            )
        )
        task_dir = output / "cloning" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        for addgene_id in task.inventory_ids:
            shutil.copy2(
                input_paths[addgene_id], task_dir / f"addgene-{addgene_id}.gbk"
            )
        _copy_igem_inventory(igem_parts, task_dir)
        _write_enzyme_inventory(task_dir)

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

        if task.slug in REAGENT_TASK_SLUGS:
            reagent_dir = output / "reagent_inventory" / task_id
            reagent_dir.mkdir(parents=True, exist_ok=True)
            for addgene_id in task.inventory_ids:
                shutil.copy2(
                    input_paths[addgene_id],
                    reagent_dir / f"addgene-{addgene_id}.gbk",
                )
            _copy_igem_inventory(igem_parts, reagent_dir)
            reagent_protocol, reagent_details = _write_reagent_inventory(
                task,
                reagent_dir,
                primers,
                all_task_primers,
            )
            reagent_protocol_path = (
                output / "canonical_reagent_protocols" / f"{task_id}.txt"
            )
            reagent_protocol_path.write_text(reagent_protocol + "\n")
            reagent_expression = reagent_protocol.split("<protocol>", 1)[1].split(
                "</protocol>", 1
            )[0]
            reagent_products = await execute_cloning_protocol_v2(
                reagent_expression,
                reagent_dir,
            )
            reagent_exact_products = [
                index
                for index, product in enumerate(reagent_products)
                if product.is_circular
                and _circular_match(str(product.sequence), str(reference.seq))
            ]
            if reagent_exact_products != [0]:
                raise ValueError(
                    f"{task.slug}: expected one exact reagent-inventory product; "
                    f"got {len(reagent_products)} products and exact matches "
                    f"{reagent_exact_products}"
                )
            reagent_questions.append(
                _reagent_question_record(
                    task,
                    task_id,
                    reagent_details["primer_count"],
                    igem_parts,
                )
            )
            reagent_manifest.append(
                {
                    "id": task_id,
                    "slug": task.slug,
                    "canonical_product_count": len(reagent_products),
                    "canonical_exact_circular_match": True,
                    "igem_plasmid_count": len(igem_parts),
                    "igem_element_count": len(igem_parts),
                    **reagent_details,
                }
            )

        questions.append(_question_record(task, task_id, igem_parts))
        intent_questions.append(_intent_challenge_record(task, task_id, igem_parts))
        intent_review.append(_intent_challenge_review(task, task_id))
        task_manifest.append(
            {
                "id": task_id,
                "slug": task.slug,
                "title": task.title,
                "inventory_addgene_ids": list(task.inventory_ids),
                "inventory_igem_plasmid_count": len(igem_parts),
                "inventory_igem_element_count": len(igem_parts),
                "inventory_enzyme_count": len(ENZYME_REAGENTS),
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
    (output / "questions_intent_challenge.jsonl").write_text(
        "".join(
            json.dumps(question, sort_keys=True) + "\n" for question in intent_questions
        )
    )
    (output / "intent_challenge_design_v1.json").write_text(
        json.dumps(
            {
                "version": INTENT_CHALLENGE_VERSION,
                "design": "matched prompt-only hardening experiment",
                "shared_inventory_suffix": TASK_INVENTORY_SUFFIX,
                "tasks": intent_review,
            },
            indent=2,
        )
        + "\n"
    )
    (output / "questions_reagent_inventory.jsonl").write_text(
        "".join(
            json.dumps(question, sort_keys=True) + "\n"
            for question in reagent_questions
        )
    )
    manifest = {
        "version": VERSION,
        "generator": "tools/generate_cloning_inventory_hard_questions.py",
        "question_set": {
            "path": "questions.jsonl",
            "difficulty": "hard_inventory_multifragment",
        },
        "intent_challenge_question_set": {
            "path": "questions_intent_challenge.jsonl",
            "difficulty": "intent_driven_sequence_traps",
            "version": INTENT_CHALLENGE_VERSION,
            "task_count": len(intent_questions),
            "matched_question_set": "questions.jsonl",
            "reviewer_design": "intent_challenge_design_v1.json",
        },
        "reagent_inventory_question_set": {
            "path": "questions_reagent_inventory.jsonl",
            "difficulty": "hard_reagent_inventory",
            "task_count": len(reagent_questions),
            "task_slugs": list(REAGENT_TASK_SLUGS),
        },
        "inventory": [
            {
                "addgene_id": addgene_id,
                "name": ADDGENE_NAMES[addgene_id],
                "input_filename": input_paths[addgene_id].name,
                "sha256": _sha256(input_paths[addgene_id]),
                "length_bp": len(str(records[addgene_id].seq)),
                "topology": records[addgene_id].annotations.get("topology"),
            }
            for addgene_id in used_ids
        ],
        "igem_inventory": [_public_igem_part(part) for part in igem_parts],
        "tasks": task_manifest,
        "reagent_inventory_tasks": reagent_manifest,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    _write_clean_readme(output)


def main() -> None:
    args = parse_args()
    asyncio.run(
        generate(
            args.input_dir,
            args.igem_dir,
            args.igem_elements_dir,
            args.output,
        )
    )


if __name__ == "__main__":
    main()
