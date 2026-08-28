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

CLONING_FILE_REFERENCE_GUIDANCE = """Cloning protocol filename syntax:
- The canonical form for a sequence file is a bare filename, such as `vector.gbk`.
- A quoted filename such as `"vector.gbk"` is also accepted when it exactly matches an available task file.
- Primer sequences and enzyme names remain quoted strings.

Example: `gibson(pcr(vector.gbk, "ACGT...", "TGCA..."), pcr("insert.gbk", "GCTA...", "TAGC..."))`"""

CLONING_PROTOCOL_SUFFIX = """You need to express the final protocol as a single functional expression in an equation-like syntax inside <protocol> </protocol> tags.

You may use the following operations. All operations return a FASTA or GenBank file. All input files must contain a single sequence (no multi-FASTA or multi-GenBank files). Inputs must be FASTA/GenBank files, plain text files (.txt), or outputs of other operations.

1. pcr(sequence, forward_primer, reverse_primer)
   - sequence: FASTA/GenBank file or nested operation
   - forward_primer: a literal string or a .txt file containing the primer
   - reverse_primer: a literal string or a .txt file containing the primer

2. gibson(seq1, seq2, ..., seqN)
   - seq1..seqN: sequences (FASTA/GenBank, .txt, or nested operations)

3. goldengate(seq1, seq2, ..., seqN, enzymes='Enz1,Enz2,...')
   - seq1..seqN: sequences (FASTA/GenBank, .txt, or nested operations)
   - enzymes: a literal string of enzyme names separated by commas or a .txt file containing them

4. restriction_assemble(fragment1, fragment2)
   - fragment1: sequence (FASTA/GenBank/.txt) or nested operation
   - fragment2: sequence (FASTA/GenBank/.txt) or nested operation

5. enzyme_cut(sequence, "EnzymeName")
   - sequence: FASTA/GenBank file or nested operation
   - EnzymeName: a literal string with the enzyme name (e.g., "NdeI", "XhoI", "BamHI")
   - Returns the largest fragment from the digest (typically the backbone or main insert)

All operations may be nested arbitrarily.""" + (
    "\n\n" + CLONING_FILE_REFERENCE_GUIDANCE
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
