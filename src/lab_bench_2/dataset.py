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
from typing import TYPE_CHECKING, Any, cast

from inspect_ai.dataset import Dataset, MemoryDataset, Sample, hf_dataset
from inspect_ai.model import ChatMessage, ChatMessageUser, Content, ContentText

from lab_bench_2 import attachment_builder, file_downloader, prompt_composer
from lab_bench_2.prompt_composer import Mode
from utils.sample_ids import create_stable_id

if TYPE_CHECKING:
    # ``evals`` ships with the optional ``labbench2`` dependency; import it only
    # for type checking so module load doesn't require the extra (which would
    # break Inspect's entry-point task discovery). Runtime uses import it locally.
    from evals.models import LabBenchQuestion

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
    return _record_to_sample(record, mode=mode)


def _record_to_sample(
    record: dict[str, Any],
    mode: Mode,
    *,
    files_dir: Path | None = None,
    reference_path: Path | None = None,
) -> Sample:
    """Map one record, optionally using local files and a local reference."""
    from evals.models import LabBenchQuestion

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
    if reference_path is not None:
        metadata["reference_path"] = str(reference_path)

    files: list[Path] = []
    attachments: list[Content] = []
    if question.files:
        resolved_files_dir = files_dir or file_downloader.fetch(question.files)
        if not resolved_files_dir.is_dir():
            raise FileNotFoundError(
                f"Question files directory not found: {resolved_files_dir}"
            )
        metadata["files_path"] = str(resolved_files_dir)
        files = file_downloader.list_files(resolved_files_dir)
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


def load_local_cloning_dataset(path: Path | str, mode: Mode = "file") -> Dataset:
    """Load self-contained local CloningQA records and their references.

    The JSONL records use the same schema as the Hugging Face dataset, but each
    ``files`` value is resolved relative to the JSONL's parent directory. A
    reference must exist at ``validation/<id>_assembled.fa``.
    """
    from evals.models import LabBenchQuestion

    dataset_path = Path(path).resolve()
    root = dataset_path.parent
    samples: list[Sample] = []
    for line_number, line in enumerate(dataset_path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        question = LabBenchQuestion.model_validate(record)
        if question.tag != "cloning":
            raise ValueError(
                f"Local dataset line {line_number} has tag {question.tag!r}; "
                "only cloning is supported."
            )
        if not question.files:
            raise ValueError(
                f"Local cloning dataset line {line_number} has no files directory."
            )
        if not _question_supports_mode(question, mode):
            continue
        files_dir = root / question.files
        reference_path = root / "validation" / f"{question.id}_assembled.fa"
        if not reference_path.is_file():
            raise FileNotFoundError(f"Cloning reference not found: {reference_path}")
        samples.append(
            _record_to_sample(
                record,
                mode,
                files_dir=files_dir,
                reference_path=reference_path,
            )
        )
    if not samples:
        raise ValueError(f"Local cloning dataset has no samples for mode {mode!r}")
    return MemoryDataset(samples=samples, name=f"local-cloning-{dataset_path.stem}")


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
        from evals.models import LabBenchQuestion

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
