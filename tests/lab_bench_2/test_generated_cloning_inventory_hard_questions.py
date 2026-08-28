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
REAGENT_QUESTIONS = [
    json.loads(line)
    for line in (PILOT / "questions_reagent_inventory.jsonl").read_text().splitlines()
]
REAGENT_TASKS: tuple[dict[str, Any], ...] = tuple(
    MANIFEST["reagent_inventory_tasks"]
)


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
        assert task["inventory_igem_part_count"] == 8
        assert task["canonical_exact_circular_match"]
        assert task["canonical_product_count"] == 1
        assert len(task["components"]) == task["canonical_component_count"]
    for question in QUESTIONS:
        LabBenchQuestion.model_validate(question)
        assert question["difficulty"]["name"] == "hard_inventory_multifragment"
        assert question["difficulty"]["method"] == "model_chooses"
        assert question["difficulty"]["igem_part_count"] == 8
        assert "All available Addgene and iGEM plasmids" in question["question"]
        assert "Do not synthesize genes de novo" in question["question"]


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
        assert "Available inventory:" not in text
        assert "Functional and construction constraints:" not in text
        assert "Choose any supported assembly method" not in text
        assert "The final circular construct" not in text
        assert "PCR-derived assembly components" not in text
        assert len(text) < 700
        assert all(term not in text for term in hidden_terms)


def test_reagent_inventory_subset_is_matched_and_opaque() -> None:
    assert len(REAGENT_QUESTIONS) == len(REAGENT_TASKS) == 3
    assert {question["id"] for question in REAGENT_QUESTIONS} == {
        task["id"] for task in REAGENT_TASKS
    }
    assert {task["canonical_primer_count"] // 2 for task in REAGENT_TASKS} == {
        3,
        4,
        5,
    }

    for question, task in zip(REAGENT_QUESTIONS, REAGENT_TASKS, strict=True):
        LabBenchQuestion.model_validate(question)
        assert question["difficulty"]["name"] == "hard_reagent_inventory"
        assert question["difficulty"]["novel_primers_allowed"] is False
        assert question["difficulty"]["igem_part_count"] == 8
        assert "fixed primer and enzyme stock" in question["question"]
        assert task["primer_count"] == 2 * task["canonical_primer_count"]
        assert task["decoy_primer_count"] == task["canonical_primer_count"]
        assert len(task["enzymes"]) == 8

        task_dir = PILOT / question["files"]
        primer_files = sorted(task_dir.glob("primer-*.txt"))
        enzyme_files = sorted(task_dir.glob("enzyme-*.txt"))
        igem_files = sorted(task_dir.glob("igem-*.gbk"))
        assert len(primer_files) == task["primer_count"]
        assert len(enzyme_files) == 8
        assert len(igem_files) == task["igem_part_count"] == 8
        assert all(
            SeqIO.read(path, "genbank").annotations.get("topology") == "circular"
            for path in igem_files
        )
        assert not list(task_dir.glob("igem-*.fasta"))
        assert not list(task_dir.glob("*.json"))
        assert all(path.read_text().strip().isalpha() for path in primer_files)
        assert {path.read_text().strip() for path in enzyme_files} == {
            "BamHI",
            "BsaI",
            "BsmBI",
            "EcoRI",
            "HindIII",
            "NdeI",
            "NotI",
            "XhoI",
        }
        index_lines = (task_dir / "reagent_inventory.tsv").read_text().splitlines()
        assert len(index_lines) == 1 + len(primer_files) + len(enzyme_files)
        assert len((task_dir / "igem_inventory.tsv").read_text().splitlines()) == 9


def test_selected_igem_inventory_is_qc_valid_and_hash_matched() -> None:
    parts = MANIFEST["igem_inventory"]

    assert len(parts) == 8
    assert {part["part_type"] for part in parts} >= {
        "cds",
        "plasmid backbone",
        "promoter",
        "rbs",
        "terminator",
    }
    assert all(part["is_valid"] and part["qc_status"] == "Correct" for part in parts)
    task_dirs = [PILOT / "cloning" / task["id"] for task in TASKS]
    task_dirs.extend(
        PILOT / "reagent_inventory" / task["id"] for task in REAGENT_TASKS
    )
    for task_dir in task_dirs:
        for part in parts:
            path = task_dir / part["filename"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == part["sha256"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task", REAGENT_TASKS, ids=lambda task: f"reagents-{task['slug']}"
)
async def test_stocked_primer_protocol_produces_exact_reference(
    task: dict[str, Any],
) -> None:
    task_id = task["id"]
    protocol = (
        PILOT / "canonical_reagent_protocols" / f"{task_id}.txt"
    ).read_text()
    expression = protocol.split("<protocol>", 1)[1].split("</protocol>", 1)[0]
    products = await execute_cloning_protocol_v2(
        expression,
        PILOT / "reagent_inventory" / task_id,
    )
    reference = BioSequence.from_fasta(
        PILOT / "validation" / f"{task_id}_assembled.fa"
    )

    assert '"' not in expression
    assert expression.count("primer-") == task["canonical_primer_count"]
    assert len(products) == 1
    assert products[0].is_circular
    assert sequence_similarity_v2(products[0], reference) == 1.0


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
    for sample in dataset:
        assert sample.metadata is not None
        inventory = Path(sample.metadata["files_path"])
        assert len(list(inventory.glob("igem-*.gbk"))) == 8
        assert (inventory / "igem_inventory.tsv").is_file()


def test_igem_files_are_exposed_in_file_and_inject_modes() -> None:
    file_sample = load_local_cloning_dataset(
        PILOT / "questions.jsonl", mode="file"
    )[0]
    assert isinstance(file_sample.input, list)
    assert isinstance(file_sample.input[0].content, list)
    attached_names = {
        getattr(item, "filename", None) for item in file_sample.input[0].content
    }
    assert sum(
        isinstance(name, str) and name.startswith("igem-")
        for name in attached_names
    ) == 8

    inject_sample = load_local_cloning_dataset(
        PILOT / "questions.jsonl", mode="inject"
    )[0]
    assert isinstance(inject_sample.input, str)
    assert inject_sample.input.count("## igem-") == 8


def test_reagent_questions_and_readme_are_reviewable() -> None:
    dataset = load_local_cloning_dataset(
        PILOT / "questions_reagent_inventory.jsonl", mode="file"
    )
    readme = (PILOT / "README.md").read_text()

    assert len(dataset) == 3
    assert "## Reagent-inventory questions for review (3 of 6)" in readme
    assert "## Which requirements are realistic?" in readme
    reagent_slugs = {task["slug"] for task in REAGENT_TASKS}
    for task in TASKS:
        if task["slug"] not in reagent_slugs:
            continue
        assert task["title"] in readme
    assert "questions_reagent_inventory.jsonl" in readme
