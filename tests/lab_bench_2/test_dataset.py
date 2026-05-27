from pathlib import Path
from typing import Any

import pytest
from inspect_ai.model import ChatMessageUser, ContentDocument, ContentImage, ContentText

from lab_bench_2 import dataset as dataset_module
from lab_bench_2.dataset import (
    LAB_BENCH_2_DATASET_PATH,
    LAB_BENCH_2_DATASET_REVISION,
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


class TestModeGating:
    def test_returns_none_when_question_does_not_support_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a file-bearing question that disables file mode
        record = _file_bearing_record(
            mode={"inject": True, "file": False, "retrieve": True}
        )
        _stub_file_downloader(tmp_path, monkeypatch)

        # when
        sut = record_to_sample(record, mode="file")

        # then
        assert sut is None

    def test_file_less_question_is_unaffected_by_mode_flags(self) -> None:
        # given a file-less record (no files key) — mode gating only kicks in for
        # file-bearing questions, so any mode is accepted
        record = {
            "id": "litqa3-x",
            "tag": "litqa3",
            "version": "1",
            "question": "Q?",
            "ideal": "A",
        }

        # when
        sut = record_to_sample(record, mode="retrieve")

        # then
        assert sut is not None


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


class TestLoadDataset:
    def test_forwards_shuffle_to_hf_dataset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a stubbed hf_dataset that records its kwargs
        captured: dict[str, Any] = {}

        def fake_hf_dataset(**kwargs: Any) -> object:
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(dataset_module, "hf_dataset", fake_hf_dataset)

        # when
        from lab_bench_2.dataset import load_lab_bench_2_dataset

        load_lab_bench_2_dataset(tag="litqa3", shuffle=True)

        # then
        assert captured["shuffle"] is True

    def test_shuffle_defaults_to_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # given a stubbed hf_dataset that records its kwargs
        captured: dict[str, Any] = {}

        def fake_hf_dataset(**kwargs: Any) -> object:
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(dataset_module, "hf_dataset", fake_hf_dataset)

        # when
        from lab_bench_2.dataset import load_lab_bench_2_dataset

        load_lab_bench_2_dataset(tag="litqa3")

        # then
        assert captured["shuffle"] is False


def _stub_file_downloader(files_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace dataset.FileDownloader with a stub that returns ``files_dir``."""

    class StubFileDownloader:
        def fetch(self, gcs_prefix: str) -> Path:
            return files_dir

        @staticmethod
        def list_files(directory: Path) -> list[Path]:
            return sorted(p for p in directory.iterdir() if p.is_file())

    monkeypatch.setattr(dataset_module, "FileDownloader", StubFileDownloader)


@pytest.fixture(scope="module")
def dataset_infos() -> DatasetInfosDict:
    return get_dataset_infos_dict(
        LAB_BENCH_2_DATASET_PATH, revision=LAB_BENCH_2_DATASET_REVISION
    )


@pytest.mark.huggingface
@pytest.mark.dataset_download
def test_litqa3_dataset_structure(dataset_infos: DatasetInfosDict) -> None:
    assert_huggingface_dataset_structure(
        dataset_infos,
        {
            "configs": {
                "litqa3": {
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
