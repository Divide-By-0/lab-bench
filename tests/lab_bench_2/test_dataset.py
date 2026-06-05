from pathlib import Path
from typing import Any

import pytest
from evals.models import LabBenchQuestion
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, ContentDocument, ContentImage, ContentText

from lab_bench_2 import dataset as dataset_module
from lab_bench_2 import file_downloader
from lab_bench_2.dataset import (
    LAB_BENCH_2_DATASET_PATH,
    LAB_BENCH_2_DATASET_REVISION,
    MAX_TAGS_IN_DATASET_NAME,
    _multi_tags_dataset_name,
    _question_supports_mode,
    load_multi_tags_dataset,
    parse_validator_params,
    record_to_sample,
)
from utils.huggingface import (
    DatasetInfosDict,
    assert_huggingface_dataset_structure,
    get_dataset_infos_dict,
)


class TestRecordToSample:
    def test_maps_core_fields(self) -> None:
        # given a litqa3-style record (synthetic, schema-faithful)
        record = {
            "id": "litqa3-0001",
            "tag": "litqa3",
            "version": "1",
            "type": "",
            "question": "What protein does the human SNCA gene encode?",
            "ideal": "Alpha-synuclein",
            "sources": ["https://example.org/paper"],
            "prompt_suffix": "",
        }

        # when
        sut = record_to_sample(record)

        # then
        assert sut is not None
        assert str(sut.id).startswith("labbench2_")
        assert sut.target == "Alpha-synuclein"
        assert "SNCA" in str(sut.input)
        assert sut.metadata is not None
        assert sut.metadata["id"] == "litqa3-0001"
        assert sut.metadata["tag"] == "litqa3"
        assert sut.metadata["mode"] == "inject"
        assert sut.metadata["sources"] == ["https://example.org/paper"]

    def test_appends_prompt_suffix(self) -> None:
        # given a record with a prompt suffix
        record = {
            "id": "litqa3-0002",
            "tag": "litqa3",
            "version": "1",
            "question": "What is the capital of France?",
            "ideal": "Paris",
            "prompt_suffix": "Answer concisely.",
        }

        # when
        sut = record_to_sample(record)

        # then
        assert sut is not None
        assert str(sut.input).endswith("Answer concisely.")

    def test_defaults_when_optional_fields_missing(self) -> None:
        # given a record without optional fields
        record = {
            "id": "litqa3-0003",
            "tag": "litqa3",
            "version": "1",
            "question": "Q?",
            "ideal": "A",
        }

        # when
        sut = record_to_sample(record)

        # then
        assert sut is not None
        assert sut.metadata is not None
        assert sut.metadata["sources"] == []
        assert sut.metadata["type"] is None


def _file_bearing_record(**overrides: Any) -> dict[str, Any]:
    record = {
        "id": "seqqa2-0001",
        "tag": "seqqa2",
        "version": "1",
        "question": "Find the start codon.",
        "ideal": "ATG",
        "files": "seqqa2/0001",
        "mode": {"inject": True, "file": True, "retrieve": True},
    }
    record.update(overrides)
    return record


class TestQuestionSupportsMode:
    def test_rejects_file_bearing_question_when_mode_flag_is_false(self) -> None:
        # given a file-bearing question that disables file mode
        question = LabBenchQuestion.model_validate(
            _file_bearing_record(mode={"inject": True, "file": False, "retrieve": True})
        )

        # when / then
        assert not _question_supports_mode(question, "file")

    def test_accepts_file_bearing_question_when_mode_flag_is_true(self) -> None:
        # given a file-bearing question that enables retrieve mode
        question = LabBenchQuestion.model_validate(
            _file_bearing_record(mode={"inject": True, "file": True, "retrieve": True})
        )

        # when / then
        assert _question_supports_mode(question, "retrieve")

    def test_file_less_question_is_unaffected_by_mode_flags(self) -> None:
        # given a file-less record (no files key) — mode gating only applies
        # to file-bearing questions, so any mode is accepted
        question = LabBenchQuestion.model_validate(
            {
                "id": "litqa3-x",
                "tag": "litqa3",
                "version": "1",
                "question": "Q?",
                "ideal": "A",
            }
        )

        # when / then
        assert _question_supports_mode(question, "retrieve")


