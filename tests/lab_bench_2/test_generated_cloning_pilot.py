import json
from pathlib import Path

import pytest
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from evals.models import LabBenchQuestion
from labbench2.cloning.cloning_protocol import CloningProtocol
from labbench2.cloning.sequence_models import BioSequence

from lab_bench_2.dataset import load_local_cloning_dataset
from lab_bench_2.prompt_composer import CLONING_FILE_REFERENCE_GUIDANCE

PILOT = Path(__file__).parents[2] / "experiments" / "cloning_pilot_181752_13770"
EXPECTED = {
    "777f42d4-f239-5979-8a6e-e13daceba2a3": ("EGFP", 5476),
    "a641ec71-1142-5e19-a1c5-354142bcc6c4": ("AmpR", 5617),
    "02e631d2-19f5-50f9-a43a-af5e7440fb7d": ("NeoR/KanR", 5551),
}


def _complete_cds(record: SeqRecord, label: str) -> str:
    candidates = []
    for feature in record.features:
        feature_label = (feature.qualifiers.get("label") or [""])[0]
        sequence = str(feature.extract(record.seq)).upper()
        if (
            feature.type == "CDS"
            and feature_label == label
            and sequence.startswith("ATG")
            and sequence[-3:] in {"TAA", "TAG", "TGA"}
            and len(sequence) % 3 == 0
        ):
            candidates.append(sequence)
    assert len(candidates) == 1
    return candidates[0]


@pytest.mark.parametrize(("task_id", "expected"), EXPECTED.items())
def test_pilot_reference_is_direct_circular_replacement(
    task_id: str, expected: tuple[str, int]
) -> None:
    label, expected_length = expected
    task_dir = PILOT / "cloning" / task_id
    destination = SeqIO.read(task_dir / "pcmv-mmlvgag-3xnes-cas9.gbk", "genbank")
    source = SeqIO.read(task_dir / "pcalnl-gfp.gbk", "genbank")
    insert = _complete_cds(source, label)
    reference = BioSequence.from_fasta(PILOT / "validation" / f"{task_id}_assembled.fa")

    assert reference.is_circular
    assert len(reference.sequence) == expected_length
    assert reference.sequence == insert + str(destination.seq[6027:]).upper()

    protocol = CloningProtocol.from_file(
        PILOT / "canonical_protocols" / f"{task_id}.txt"
    )
    assert protocol.operation.file_references() == {
        "pcmv-mmlvgag-3xnes-cas9.gbk",
        "pcalnl-gfp.gbk",
    }


def test_pilot_question_records_and_manifest_are_consistent() -> None:
    questions = [
        LabBenchQuestion.model_validate_json(line)
        for line in (PILOT / "questions.jsonl").read_text().splitlines()
    ]
    manifest = json.loads((PILOT / "manifest.json").read_text())

    assert {question.id for question in questions} == set(EXPECTED)
    assert {task["id"] for task in manifest["tasks"]} == set(EXPECTED)
    assert all(question.type == "gibson" for question in questions)
    assert all(question.validator_params == "{}" for question in questions)
    assert all(
        CLONING_FILE_REFERENCE_GUIDANCE in question.prompt_suffix
        for question in questions
    )
    assert all(task["canonical_exact_circular_match"] for task in manifest["tasks"])


def test_pilot_loads_as_local_file_mode_dataset() -> None:
    dataset = load_local_cloning_dataset(PILOT / "questions.jsonl", mode="file")

    assert len(dataset) == 3
    for sample in dataset:
        assert sample.metadata is not None
        assert Path(sample.metadata["files_path"]).is_dir()
        assert Path(sample.metadata["reference_path"]).is_file()
