import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from evals.models import LabBenchQuestion
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.cloning_simulators.execution import execute_cloning_protocol_v2
from lab_bench_2.cloning_simulators.sequence_similarity_v2 import sequence_similarity_v2
from lab_bench_2.dataset import load_local_cloning_dataset

PILOT = Path(__file__).parents[2] / "experiments" / "cloning_inventory_pilot_v1"
MANIFEST = json.loads((PILOT / "manifest.json").read_text())
TASKS: tuple[dict[str, Any], ...] = tuple(MANIFEST["tasks"])
QUESTION_FILES = {
    "baseline": "questions.jsonl",
    "method_blind": "questions_method_blind.jsonl",
    "inventory_functional": "questions_inventory_functional.jsonl",
}


def _questions(filename: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (PILOT / filename).read_text().splitlines()]


def test_inventory_manifest_and_question_sets_are_consistent() -> None:
    expected_ids = {task["id"] for task in TASKS}

    assert len(MANIFEST["tasks"]) == 6
    assert {task["id"] for task in MANIFEST["tasks"]} == expected_ids
    assert {
        name: profile["path"] for name, profile in MANIFEST["question_sets"].items()
    } == QUESTION_FILES
    assert all(task["canonical_exact_circular_match"] for task in MANIFEST["tasks"])

    for filename in QUESTION_FILES.values():
        questions = _questions(filename)
        assert len(questions) == 6
        assert {question["id"] for question in questions} == expected_ids
        for question in questions:
            LabBenchQuestion.model_validate(question)


def test_difficulty_variants_change_only_prompt_disclosure() -> None:
    question_sets = {
        name: {question["id"]: question for question in _questions(filename)}
        for name, filename in QUESTION_FILES.items()
    }
    for task_id, baseline in question_sets["baseline"].items():
        for profile_name in ("method_blind", "inventory_functional"):
            variant = question_sets[profile_name][task_id]
            for field in (
                "id",
                "files",
                "sources",
                "prompt_suffix",
                "validator_params",
            ):
                assert variant[field] == baseline[field]

    baseline_text = "\n".join(
        str(question["question"]) for question in question_sets["baseline"].values()
    )
    method_blind_text = "\n".join(
        str(question["question"]) for question in question_sets["method_blind"].values()
    )
    inventory_text = "\n".join(
        str(question["question"])
        for question in question_sets["inventory_functional"].values()
    )
    assert "using Gibson assembly" in baseline_text
    assert "using Gibson assembly" not in method_blind_text
    assert "Choose an appropriate assembly method" in method_blind_text
    assert "as the backbone" in method_blind_text
    assert "no backbone or insert source has been preselected" in inventory_text
    assert "The finished construct must provide" in inventory_text
    assert "using Gibson assembly" not in inventory_text


@pytest.mark.parametrize("task", TASKS, ids=lambda task: str(task["slug"]))
def test_reference_is_the_configured_circular_replacement(
    task: dict[str, Any],
) -> None:
    task_id = task["id"]
    task_dir = PILOT / "cloning" / task_id
    destination_id = task["destination_addgene_id"]
    source_id = task["source_addgene_id"]
    destination = SeqIO.read(task_dir / f"addgene-{destination_id}.gbk", "genbank")
    source = SeqIO.read(task_dir / f"addgene-{source_id}.gbk", "genbank")
    source_start, source_end = task["source_interval_zero_based_half_open"]
    insert = str(source.seq)[source_start:source_end].upper()
    if restored := task["restored_destination_prefix"]:
        prefix_start, prefix_end = restored
        insert = str(destination.seq)[prefix_start:prefix_end].upper() + insert
    delete_start, delete_end = task["deleted_interval_zero_based_half_open"]
    destination_sequence = str(destination.seq).upper()
    expected = (
        insert + destination_sequence[delete_end:] + destination_sequence[:delete_start]
    )
    reference = BioSequence.from_fasta(PILOT / "validation" / f"{task_id}_assembled.fa")

    assert reference.is_circular
    assert reference.sequence == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("task", TASKS, ids=lambda task: str(task["slug"]))
async def test_canonical_protocol_produces_one_exact_circular_product(
    task: dict[str, Any],
) -> None:
    task_id = task["id"]
    task_dir = PILOT / "cloning" / task_id
    protocol_text = (PILOT / "canonical_protocols" / f"{task_id}.txt").read_text()
    expression = protocol_text.split("<protocol>", 1)[1].split("</protocol>", 1)[0]
    products = await execute_cloning_protocol_v2(
        expression,
        task_dir,
    )
    reference = BioSequence.from_fasta(PILOT / "validation" / f"{task_id}_assembled.fa")

    assert len(products) == 1
    assert products[0].is_circular
    assert sequence_similarity_v2(products[0], reference) == 1.0


def test_review_references_include_critical_functional_annotations() -> None:
    records = {
        task["slug"]: SeqIO.read(
            PILOT / "validation" / f"{task['id']}_assembled.gbk",
            "genbank",
        )
        for task in TASKS
    }

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

    assert labels("cre-mcherry").count("loxP") == 2
    assert "TCF/LEF response-site array" in labels("topflash-egfp")
    assert "P2A" in labels("cas9-p2a-puro")
    assert "PuroR" in labels("cas9-p2a-puro")
    assert "tdTomato" in labels("t7-tdtomato-his")
    assert "6xHis" in labels("t7-tdtomato-his")


def test_reference_translation_boundaries_are_functional() -> None:
    records = {
        task["slug"]: SeqIO.read(
            PILOT / "validation" / f"{task['id']}_assembled.gbk",
            "genbank",
        )
        for task in TASKS
    }
    coding_regions = {
        # slug: (start, length, expected translated tail)
        "lenti-mcherry": (0, 828, "GGTVQGKE*"),
        "topflash-egfp": (15, 720, "GMDELYK*"),
        "cre-mcherry": (0, 711, "GMDELYK*"),
        "lenti-egfp-neor": (0, 795, "YRLLDEFF*"),
        "cas9-p2a-puro": (0, 654, "CMTRKPGA*"),
        "t7-tdtomato-his": (0, 1458, "GSSHHHHHH*"),
    }

    for slug, (start, length, expected_tail) in coding_regions.items():
        coding_sequence = records[slug].seq[start : start + length]
        translation = str(Seq(coding_sequence).translate())
        assert translation.endswith(expected_tail)
        assert "*" not in translation[:-1]

    for slug, (start, _, _) in coding_regions.items():
        if slug != "cas9-p2a-puro":
            assert str(records[slug].seq[start : start + 3]).upper() == "ATG"


def test_packaged_inventory_files_match_manifest_hashes() -> None:
    hashes = {entry["addgene_id"]: entry["sha256"] for entry in MANIFEST["inventory"]}
    for task in TASKS:
        task_dir = PILOT / "cloning" / task["id"]
        for addgene_id in task["inventory_addgene_ids"]:
            path = task_dir / f"addgene-{addgene_id}.gbk"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes[addgene_id]


@pytest.mark.parametrize("question_file", QUESTION_FILES.values())
def test_each_question_set_loads_as_a_local_file_dataset(question_file: str) -> None:
    dataset = load_local_cloning_dataset(PILOT / question_file, mode="file")

    assert len(dataset) == 6
    assert all(sample.metadata is not None for sample in dataset)
