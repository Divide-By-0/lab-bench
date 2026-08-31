#!/usr/bin/env python3
"""Generate three small CloningQA-style replacement tasks from two plasmids.

This is intentionally a manifest-free pilot generator. It turns a destination
plasmid and a source plasmid into self-contained task packages for replacing a
known destination interval with complete, annotated source CDSs. The generated
canonical Gibson protocols are executed with cloning simulator v2 and must
reproduce the independently spliced circular references exactly.
"""

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
from Bio.SeqFeature import SeqFeature, SimpleLocation
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

DESTINATION_FILENAME = "pcmv-mmlvgag-3xnes-cas9.gbk"
SOURCE_FILENAME = "pcalnl-gfp.gbk"
DESTINATION_LABEL = "pCMV-MMLVgag-3xNES-Cas9"
SOURCE_LABEL = "pCALNL-GFP"
DESTINATION_ADDGENE_ID = 181752
SOURCE_ADDGENE_ID = 13770
REPLACE_START = 0
REPLACE_END = 6027
OVERLAP_LENGTH = 20
ANNEAL_LENGTH = 20

PROTOCOL_SUFFIX = CLONING_PROTOCOL_SUFFIX


@dataclass(frozen=True)
class InsertSpec:
    """One complete source CDS used as a replacement insert."""

    slug: str
    label: str
    prompt_name: str


