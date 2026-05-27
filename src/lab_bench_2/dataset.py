"""Dataset loading for the LAB-Bench 2 evaluation.

Questions live in a single (gated) HuggingFace dataset broken up by tags.
File-bearing tags can be served in three modes — ``inject`` (file text
concatenated into the prompt), ``file`` (files attached as API content), or
``retrieve`` (only file stems given, agent must fetch). Mode dispatch and
attachment building are ported from EdisonScientific/labbench2's
``evals/loader.py``.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any, Literal, cast

from evals.models import LabBenchQuestion
from evals.utils import (
    GCS_BUCKET,
    download_question_files,
    is_text_injectable_format,
)
from inspect_ai.dataset import Dataset, Sample, hf_dataset
from inspect_ai.model import (
    ChatMessage,
    ChatMessageUser,
    Content,
    ContentDocument,
    ContentImage,
    ContentText,
)

from utils.sample_ids import create_stable_id

Mode = Literal["file", "inject", "retrieve"]

LAB_BENCH_2_DATASET_PATH = "EdisonScientific/labbench2"
LAB_BENCH_2_DATASET_REVISION = "27d12d72af24e3f70db8a99df63e567366cbdb80"
LAB_BENCH_2_DATASET_SPLIT = "train"

FILE_REFERENCE_INSTRUCTION_TEMPLATE = (
    "\n\nAttached files: {file_list}\n\n"
    "In your answer, refer to files using only these exact base names "
    "(not full paths)."
)
RETRIEVE_INSTRUCTION_TEMPLATE = (
    "\n\nUse the provided retrieval tools to inspect the mirrored source files "
    "for this task when you need sequences or supporting data. In your answer, "
    "refer to the sequences using only the following file names (not full paths) "
    "with any valid extension (e.g., .gb, .fa, .fasta): {file_list}"
)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_DOCUMENT_EXTENSIONS = {
    ".fa",
    ".fasta",
    ".gb",
    ".gbk",
    ".gbff",
    ".genbank",
    ".json",
    ".jsonl",
    ".md",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
}
PDF_EXTENSIONS = {".pdf"}
MAX_IMAGE_ATTACHMENT_BYTES = 3_900_000
IMAGE_ATTACHMENT_CACHE_DIR = (
    Path.home() / ".cache" / "inspect_evals" / "lab_bench_2" / "images"
)


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

    question_text = question.question
    attachments: list[Content] = []

    if question.files:
        files_path = load_question_files(question.files)
        metadata["files_path"] = str(files_path)
        question_files = sorted_question_files(files_path)

        if mode == "inject":
            injectable_files = [
                f"## {file_path.name}\n\n{file_path.read_text()}"
                for file_path in question_files
                if is_text_injectable_format(file_path)
            ]
            if injectable_files:
                question_text += "\n\nFiles:\n\n" + "\n\n".join(injectable_files)
        elif mode == "file":
            attachments = build_file_attachments(files_path)
            question_text += file_reference_instruction(
                [file_path.name for file_path in question_files]
            )
        elif mode == "retrieve":
            file_stems = [file_path.stem for file_path in question_files]
            metadata["expected_file_stems"] = file_stems
            question_text += RETRIEVE_INSTRUCTION_TEMPLATE.format(
                file_list=", ".join(file_stems)
            )

    if question.prompt_suffix:
        question_text += "\n\n" + question.prompt_suffix

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
        return cast(dict[str, Any], json.loads(validator_params))
    except json.JSONDecodeError:
        parsed = ast.literal_eval(validator_params)
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
        raise ValueError("validator_params must parse to a dictionary")


def load_question_files(gcs_prefix: str) -> Path:
    files_path = cast(
        Path,
        download_question_files(bucket_name=GCS_BUCKET, gcs_prefix=gcs_prefix),
    )
    if not files_path.exists() or not any(files_path.iterdir()):
        raise RuntimeError(
            f"Question expects files at '{gcs_prefix}' but none were downloaded."
        )
    return files_path


def sorted_question_files(files_path: Path) -> list[Path]:
    return sorted(path for path in files_path.iterdir() if path.is_file())


def file_reference_instruction(file_names: list[str]) -> str:
    return FILE_REFERENCE_INSTRUCTION_TEMPLATE.format(file_list=", ".join(file_names))


def build_file_attachments(files_path: Path) -> list[Content]:
    attachments: list[Content] = []
    for file_path in sorted_question_files(files_path):
        if file_path.suffix.lower() in IMAGE_EXTENSIONS:
            attachments.append(
                ContentImage(image=str(prepare_image_for_attachment(file_path)))
            )
        else:
            mime_type = document_mime_type(file_path)
            attachments.append(
                ContentDocument(
                    document=document_attachment_contents(file_path, mime_type),
                    filename=file_path.name,
                    mime_type=mime_type,
                )
            )
    return attachments


def document_mime_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "application/pdf"
    if suffix == ".csv":
        return "text/csv"
    if suffix == ".tsv":
        return "text/tab-separated-values"
    if suffix in {".json", ".jsonl"}:
        return "application/json"
    if suffix in TEXT_DOCUMENT_EXTENSIONS:
        return "text/plain"

    guessed_mime_type, _ = mimetypes.guess_type(file_path.name)
    if guessed_mime_type and (
        guessed_mime_type.startswith("text/")
        or guessed_mime_type in {"application/json", "application/xml", "text/xml"}
    ):
        return guessed_mime_type

    return "text/plain"


def document_attachment_contents(file_path: Path, mime_type: str) -> str:
    if mime_type == "application/pdf":
        return str(file_path)

    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def prepare_image_for_attachment(file_path: Path) -> Path:
    if file_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
        return file_path

    from PIL import Image

    IMAGE_ATTACHMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()[:12]
    cached_base = (
        IMAGE_ATTACHMENT_CACHE_DIR
        / f"{file_path.stem}-{digest}-{file_path.stat().st_size}"
    )
    png_path = cached_base.with_suffix(".png")
    jpg_path = cached_base.with_suffix(".jpg")

    with Image.open(file_path) as source_image:
        image = source_image.copy()

    def resize(image_to_resize: "Image.Image", scale: float) -> "Image.Image":
        if scale == 1.0:
            return image_to_resize.copy()
        width = max(1, int(image_to_resize.width * scale))
        height = max(1, int(image_to_resize.height * scale))
        return image_to_resize.resize((width, height), Image.Resampling.LANCZOS)

    for scale in (1.0, 0.9, 0.8, 0.7, 0.6):
        candidate = resize(image, scale)
        candidate.save(png_path, format="PNG", optimize=True)
        if png_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
            return png_path

    rgb_image = image.convert("RGB")
    for scale in (1.0, 0.9, 0.8, 0.7, 0.6):
        candidate = resize(rgb_image, scale)
        for quality in (90, 80, 70):
            candidate.save(jpg_path, format="JPEG", optimize=True, quality=quality)
            if jpg_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
                return jpg_path

    return jpg_path
