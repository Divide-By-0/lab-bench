"""Dataset loading for the LAB-Bench 2 evaluation.

Questions live in a single (gated) HuggingFace dataset broken up by tags.
File-bearing tags can be served in three modes — ``inject`` / ``file`` /
``retrieve`` — orchestrated here via the ``file_downloader``,
``attachment_builder``, and ``prompt_composer`` collaborators.
"""

from __future__ import annotations

import ast
import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from evals.models import LabBenchQuestion
from inspect_ai.dataset import Dataset, MemoryDataset, Sample, hf_dataset
from inspect_ai.model import ChatMessage, ChatMessageUser, Content, ContentText

from lab_bench_2 import attachment_builder, file_downloader, prompt_composer
from lab_bench_2.prompt_composer import Mode
from utils.sample_ids import create_stable_id

LAB_BENCH_2_DATASET_PATH = "EdisonScientific/labbench2"
LAB_BENCH_2_DATASET_REVISION = "27d12d72af24e3f70db8a99df63e567366cbdb80"
LAB_BENCH_2_DATASET_SPLIT = "train"

# How many tags to spell out in a multi-tag dataset name before eliding the
# rest, to keep the name readable when many tags run together.
MAX_TAGS_IN_DATASET_NAME = 5

logger = logging.getLogger(__name__)


def record_to_sample(record: dict[str, Any], mode: Mode = "inject") -> Sample:
    """Map a raw LAB-Bench 2 record to an Inspect Sample for the given mode.

    Precondition: the record's question supports ``mode``. The loader filters
    unsupported records via ``_question_supports_mode`` before calling this.
    """
    question = LabBenchQuestion.model_validate(record)

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
        files_dir = file_downloader.fetch(question.files)
        metadata["files_path"] = str(files_dir)
        files = file_downloader.list_files(files_dir)
        if mode == "file":
            attachments = attachment_builder.build(files)
        elif mode == "retrieve":
            metadata["expected_file_stems"] = [f.stem for f in files]

    question_text = prompt_composer.compose(
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
) -> Dataset:
    """Load a single LAB-Bench 2 tag, pinned to a fixed dataset revision.

    Args:
        tag: The dataset config to load (e.g. ``"litqa3"``).
        mode: How to deliver question files (``inject`` / ``file`` / ``retrieve``).
            No-op for file-less tags.
    """

    def to_samples(record: dict[str, Any]) -> list[Sample]:
        question = LabBenchQuestion.model_validate(record)
        if not _question_supports_mode(question, mode):
            logger.info(
                f"Skipping question id {question.id}: does not support mode {mode!r}"
            )
            return []
        return [record_to_sample(record, mode=mode)]

    return hf_dataset(
        path=LAB_BENCH_2_DATASET_PATH,
        name=tag,
        split=LAB_BENCH_2_DATASET_SPLIT,
        revision=LAB_BENCH_2_DATASET_REVISION,
        sample_fields=to_samples,
    )


def load_multi_tags_dataset(tags: Sequence[str], mode: Mode = "file") -> Dataset:
    """Load and concatenate tags' samples into one mixed-tag dataset.

    Each tag is loaded at the given ``mode`` via
    :func:`load_lab_bench_2_dataset` (which drops samples a tag can't serve in
    that mode), and the samples are concatenated. Each sample keeps its ``tag``
    metadata, so a grouped scorer can report per-tag and overall.
    """
    samples = [sample for tag in tags for sample in load_lab_bench_2_dataset(tag, mode)]
    return MemoryDataset(samples=samples, name=_multi_tags_dataset_name(tags))


def _multi_tags_dataset_name(tags: Sequence[str]) -> str:
    """Build a ``MemoryDataset`` name from the selected tags.

    Tags are sorted for stability. When more than ``MAX_TAGS_IN_DATASET_NAME``
    tags run together, the surplus is elided as ``+N-more`` so the name stays
    short regardless of how many tags are selected.
    """
    ordered = sorted(tags)
    if len(ordered) <= MAX_TAGS_IN_DATASET_NAME:
        body = "+".join(ordered)
    else:
        shown = "+".join(ordered[:MAX_TAGS_IN_DATASET_NAME])
        body = f"{shown}+{len(ordered) - MAX_TAGS_IN_DATASET_NAME}-more"
    return f"lab_bench_2_{body}"


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
