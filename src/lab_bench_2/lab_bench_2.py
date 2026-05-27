"""LAB-Bench 2: a benchmark of biology research tasks (arXiv:2604.09554).

A single parameterized task selects a dataset `tag` and a file-delivery `mode`,
and accepts an optional `solver` (defaulting to the benchmark's "bare"
single-turn `generate()`).
"""

from __future__ import annotations

from inspect_ai import Task, task
from inspect_ai.solver import Solver

from lab_bench_2.dataset import load_lab_bench_2_dataset
from lab_bench_2.prompt_composer import Mode
from lab_bench_2.scorers import scorer_for_tag
from lab_bench_2.solvers import bare
from utils.metadata import load_version_from_yaml

SUPPORTED_TAGS = (
    "litqa3",
    "patentqa",
    "protocolqa2",
    "sourcequality",
    "trialqa",
)

EVAL_VERSION = load_version_from_yaml("lab_bench_2")


@task
def lab_bench_2(
    tag: str = "litqa3",
    mode: Mode = "inject",
    shuffle: bool = False,
    solver: Solver | None = None,
) -> Task:
    """LAB-Bench 2 evaluation task.

    Args:
        tag: Which LAB-Bench 2 subset to run. Supported tags: ``litqa3``,
            ``patentqa``, ``protocolqa2``, ``sourcequality``, ``trialqa``.
        mode: How a question's data files are delivered to the model. A no-op
            for tags without files (such as litqa3). Options:

            - ``file``: Files uploaded via API. PDFs/images attached as
              context; other files as document attachments.
            - ``inject``: Text file contents concatenated into the prompt as
              text.
            - ``retrieve``: Only file names/stems are given; prompt instructs
              the agent to retrieve the necessary sequences or data from a
              source of its choosing. File contents are withheld.
        shuffle: Whether to shuffle the dataset on load. Useful with ``--limit``
            for a randomized sub-sample across runs.
        solver: The solver to run. Defaults to ``bare()`` (the benchmark's "bare"
            configuration: a plain single-turn ``generate()``) when not provided.
            Pass any Inspect solver to override, e.g. ``-T solver=bare`` on the CLI.
    """
    if tag not in SUPPORTED_TAGS:
        raise NotImplementedError(
            f"tag={tag!r} is not implemented yet; supported tags: {list(SUPPORTED_TAGS)}."
        )
    return Task(
        dataset=load_lab_bench_2_dataset(tag=tag, mode=mode, shuffle=shuffle),
        solver=solver or bare(),
        scorer=scorer_for_tag(tag),
        version=EVAL_VERSION,
    )
