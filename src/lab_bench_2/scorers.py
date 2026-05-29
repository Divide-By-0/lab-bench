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


SCORERS_BY_TAG = {
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
