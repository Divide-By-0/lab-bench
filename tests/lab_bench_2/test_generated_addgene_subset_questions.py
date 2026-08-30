import json
from pathlib import Path

import pytest
from evals.models import LabBenchQuestion
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.addgene_inventory_subset import subset_gbk_dir
from lab_bench_2.cloning_simulators.execution import execute_cloning_protocol_v2
from lab_bench_2.cloning_simulators.sequence_similarity_v2 import sequence_similarity_v2
from lab_bench_2.dataset import load_local_cloning_dataset
from lab_bench_2.prompt_composer import CLONING_FILE_REFERENCE_GUIDANCE

PACK = Path(__file__).parents[2] / "experiments" / "cloning_addgene_subset_v1"
QUESTIONS = [
    json.loads(line) for line in (PACK / "questions.jsonl").read_text().splitlines()
]
REVIEWS = json.loads((PACK / "reviews.json").read_text())
GBK_COUNT = len(list(subset_gbk_dir().glob("addgene-plasmid-*.gbk")))


def test_addgene_subset_pack_covers_each_tracked_gbk() -> None:
    assert GBK_COUNT == 55
    assert len(QUESTIONS) == 55
    assert len(REVIEWS) == 55
    assert {question["id"] for question in QUESTIONS} == {
        review["id"] for review in REVIEWS
    }
    assert len({question["id"] for question in QUESTIONS}) == 55
    assert {review["backbone_file"] for review in REVIEWS} == {
        path.name for path in subset_gbk_dir().glob("addgene-plasmid-*.gbk")
    }
    assert all(review["simulator_verified"] for review in REVIEWS)


def test_addgene_subset_questions_match_labbench_schema() -> None:
    for question in QUESTIONS:
        parsed = LabBenchQuestion.model_validate(question)
        assert parsed.tag == "cloning"
        assert parsed.ideal == ""
        assert question["files"] == "cloning/shared"
        assert question["type"] == "gibson"
        assert CLONING_FILE_REFERENCE_GUIDANCE in question["prompt_suffix"]
        assert question["difficulty"]["name"] == "addgene_subset_cds_swap"
        assert question["difficulty"]["component_count"] == 2
        fasta = PACK / "validation" / f"{question['id']}_assembled.fa"
        protocol = PACK / "canonical_protocols" / f"{question['id']}.txt"
        assert fasta.is_file()
        assert protocol.is_file()
        assert "<protocol>" in protocol.read_text()
        assert "gibson(" in protocol.read_text()


def test_addgene_subset_scientist_keys_exist() -> None:
    keys = (PACK / "ANSWER_KEYS.md").read_text()
    tsv = (PACK / "answer_keys.tsv").read_text().splitlines()
    assert keys.count("| yes |") == 55
    assert len(tsv) == 56
    assert (PACK / "README.md").read_text().count("gpt-5.6-sol") == 1
    shared = PACK / "cloning" / "shared"
    assert len(list(shared.glob("addgene-plasmid-*.gbk"))) == 55
    assert (shared / "enzyme_inventory.tsv").is_file()


def test_addgene_subset_includes_gibson_and_golden_gate_destinations() -> None:
    methods = {review["catalog_method"] for review in REVIEWS}
    assert "gibson" in methods
    assert "oligo_gg" in methods
    assert "golden_gate" in methods
    assert "hierarchical_gg" in methods
    dual_maps = [review for review in REVIEWS if review["map_note"]]
    assert len(dual_maps) == 8
    questions_by_id = {question["id"]: question for question in QUESTIONS}
    for review in dual_maps:
        assert review["map_note"] in questions_by_id[review["id"]]["question"]


def test_addgene_subset_loads_as_local_file_mode_dataset() -> None:
    dataset = load_local_cloning_dataset(PACK / "questions.jsonl", mode="file")
    assert len(dataset) == 55
    for sample in dataset:
        assert sample.metadata is not None
        assert Path(sample.metadata["files_path"]).is_dir()
        assert Path(sample.metadata["reference_path"]).is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_id",
    [
        REVIEWS[0]["id"],
        next(
            review["id"] for review in REVIEWS if review["catalog_method"] == "oligo_gg"
        ),
        next(review["id"] for review in REVIEWS if review["replace_strand"] == -1),
    ],
)
async def test_pydna_simulators_reproduce_addgene_subset_references(
    task_id: str,
) -> None:
    protocol_text = (PACK / "canonical_protocols" / f"{task_id}.txt").read_text()
    expression = protocol_text.split("<protocol>", 1)[1].split("</protocol>", 1)[0]
    products = await execute_cloning_protocol_v2(
        expression,
        PACK / "cloning" / "shared",
    )
    reference = BioSequence.from_fasta(PACK / "validation" / f"{task_id}_assembled.fa")
    assert len(products) == 1
    assert products[0].is_circular
    assert sequence_similarity_v2(products[0], reference) == 1.0
