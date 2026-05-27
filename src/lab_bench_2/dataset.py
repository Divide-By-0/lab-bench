"""Dataset loading for the LAB-Bench 2 evaluation.

Questions live in a single (gated) HuggingFace dataset broken up by tags.
File-bearing tags can be served in three modes — ``inject`` / ``file`` /
``retrieve`` — orchestrated here via ``FileDownloader``, ``AttachmentBuilder``,
and ``PromptComposer``.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, cast

from evals.models import LabBenchQuestion
from inspect_ai.dataset import Dataset, Sample, hf_dataset
from inspect_ai.model import ChatMessage, ChatMessageUser, Content, ContentText

from lab_bench_2.attachment_builder import AttachmentBuilder
from lab_bench_2.file_downloader import FileDownloader
from lab_bench_2.prompt_composer import Mode, PromptComposer
from utils.sample_ids import create_stable_id

LAB_BENCH_2_DATASET_PATH = "EdisonScientific/labbench2"
LAB_BENCH_2_DATASET_REVISION = "27d12d72af24e3f70db8a99df63e567366cbdb80"
LAB_BENCH_2_DATASET_SPLIT = "train"


def record_to_sample(record: dict[str, Any], mode: Mode = "inject") -> Sample | None:
    """Map a raw LAB-Bench 2 record to an Inspect Sample for the given mode.

    Returns ``None`` if the question declares it does not support ``mode``
    (e.g. a file-bearing record with ``mode.retrieve=False`` and ``mode="retrieve"``).
    """
    question = LabBenchQuestion.model_validate(record)

    if not _question_supports_mode(question, mode):
        return None

    metadata: dict[str, Any] = {
        "id": question.id,
        "tag": question.tag,
        "mode": mode,
        "type": record.get("type") or None,
        "sources": record.get("sources") or [],
        "version": question.version,
        "validator_params": parse_validator_params(question.validator_params),
        "answer_regex": question.answer_regex,
    }
    if record.get("difficulty") is not None:
        metadata["difficulty"] = record["difficulty"]

    files: list[Path] = []
    attachments: list[Content] = []
    if question.files:
        files_dir = FileDownloader().fetch(question.files)
        metadata["files_path"] = str(files_dir)
        files = FileDownloader.list_files(files_dir)
        if mode == "file":
            attachments = AttachmentBuilder().build(files)
        elif mode == "retrieve":
            metadata["expected_file_stems"] = [f.stem for f in files]

    question_text = PromptComposer().compose(
        question.question,
        mode=mode,
        files=files,
        prompt_suffix=question.prompt_suffix,
    )

    sample_input: str | list[ChatMessage]
    if attachments:
        sample_input = [
            ChatMessageUser(content=[ContentText(text=question_text), *attachments])
        ]
    else:
        sample_input = question_text

    return Sample(
        input=sample_input,
        target=question.ideal,
        id=create_stable_id(question.tag, mode, question.id, prefix="labbench2"),
        metadata=metadata,
    )


def load_lab_bench_2_dataset(
    tag: str,
    mode: Mode = "inject",
    limit: int | None = None,
) -> Dataset:
    """Load a single LAB-Bench 2 tag, pinned to a fixed dataset revision.

    Args:
        tag: The dataset config to load (e.g. ``"litqa3"``).
        mode: How to deliver question files (``inject`` / ``file`` / ``retrieve``).
            No-op for file-less tags.
        limit: Optional cap on the number of samples loaded.
    """

    def sample_fields(record: dict[str, Any]) -> Sample | list[Sample]:
        sample = record_to_sample(record, mode=mode)
        return [sample] if sample is not None else []

    return hf_dataset(
        path=LAB_BENCH_2_DATASET_PATH,
        name=tag,
        split=LAB_BENCH_2_DATASET_SPLIT,
        revision=LAB_BENCH_2_DATASET_REVISION,
        sample_fields=sample_fields,
        limit=limit,
    )


def _question_supports_mode(question: LabBenchQuestion, mode: Mode) -> bool:
    if question.files:
        return bool(getattr(question.mode, mode))
    return True


def parse_validator_params(validator_params: str | None) -> dict[str, Any]:
    if not validator_params:
        return {}
    try:
        parsed = json.loads(validator_params)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(validator_params)
    if not isinstance(parsed, dict):
        raise ValueError("validator_params must parse to a dictionary")
    return cast(dict[str, Any], parsed)
