"""Scorers for the LAB-Bench 2 evaluation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from inspect_ai.model import GenerateConfig, get_model
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState

DEFAULT_GRADER_MODEL = "anthropic/claude-sonnet-4-5"
GRADER_ROLE = "grader"

JUDGE_VERDICT_CORRECT = "correct"
JUDGE_VERDICT_INCORRECT = "incorrect"
JUDGE_VERDICT_UNSURE = "unsure"
# Excluding ``=`` from the separator stops the pattern from matching code-like
# grader output such as ``result = "correct"`` (an assignment, not a verdict).
_GRADE_PATTERN = re.compile(
    r"\bresult\b[^A-Za-z=]*(correct|incorrect|unsure)\b",
    re.IGNORECASE,
)

# The recall prompt (unlike the semantic and exact-match prompts) does not ask
# the model for a parseable verdict line, so we append one carrying the
# ``result:`` marker that ``parse_judge_verdict`` reads.
VERDICT_FORMAT_SUFFIX = (
    "\n\nAfter your analysis, end your response with a final line in exactly "
    "this form:\n\nresult: <correct|incorrect|unsure>"
)


def _judge_score(prompt_template: str) -> Scorer:
    """Build a judge that grades an answer against the reference via the template."""

    async def score(state: TaskState, target: Target) -> Score:
        answer = state.output.completion.strip()
        if not answer:
            return Score(
                value=INCORRECT, answer="", explanation="No answer was produced."
            )

        grader = get_model(
            role=GRADER_ROLE,
            default=DEFAULT_GRADER_MODEL,
            config=GenerateConfig(temperature=0.0),
        )

        prompt = prompt_template.format(
            question=state.input_text,
            correct_answer=target.text,
            answer=answer,
        )
        result = await grader.generate(prompt)
        verdict = parse_judge_verdict(result.completion)
        value = CORRECT if verdict == JUDGE_VERDICT_CORRECT else INCORRECT
        return Score(
            value=value,
            answer=answer,
            explanation=result.completion,
            metadata={"verdict": verdict},
        )

    return score


@scorer(metrics=[accuracy(), stderr()])
def semantic_judge_scorer() -> Scorer:
    """Grade an open-ended answer against the reference using a judge model."""
    from evals.prompts import STRUCTURED_EVALUATION_PROMPT

    return _judge_score(STRUCTURED_EVALUATION_PROMPT)


@scorer(metrics=[accuracy(), stderr()])
def recall_judge_scorer() -> Scorer:
    """Grade a dbqa2 answer by recall of the expected values (data-access bench)."""
    from evals.prompts import STRUCTURED_EVALUATION_PROMPT_DATA_ACCESS_BENCH_RECALL

    return _judge_score(
        STRUCTURED_EVALUATION_PROMPT_DATA_ACCESS_BENCH_RECALL + VERDICT_FORMAT_SUFFIX
    )


@scorer(metrics=[accuracy(), stderr()])
def exact_match_judge_scorer() -> Scorer:
    """Grade a figure/table/supplement answer by exact numeric match."""
    from evals.prompts import STRUCTURED_EVALUATION_PROMPT_EXACT_MATCH

    return _judge_score(STRUCTURED_EVALUATION_PROMPT_EXACT_MATCH)


@scorer(metrics=[accuracy(), stderr()])
def cloning_scorer() -> Scorer:
    """Score CloningQA answers using labbench2's cloning reward pipeline.

    Validates cloning protocols through 4 sequential stages:
    1. Format validation — protocol can be parsed
    2. Execution — protocol runs successfully
    3. Similarity — output matches reference sequence (threshold: 0.95)
    4. Digest — restriction enzyme fragments match

    Requires Go 1.21+ on the host for PCR simulation scoring.
    """
    from evals.utils import resolve_file_path
    from labbench2.cloning.rewards import cloning_reward

    async def score(state: TaskState, target: Target) -> Score:
        metadata = state.metadata or {}
        files_path_str = metadata.get("files_path")
        question_id = cast(str | None, metadata.get("id"))

        if not files_path_str or not question_id:
            return Score(
                value=INCORRECT,
                explanation="Cloning evaluation requires files_path and id metadata.",
            )

        ground_truth_filename = f"{question_id}_assembled.fa"
        ground_truth_path = resolve_file_path(ground_truth_filename, None)
        if ground_truth_path is None:
            return Score(
                value=INCORRECT,
                explanation=f"Ground truth file not found: {ground_truth_filename}",
            )

        score_value, reason = await cloning_reward(
            answer=state.output.completion,
            base_dir=Path(files_path_str),
            reference_path=ground_truth_path,
            validator_params=cast(
                dict[str, Any], metadata.get("validator_params") or {}
            ),
        )

        return Score(
            value=CORRECT if score_value >= 1.0 else INCORRECT,
            explanation=reason,
            metadata={"cloning_score": score_value},
        )

    return score


SCORERS_BY_TAG = {
    "cloning": cloning_scorer,
    "dbqa2": recall_judge_scorer,
    "figqa2": exact_match_judge_scorer,
    "figqa2-img": exact_match_judge_scorer,
    "figqa2-pdf": exact_match_judge_scorer,
    "litqa3": semantic_judge_scorer,
    "patentqa": semantic_judge_scorer,
    "protocolqa2": semantic_judge_scorer,
    "sourcequality": semantic_judge_scorer,
    "suppqa2": exact_match_judge_scorer,
    "tableqa2": exact_match_judge_scorer,
    "tableqa2-img": exact_match_judge_scorer,
    "tableqa2-pdf": exact_match_judge_scorer,
    "trialqa": semantic_judge_scorer,
}


def scorer_for_tag(tag: str) -> Scorer:
    """Return the scorer for a tag, or raise if the tag is not yet implemented."""
    factory = SCORERS_BY_TAG.get(tag)
    if factory is None:
        raise NotImplementedError(
            f"No scorer implemented for tag={tag!r}; "
            f"supported tags: {sorted(SCORERS_BY_TAG)}."
        )
    return factory()


def parse_judge_verdict(text: str) -> str | None:
    """Return the judge's verdict, or None if no verdict line is present.

    When multiple verdict lines appear (e.g. the rubric words echoed earlier in
    the reasoning), the last match is taken as the final verdict.
    """
    matches = _GRADE_PATTERN.findall(text or "")
    if not matches:
        return None
    return str(matches[-1]).lower()
