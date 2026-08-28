"""Unscored open-source-discovery pilot for complex cloning system design."""

from __future__ import annotations

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.scorer import Score, Scorer, Target, scorer
from inspect_ai.solver import TaskState

from lab_bench_2.solvers.agent import agentic_web
from lab_bench_2.solvers.registry import WEB_COMPOSE

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "questions.json").read_text())

OUTPUT_REQUIREMENTS = """

Return one clearly named design manifest followed by one separate `<protocol>`
block for each plasmid that must be constructed. Each protocol must be a single
functional expression composed from `pcr`, `gibson`, `goldengate`,
`enzyme_cut`, and `restriction_assemble`. Source filenames in the expressions
must correspond to exact sequence files that you downloaded or that were
supplied with the task. Also report the provenance and SHA-256 checksum of every
downloaded sequence file and give the expected final construct length and
feature order. If a quantitative requirement cannot be supported from public
evidence, state that limitation explicitly rather than fabricating a value.
""".strip()


@scorer(metrics=[])
def exploratory_design_scorer() -> Scorer:
    """Preserve outputs in Inspect without asserting open-world correctness."""

    async def score(state: TaskState, target: Target) -> Score:
        return Score.unscored(
            answer=state.output.completion,
            explanation=(
                "Exploratory open-solution design: the trace and submitted construction "
                "artifacts are preserved for review, but no complete deterministic "
                "verifier is claimed for this pilot."
            ),
            metadata={"review_status": "unverified_open_solution"},
        )

    return score


@task
def cloning_open_design_pilot() -> Task:
    """Run two complex cloning-design questions with OrbStack and web search."""
    samples = [
        Sample(
            id=record["id"],
            input=f"{record['question']}\n\n{OUTPUT_REQUIREMENTS}",
            target="",
            metadata={
                "title": record["title"],
                "files_path": str(ROOT / record["files_directory"]),
                "evaluation_mode": "unscored_open_solution",
            },
        )
        for record in QUESTIONS
    ]
    return Task(
        dataset=MemoryDataset(samples=samples, name="cloning-open-design-pilot-v1"),
        # The CLI run uses a $0.13 pre-warning threshold; the synthetic cost
        # configuration maps $0.20 to the requested 200k novel-token ceiling.
        solver=agentic_web(final_warning_cost_limit=0.2),
        scorer=exploratory_design_scorer(),
        sandbox=("docker", WEB_COMPOSE),
        name="cloning_open_design_pilot",
        version="1.0",
    )