class TestParseValidatorParams:
    def test_parses_json_payload(self) -> None:
        assert parse_validator_params('{"k": 1}') == {"k": 1}

    def test_falls_back_to_python_literal(self) -> None:
        # given a single-quoted dict that's not valid JSON
        assert parse_validator_params("{'k': 1}") == {"k": 1}

    def test_empty_returns_empty_dict(self) -> None:
        assert parse_validator_params(None) == {}
        assert parse_validator_params("") == {}

    def test_rejects_non_dict_literal(self) -> None:
        with pytest.raises(ValueError, match="must parse to a dictionary"):
            parse_validator_params("[1, 2, 3]")


class TestFileModeIntegration:
    def test_file_mode_attaches_image_and_document(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a record whose files include a PDF and an image
        from PIL import Image  # noqa: PLC0415 -- test-local fixture image

        (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4")
        Image.new("RGB", (5, 5), color=(0, 0, 0)).save(tmp_path / "fig.png")
        _stub_file_downloader(tmp_path, monkeypatch)

        # when
        sut = record_to_sample(_file_bearing_record(), mode="file")

        # then
        assert sut is not None
        assert isinstance(sut.input, list)
        message = sut.input[0]
        assert isinstance(message, ChatMessageUser)
        kinds = [type(c).__name__ for c in message.content]
        assert kinds == ["ContentText", "ContentDocument", "ContentImage"]
        text = message.content[0]
        assert isinstance(text, ContentText)
        assert "refer to files using only their base names" in text.text
        document = message.content[1]
        assert isinstance(document, ContentDocument)
        assert document.mime_type == "application/pdf"
        image = message.content[2]
        assert isinstance(image, ContentImage)

    def test_retrieve_mode_lists_file_stems_and_skips_attachments(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a record with two sequence files
        (tmp_path / "plasmid_A.gb").write_text(">A")
        (tmp_path / "plasmid_B.fasta").write_text(">B")
        _stub_file_downloader(tmp_path, monkeypatch)

        # when
        sut = record_to_sample(_file_bearing_record(), mode="retrieve")

        # then — input is a plain string (no attachments) and stems are exposed
        assert sut is not None
        assert isinstance(sut.input, str)
        assert "plasmid_A, plasmid_B" in sut.input
        assert sut.metadata is not None
        assert sut.metadata["expected_file_stems"] == ["plasmid_A", "plasmid_B"]

    def test_inject_mode_inlines_text_files_into_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a record with an injectable text file
        (tmp_path / "notes.txt").write_text("payload")
        _stub_file_downloader(tmp_path, monkeypatch)

        # when
        sut = record_to_sample(_file_bearing_record(), mode="inject")

        # then
        assert sut is not None
        assert isinstance(sut.input, str)
        assert "## notes.txt" in sut.input
        assert "payload" in sut.input

    def test_difficulty_field_propagates_to_metadata_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a record with a difficulty field
        (tmp_path / "notes.txt").write_text("p")
        _stub_file_downloader(tmp_path, monkeypatch)

        # when
        sut = record_to_sample(_file_bearing_record(difficulty="hard"), mode="inject")

        # then
        assert sut is not None
        assert sut.metadata is not None
        assert sut.metadata["difficulty"] == "hard"

    def test_difficulty_omitted_from_metadata_when_absent(self) -> None:
        # given a file-less record without difficulty
        record = {
            "id": "litqa3-x",
            "tag": "litqa3",
            "version": "1",
            "question": "Q?",
            "ideal": "A",
        }

        # when
        sut = record_to_sample(record)

        # then
        assert sut is not None
        assert sut.metadata is not None
        assert "difficulty" not in sut.metadata


class TestMultiTagsDatasetName:
    def test_single_tag(self) -> None:
        assert _multi_tags_dataset_name(["litqa3"]) == "lab_bench_2_litqa3"

    def test_lists_all_tags_sorted_when_within_cap(self) -> None:
        # given tags out of order and within the cap
        assert (
            _multi_tags_dataset_name(["litqa3", "cloning"])
            == "lab_bench_2_cloning+litqa3"
        )

    def test_lists_all_tags_when_exactly_at_cap(self) -> None:
        tags = [f"t{i}" for i in range(MAX_TAGS_IN_DATASET_NAME)]
        expected = "lab_bench_2_" + "+".join(sorted(tags))
        assert _multi_tags_dataset_name(tags) == expected

    def test_elides_surplus_when_over_cap(self) -> None:
        # given one more tag than the cap
        tags = [f"t{i}" for i in range(MAX_TAGS_IN_DATASET_NAME + 1)]
        shown = "+".join(sorted(tags)[:MAX_TAGS_IN_DATASET_NAME])
        # then the surplus is elided as +N-more
        assert _multi_tags_dataset_name(tags) == f"lab_bench_2_{shown}+1-more"


class TestLoadAllTagsDataset:
    def test_concatenates_tags_and_preserves_tag_metadata(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a per-tag loader stubbed to avoid network, returning two
        # samples per tag
        def fake_loader(tag: str, mode: str = "file") -> list[Sample]:
            return [
                Sample(input="q", target="a", id=f"{tag}-{i}", metadata={"tag": tag})
                for i in range(2)
            ]

        monkeypatch.setattr(dataset_module, "load_lab_bench_2_dataset", fake_loader)

        # when loading several tags as one dataset
        requested = ["litqa3", "cloning"]
        sut = load_multi_tags_dataset(requested, mode="file")

        # then every requested subset contributes at least one sample (nothing
        # is silently dropped), each sample keeps its tag, and the dataset name
        # is derived from the (sorted) tag selection
        samples = list(sut)
        assert sut.name == "lab_bench_2_cloning+litqa3"
        loaded_tags = [s.metadata["tag"] for s in samples if s.metadata is not None]
        for tag in requested:
            assert loaded_tags.count(tag) == 2, (
                f"wrong number of samples loaded for tag {tag!r}"
            )
        assert len(samples) == 2 * len(requested)

    def test_forwards_mode_to_per_tag_loader(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a loader that records the mode it was called with
        seen: list[str] = []

        def fake_loader(tag: str, mode: str = "file") -> list[Sample]:
            seen.append(mode)
            return []

        monkeypatch.setattr(dataset_module, "load_lab_bench_2_dataset", fake_loader)

        # when
        load_multi_tags_dataset(["litqa3", "cloning"], mode="inject")

        # then the requested mode is forwarded for every tag
        assert seen == ["inject", "inject"]


def _stub_file_downloader(files_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the file_downloader module so dataset tests don't touch GCS."""
    monkeypatch.setattr(file_downloader, "fetch", lambda *_, **__: files_dir)


@pytest.fixture(scope="module")
def dataset_infos() -> DatasetInfosDict:
    return get_dataset_infos_dict(
        LAB_BENCH_2_DATASET_PATH, revision=LAB_BENCH_2_DATASET_REVISION
    )


@pytest.mark.huggingface
@pytest.mark.dataset_download
@pytest.mark.parametrize(
    "tag",
    ["litqa3", "patentqa", "protocolqa2", "sourcequality", "trialqa"],
)
def test_supported_tags_have_expected_schema(
    dataset_infos: DatasetInfosDict, tag: str
) -> None:
    assert_huggingface_dataset_structure(
        dataset_infos,
        {
            "configs": {
                tag: {
                    "splits": ["train"],
                    "features": {
                        "id": "string",
                        "question": "string",
                        "ideal": "string",
                        "tag": "string",
                    },
                }
            }
        },
    )
