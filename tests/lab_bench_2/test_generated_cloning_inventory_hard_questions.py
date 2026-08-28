import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from evals.models import LabBenchQuestion
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.cloning_simulators.execution import execute_cloning_protocol_v2
from lab_bench_2.cloning_simulators.sequence_similarity_v2 import (
    sequence_similarity_v2,
)
from lab_bench_2.dataset import load_local_cloning_dataset

PILOT = Path(__file__).parents[2] / "experiments" / "cloning_inventory_hard_v1"
MANIFEST = json.loads((PILOT / "manifest.json").read_text())
TASKS: tuple[dict[str, Any], ...] = tuple(MANIFEST["tasks"])
QUESTIONS = [
    json.loads(line) for line in (PILOT / "questions.jsonl").read_text().splitlines()
]


def _reference(task: dict[str, Any]) -> SeqRecord:
    return SeqIO.read(
        PILOT / "validation" / f"{task['id']}_assembled.gbk",
        "genbank",
    )


def _circular_slice(sequence: str, start: int, length: int) -> str:
    return (sequence + sequence)[start : start + length]


def _translation_has_one_terminal_stop(sequence: str) -> None:
    assert len(sequence) % 3 == 0
    translation = str(Seq(sequence).translate())
    assert translation.startswith("M")
    assert translation.endswith("*")
    assert "*" not in translation[:-1]


def test_hard_manifest_and_questions_are_consistent() -> None:
    assert len(TASKS) == 6
    assert len(QUESTIONS) == 6
    assert {task["id"] for task in TASKS} == {
        question["id"] for question in QUESTIONS
    }
    assert {task["canonical_component_count"] for task in TASKS} == {3, 4, 5}

    for task in TASKS:
        assert len(task["inventory_addgene_ids"]) == 12
        assert task["canonical_exact_circular_match"]
        assert task["canonical_product_count"] == 1
        assert len(task["components"]) == task["canonical_component_count"]
    for question in QUESTIONS:
        LabBenchQuestion.model_validate(question)
        assert question["difficulty"]["name"] == "hard_inventory_multifragment"
        assert question["difficulty"]["method"] == "model_chooses"
        assert question["question"].count("`addgene-") == 12


def test_prompts_do_not_disclose_plasmid_names_sources_or_method() -> None:
    hidden_terms = (
        "pLJM1",
        "TOPFlash",
        "pCALNL",
        "pX330",
        "pET MBP",
        "lentiCRISPR",
        "Gibson assembly",
    )
    for question in QUESTIONS:
        text = question["question"]
        assert "filenames deliberately provide only accession numbers" in text
        assert "Choose any supported assembly method" in text
        assert all(term not in text for term in hidden_terms)


@pytest.mark.asyncio
@pytest.mark.parametrize("task", TASKS, ids=lambda task: str(task["slug"]))
async def test_canonical_protocol_produces_one_exact_circular_product(
    task: dict[str, Any],
) -> None:
    task_id = task["id"]
    protocol = (PILOT / "canonical_protocols" / f"{task_id}.txt").read_text()
    expression = protocol.split("<protocol>", 1)[1].split("</protocol>", 1)[0]
    products = await execute_cloning_protocol_v2(
        expression,
        PILOT / "cloning" / task_id,
    )
    reference = BioSequence.from_fasta(
        PILOT / "validation" / f"{task_id}_assembled.fa"
    )

    assert len(products) == 1
    assert products[0].is_circular
    assert sequence_similarity_v2(products[0], reference) == 1.0


@pytest.mark.parametrize("task", TASKS, ids=lambda task: str(task["slug"]))
def test_component_provenance_covers_the_complete_reference(
    task: dict[str, Any],
) -> None:
    reference = _reference(task)
    intervals = [
        component["reference_interval_zero_based_half_open"]
        for component in task["components"]
    ]
    cursor = 0
    for start, end in intervals:
        assert start == cursor
        assert end > start
        cursor = end
    assert cursor == len(str(reference.seq)) == task["reference_length_bp"]
    assert reference.annotations["topology"] == "circular"


def test_frame_sensitive_open_reading_frames_are_intact() -> None:
    records = {task["slug"]: str(_reference(task).seq).upper() for task in TASKS}

    # The Wnt construct begins with 15 bp of native initiation context.
    _translation_has_one_terminal_stop(records["wnt-egfp-p2a-puro"][15 : 15 + 1371])
    # The retained pLJM1 junction supplies the mCherry fusion stop.
    _translation_has_one_terminal_stop(
        records["lenti-mcherry-neor-two-locus"][:828]
    )
    _translation_has_one_terminal_stop(
        records["lenti-mcherry-neor-two-locus"][1476 : 1476 + 795]
    )
    _translation_has_one_terminal_stop(
        records["cre-tdtomato-p2a-puro"][:2082]
    )
    # Cas9 begins in the final backbone component and crosses the circular origin.
    cas9 = records["cas9-p2a-mcherry-kanr"]
    _translation_has_one_terminal_stop(_circular_slice(cas9, 4958, 5037))
    _translation_has_one_terminal_stop(cas9[2074 : 2074 + 816])
    # The retained destination ATG is the final codon of the second component.
    t7 = records["t7-histev-tdtomato-kanr"]
    _translation_has_one_terminal_stop(t7[3926 : 3926 + 1527])
    _translation_has_one_terminal_stop(t7[:816])
    _translation_has_one_terminal_stop(
        records["lenti-guide-mcherry-p2a-neor"][:1560]
    )


def test_review_references_retain_critical_annotations() -> None:
    records = {task["slug"]: _reference(task) for task in TASKS}

    def labels(slug: str) -> list[str]:
        return [
            str(
                (
                    feature.qualifiers.get("label")
                    or feature.qualifiers.get("gene")
                    or [""]
                )[0]
            )
            for feature in records[slug].features
        ]

    assert "TCF/LEF response-site array" in labels("wnt-egfp-p2a-puro")
    assert labels("cre-tdtomato-p2a-puro").count("loxP") == 2
    assert "P2A" in labels("cas9-p2a-mcherry-kanr")
    assert "KanR" in labels("cas9-p2a-mcherry-kanr")
    assert "6xHis" in labels("t7-histev-tdtomato-kanr")
    assert "TEV site" in labels("t7-histev-tdtomato-kanr")
    assert "WPRE" in labels("lenti-guide-mcherry-p2a-neor")


def test_packaged_inventory_files_match_manifest_hashes() -> None:
    hashes = {entry["addgene_id"]: entry["sha256"] for entry in MANIFEST["inventory"]}
    for task in TASKS:
        task_dir = PILOT / "cloning" / task["id"]
        for addgene_id in task["inventory_addgene_ids"]:
            path = task_dir / f"addgene-{addgene_id}.gbk"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes[addgene_id]


def test_hard_questions_load_as_a_local_file_dataset() -> None:
    dataset = load_local_cloning_dataset(PILOT / "questions.jsonl", mode="file")

    assert len(dataset) == 6
    assert all(sample.metadata is not None for sample in dataset)