INSERTS = (
    InsertSpec("egfp", "EGFP", "EGFP"),
    InsertSpec("ampr", "AmpR", "AmpR/bla"),
    InsertSpec("neor-kanr", "NeoR/KanR", "NeoR/KanR"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/cloning_pilot_181752_13770"),
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _feature_label(feature: SeqFeature) -> str:
    for key in ("label", "gene"):
        if values := feature.qualifiers.get(key):
            return str(values[0])
    return ""


def _complete_cds(record: SeqRecord, label: str) -> tuple[SeqFeature, str]:
    stops = {"TAA", "TAG", "TGA"}
    candidates: list[tuple[SeqFeature, str]] = []
    for feature in record.features:
        if feature.type != "CDS" or _feature_label(feature) != label:
            continue
        sequence = str(feature.extract(record.seq)).upper()
        if (
            sequence.startswith("ATG")
            and sequence[-3:] in stops
            and len(sequence) % 3 == 0
        ):
            candidates.append((feature, sequence))
    if len(candidates) != 1:
        raise ValueError(
            f"Expected one complete in-frame CDS labelled {label!r}; found {len(candidates)}"
        )
    return candidates[0]


def _reverse_complement(sequence: str) -> str:
    return str(Seq(sequence).reverse_complement())


def _task_id(slug: str) -> str:
    seed = (
        f"labbench2-cloning-pilot:addgene-{DESTINATION_ADDGENE_ID}:"
        f"addgene-{SOURCE_ADDGENE_ID}:{slug}"
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _primers(backbone: str, insert: str) -> dict[str, str]:
    overlap = OVERLAP_LENGTH
    anneal = ANNEAL_LENGTH
    return {
        "backbone_forward": backbone[:anneal],
        "backbone_reverse": _reverse_complement(backbone[-anneal:]),
        "insert_forward": backbone[-overlap:] + insert[:anneal],
        "insert_reverse": (
            _reverse_complement(backbone[:overlap])
            + _reverse_complement(insert[-anneal:])
        ),
    }


def _canonical_protocol(primers: dict[str, str]) -> str:
    return f"""<protocol>
gibson(
    pcr({DESTINATION_FILENAME}, \"{primers["backbone_forward"]}\", \"{primers["backbone_reverse"]}\"),
    pcr({SOURCE_FILENAME}, \"{primers["insert_forward"]}\", \"{primers["insert_reverse"]}\")
)
</protocol>"""


def _circular_match(first: str, second: str) -> bool:
    if len(first) != len(second):
        return False
    return first in second + second or _reverse_complement(first) in second + second


def _reference_record(
    destination: SeqRecord,
    source_feature: SeqFeature,
    insert: str,
    task_id: str,
    insert_label: str,
) -> SeqRecord:
    destination_sequence = str(destination.seq).upper()
    retained = destination_sequence[REPLACE_END:]
    assembled = insert + retained
    record = SeqRecord(
        Seq(assembled),
        id=task_id,
        name=f"pilot-{insert_label}"[:16],
        description=(
            f"{DESTINATION_LABEL} with its full fusion ORF replaced by {insert_label}"
        ),
    )
    record.annotations = copy.deepcopy(destination.annotations)
    record.annotations["molecule_type"] = "DNA"
    record.annotations["topology"] = "circular"
    record.annotations["comment"] = (
        f"Pilot task {task_id}. Direct sequence reference generated by replacing "
        f"destination bases {REPLACE_START}:{REPLACE_END} with the complete "
        f"{insert_label} CDS extracted from {SOURCE_LABEL} (Addgene "
        f"#{SOURCE_ADDGENE_ID})."
    )
    record.features = [
        SeqFeature(SimpleLocation(0, len(assembled)), type="source"),
        SeqFeature(
            SimpleLocation(0, len(insert), strand=1),
            type="misc_feature",
            qualifiers={
                "label": [f"{insert_label} insert"],
                "note": [
                    f"Sequence provenance: {SOURCE_LABEL} (Addgene #{SOURCE_ADDGENE_ID})"
                ],
            },
        ),
        SeqFeature(
            SimpleLocation(len(insert), len(assembled), strand=1),
            type="misc_feature",
            qualifiers={
                "label": [f"retained {DESTINATION_LABEL} backbone"],
                "note": [
                    f"Sequence provenance: {DESTINATION_LABEL} "
                    f"(Addgene #{DESTINATION_ADDGENE_ID}), original bases "
                    f"{REPLACE_END}:{len(destination_sequence)}"
                ],
            },
        ),
    ]

    insert_cds = copy.deepcopy(source_feature)
    insert_cds.location = SimpleLocation(0, len(insert), strand=1)
    insert_cds.qualifiers = copy.deepcopy(source_feature.qualifiers)
    insert_cds.qualifiers["label"] = [insert_label]
    insert_cds.qualifiers.setdefault("note", []).append(
        f"Sequence provenance: complete CDS from {SOURCE_LABEL} "
        f"(Addgene #{SOURCE_ADDGENE_ID})"
    )
    record.features.append(insert_cds)

    shift = len(insert) - REPLACE_END
    for feature in destination.features:
        if feature.type == "source" or int(feature.location.start) < REPLACE_END:
            continue
        retained_feature = copy.deepcopy(feature)
        retained_feature.location = feature.location + shift
        retained_feature.qualifiers = copy.deepcopy(feature.qualifiers)
        retained_feature.qualifiers.setdefault("note", []).append(
            f"Sequence provenance: {DESTINATION_LABEL} "
            f"(Addgene #{DESTINATION_ADDGENE_ID})"
        )
        record.features.append(retained_feature)
    return record


def _question_spec(insert: InsertSpec) -> CloningQuestionSpec:
    return CloningQuestionSpec(
        goal=(
            "I want to make a compact mammalian expression plasmid expressing "
            f"{insert.prompt_name}"
        ),
        named_backbone_instruction=(
            f"Use {DESTINATION_LABEL} (Addgene #{DESTINATION_ADDGENE_ID}) as the "
            "backbone"
        ),
        exact_architecture=(
            (
                "Replace the complete MMLV-Gag-3xNES-Cas9 fusion coding sequence, "
                "from its start codon through its stop codon, with the complete "
                f"{insert.prompt_name} coding sequence (CDS) from {SOURCE_LABEL} "
                f"(Addgene #{SOURCE_ADDGENE_ID}), including the insert's native "
                "stop codon"
            ),
            (
                "Preserve the backbone's existing CMV promoter, beta-globin "
                "poly(A) signal, bacterial origin, and selectable marker"
            ),
        ),
        inventory=(
            InventoryItem(
                name=DESTINATION_LABEL,
                accession=f"Addgene #{DESTINATION_ADDGENE_ID}",
                filename=DESTINATION_FILENAME,
                description=(
                    "a circular mammalian expression plasmid containing a strong "
                    "constitutive promoter, a large retroviral/Cas9 fusion ORF, a "
                    "mammalian polyadenylation signal, a bacterial origin, and a "
                    "bacterial selectable marker"
                ),
            ),
            InventoryItem(
                name=SOURCE_LABEL,
                accession=f"Addgene #{SOURCE_ADDGENE_ID}",
                filename=SOURCE_FILENAME,
                description=(
                    "a circular plasmid with annotated complete EGFP, AmpR/bla, "
                    "and NeoR/KanR coding sequences among its available parts"
                ),
            ),
        ),
        functional_requirements=(
            f"constitutive mammalian expression of one intact {insert.prompt_name} "
            "coding sequence with its own start and stop codons",
            "a mammalian transcription-termination and polyadenylation signal",
            "a bacterial origin of replication and bacterial selection",
            "no remaining MMLV-Gag-3xNES-Cas9 fusion coding sequence",
        ),
        preservation_rule=(
            "Make the smallest sequence change needed to a selected inventory "
            "backbone: preserve its sequence outside the replaced mammalian "
            "protein-coding region rather than redesigning the other elements"
        ),
        assembly_method="Gibson",
    )


def _question(
    task_id: str, insert: InsertSpec, dials: DifficultyDials = BASELINE
) -> dict[str, Any]:
    question = render_cloning_question(_question_spec(insert), dials)
    return {
        "id": task_id,
        "tag": "cloning",
        "version": "pilot-1.0",
        "type": "gibson",
        "question": question,
        "ideal": "",
        "files": f"cloning/{task_id}",
        "sources": [
            f"https://www.addgene.org/{DESTINATION_ADDGENE_ID}/",
            f"https://www.addgene.org/{SOURCE_ADDGENE_ID}/",
        ],
        "prompt_suffix": PROTOCOL_SUFFIX,
        "validator_params": "{}",
        "answer_regex": "",
        "mode": {"inject": True, "file": True, "retrieve": True},
        **({"difficulty": dials.metadata()} if dials != BASELINE else {}),
    }


def _write_fasta(record: SeqRecord, path: Path) -> None:
    sequence = str(record.seq).upper()
    lines = [
        f">{record.id}: {record.description} (circular)",
        *(sequence[index : index + 80] for index in range(0, len(sequence), 80)),
    ]
    path.write_text("\n".join(lines) + "\n")


async def _generate(destination_path: Path, source_path: Path, output: Path) -> None:
    destination = SeqIO.read(destination_path, "genbank")
    source = SeqIO.read(source_path, "genbank")
    destination_sequence = str(destination.seq).upper()
    replaced = destination_sequence[REPLACE_START:REPLACE_END]
    if not (
        destination.annotations.get("topology") == "circular"
        and replaced.startswith("ATG")
        and replaced[-3:] in {"TAA", "TAG", "TGA"}
        and len(replaced) % 3 == 0
    ):
        raise ValueError(
            "Configured destination replacement is not a complete circular-plasmid ORF"
        )

    output.mkdir(parents=True, exist_ok=True)
    (output / "cloning").mkdir(exist_ok=True)
    (output / "validation").mkdir(exist_ok=True)
    (output / "canonical_protocols").mkdir(exist_ok=True)

    backbone = destination_sequence[REPLACE_END:]
    question_sets: dict[str, list[dict[str, Any]]] = {
        profile.name: [] for profile in DIFFICULTY_PROFILES
    }
    tasks: list[dict[str, Any]] = []
    for insert_spec in INSERTS:
        source_feature, insert_sequence = _complete_cds(source, insert_spec.label)
        task_id = _task_id(insert_spec.slug)
        task_dir = output / "cloning" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination_path, task_dir / DESTINATION_FILENAME)
        shutil.copy2(source_path, task_dir / SOURCE_FILENAME)

        primers = _primers(backbone, insert_sequence)
        protocol = _canonical_protocol(primers)
        reference = _reference_record(
            destination,
            source_feature,
            insert_sequence,
            task_id,
            insert_spec.label,
        )
        fasta_path = output / "validation" / f"{task_id}_assembled.fa"
        genbank_path = output / "validation" / f"{task_id}_assembled.gbk"
        protocol_path = output / "canonical_protocols" / f"{task_id}.txt"
        _write_fasta(reference, fasta_path)
        SeqIO.write([reference], genbank_path, "genbank")
        protocol_path.write_text(protocol + "\n")

        products = await execute_cloning_protocol_v2(protocol, task_dir)
        exact_products = [
            index
            for index, product in enumerate(products)
            if product.is_circular
            and _circular_match(
                str(product.sequence).upper(), str(reference.seq).upper()
            )
        ]
        if exact_products != [0]:
            raise ValueError(
                f"{insert_spec.label}: expected one exact canonical product, got "
                f"{len(products)} products and matches {exact_products}"
            )

        for profile in DIFFICULTY_PROFILES:
            question_sets[profile.name].append(_question(task_id, insert_spec, profile))
        tasks.append(
            {
                "id": task_id,
                "slug": insert_spec.slug,
                "insert_label": insert_spec.label,
                "source_feature_location": str(source_feature.location),
                "replacement_interval_zero_based_half_open": [
                    REPLACE_START,
                    REPLACE_END,
                ],
                "insert_length_bp": len(insert_sequence),
                "retained_backbone_length_bp": len(backbone),
                "reference_length_bp": len(str(reference.seq)),
                "reference_is_circular": True,
                "primers_5_to_3": primers,
                "canonical_product_count": len(products),
                "canonical_exact_circular_match": True,
            }
        )

    question_paths = {
        BASELINE.name: output / "questions.jsonl",
        METHOD_BLIND.name: output / "questions_method_blind.jsonl",
        INVENTORY_FUNCTIONAL.name: output / "questions_inventory_functional.jsonl",
    }
    for profile_name, questions_path in question_paths.items():
        questions_path.write_text(
            "".join(
                json.dumps(question, sort_keys=True) + "\n"
                for question in question_sets[profile_name]
            )
        )
    manifest = {
        "generator": "tools/generate_cloning_pilot.py",
        "destination": {
            "label": DESTINATION_LABEL,
            "addgene_id": DESTINATION_ADDGENE_ID,
            "input_filename": destination_path.name,
            "sha256": _sha256(destination_path),
            "length_bp": len(destination.seq),
            "topology": destination.annotations.get("topology"),
        },
        "source": {
            "label": SOURCE_LABEL,
            "addgene_id": SOURCE_ADDGENE_ID,
            "input_filename": source_path.name,
            "sha256": _sha256(source_path),
            "length_bp": len(source.seq),
            "topology": source.annotations.get("topology"),
        },
        "assembly_method": "Gibson",
        "overlap_length_bp": OVERLAP_LENGTH,
        "question_sets": {
            profile.name: {
                "path": question_paths[profile.name].name,
                "dials": profile.metadata(),
            }
            for profile in DIFFICULTY_PROFILES
        },
        "tasks": tasks,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    args = _parse_args()
    asyncio.run(_generate(args.destination, args.source, args.output))


if __name__ == "__main__":
    main()
