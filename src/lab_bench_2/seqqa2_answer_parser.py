"""Answer extraction for the SeqQA2 scorer.

Wraps upstream ``extract_answer`` with whitespace-normalization fallbacks so a
line-wrapped or space-separated sequence answer still matches the question's
answer regex.
"""

from __future__ import annotations

import re
from typing import cast

ANSWER_BLOCK_RE = re.compile(r"<answer>(.*?)</answer>", re.IGNORECASE | re.DOTALL)
ASCII_WHITESPACE_RE = re.compile(r"[ \t\n\r\f\v]+")
NAMED_GROUP_RE = re.compile(r"\(\?P<[^>]+>")
IUPAC_NUCLEOTIDE_CHARS = frozenset("ACGTRYSWKMBDHVNacgtryswkmbdhvnUu")
REGEX_SYNTAX_CHARS = frozenset(r"[](){}?+*^$|,:\\-")


def _is_nucleotide_only_answer_regex(answer_regex: str) -> bool:
    """Return True if the regex's literal characters are all IUPAC nucleotides.

    Used to decide whether stripping *all* internal whitespace from an answer is
    a safe normalization (true for raw sequences, false for prose answers).
    """
    without_group_names = NAMED_GROUP_RE.sub("(", answer_regex)
    remaining = "".join(
        char
        for char in without_group_names
        if char not in REGEX_SYNTAX_CHARS and not char.isspace()
    )
    return bool(remaining) and set(remaining) <= IUPAC_NUCLEOTIDE_CHARS


def _normalized_answer_attempts(answer_text: str, answer_regex: str) -> list[str]:
    """Whitespace-normalized variants of an answer to retry regex extraction.

    Always tries collapsing runs of whitespace to a single space; for
    nucleotide-only regexes, also tries removing internal whitespace entirely.
    """
    attempts = [ASCII_WHITESPACE_RE.sub(" ", answer_text).strip()]
    if _is_nucleotide_only_answer_regex(answer_regex):
        nucleotide_attempt = ASCII_WHITESPACE_RE.sub("", answer_text).strip()
        if nucleotide_attempt not in attempts:
            attempts.append(nucleotide_attempt)
    return attempts


def extract(completion: str, answer_regex: str | None) -> dict[str, str] | None:
    """Extract seqqa2 answer params via the question's answer regex.

    Delegates to upstream ``extract_answer`` first; on failure, retries against
    whitespace-normalized variants of the ``<answer>`` block to tolerate
    line-wrapped or spaced sequence answers. Returns ``None`` if nothing matches.
    """
    from evals.evaluators import extract_answer

    extracted = extract_answer(completion, answer_regex)
    if extracted is not None:
        return cast(dict[str, str], extracted)

    if not answer_regex:
        return None

    answer_match = ANSWER_BLOCK_RE.search(completion)
    if answer_match is None:
        answer_text = completion
        prefix = "<answer>"
        suffix = "</answer>"
    else:
        answer_text = answer_match.group(1)
        prefix = completion[: answer_match.start()] + "<answer>"
        suffix = "</answer>" + completion[answer_match.end() :]

    for normalized_answer in _normalized_answer_attempts(answer_text, answer_regex):
        if not normalized_answer:
            continue
        normalized_completion = f"{prefix}{normalized_answer}{suffix}"
        extracted = extract_answer(normalized_completion, answer_regex)
        if extracted is not None:
            return cast(dict[str, str], extracted)

    return None
