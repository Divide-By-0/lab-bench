"""Scorers for the LAB-Bench 2 evaluation."""

from __future__ import annotations

import re

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
_GRADE_PATTERN = re.compile(
    r"\bresult\b[^A-Za-z]*(correct|incorrect|unsure)\b",
    re.IGNORECASE,
)


@scorer(metrics=[accuracy(), stderr()])
def semantic_judge_scorer() -> Scorer:
    """Grade an open-ended answer against the reference using a judge model."""
    from evals.prompts import STRUCTURED_EVALUATION_PROMPT

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

        prompt = STRUCTURED_EVALUATION_PROMPT.format(
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


SCORERS_BY_TAG = {
    "litqa3": semantic_judge_scorer,
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
