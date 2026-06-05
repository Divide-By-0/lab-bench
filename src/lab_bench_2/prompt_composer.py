"""Render LAB-Bench 2 question prompts per file-delivery mode."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

Mode = Literal["file", "inject", "retrieve"]

# Copied verbatim from EdisonScientific/labbench2
# https://github.com/EdisonScientific/labbench2/blob/c028ec/evals/loader.py#L91-L101
FILE_REFERENCE_INSTRUCTION = (
    "\n\nIn your answer, refer to files using only their base names (not full paths)."
)
RETRIEVE_INSTRUCTION_TEMPLATE = (
    "\n\nRetrieve the necessary sequences or data from a source of your choosing. "
    "In your answer, refer to the sequences using only the following file names "
    "(not full paths) with any valid extension (e.g., .gb, .fa, .fasta): {file_list}"
)


def compose(
    question_text: str,
    mode: Mode,
    files: list[Path],
    prompt_suffix: str = "",
) -> str:
    """Compose the user-visible question prompt for a given file-delivery mode."""
    rendered = question_text
    if files:
        if mode == "inject":
            rendered += _injected_files_text(files)
        elif mode == "file":
            rendered += FILE_REFERENCE_INSTRUCTION
        elif mode == "retrieve":
            rendered += _retrieval_instruction(files)

    if prompt_suffix:
        rendered += "\n\n" + prompt_suffix

    return rendered


def _injected_files_text(files: list[Path]) -> str:
    from evals.utils import is_text_injectable_format

    chunks = [
        f"## {f.name}\n\n{f.read_text()}" for f in files if is_text_injectable_format(f)
    ]
    if not chunks:
        return ""
    return "\n\nFiles:\n\n" + "\n\n".join(chunks)


def _retrieval_instruction(files: list[Path]) -> str:
    stems = [f.stem for f in files]
    return RETRIEVE_INSTRUCTION_TEMPLATE.format(file_list=", ".join(stems))
