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
    "cloning",
    "dbqa2",
    "figqa2",
    "figqa2-img",
    "figqa2-pdf",
    "litqa3",
    "patentqa",
    "protocolqa2",
    "seqqa2",
    "sourcequality",
    "suppqa2",
    "tableqa2",
    "tableqa2-img",
    "tableqa2-pdf",
    "trialqa",
)

EVAL_VERSION = load_version_from_yaml("lab_bench_2")


@task
def lab_bench_2(
    tag: str = "litqa3",
    mode: Mode = "file",
    solver: Solver | None = None,
) -> Task:
    """LAB-Bench 2 evaluation task.

    Args:
        tag: Which LAB-Bench 2 subset to run. Supported tags: ``cloning``,
            ``dbqa2``, ``figqa2`` (and ``figqa2-img`` / ``figqa2-pdf``),
            ``litqa3``, ``patentqa``, ``protocolqa2``, ``seqqa2``,
            ``sourcequality``, ``suppqa2``, ``tableqa2`` (and ``tableqa2-img`` /
            ``tableqa2-pdf``), ``trialqa``.
        mode: How a question's data files are delivered to the model. A no-op
            for tags without files (such as litqa3). Options:

            - ``file``: Files uploaded via API. PDFs/images attached as
              context; other files as document attachments.
            - ``inject``: Text file contents concatenated into the prompt as
              text.
            - ``retrieve``: Only file names/stems are given; prompt instructs
              the agent to retrieve the necessary sequences or data from a
              source of its choosing. File contents are withheld.
        solver: The solver to run. Defaults to ``bare()`` (the benchmark's "bare"
            configuration: a plain single-turn ``generate()``) when not provided.
            Pass any Inspect solver to override, e.g. ``-T solver=bare`` on the CLI.
    """
    if tag not in SUPPORTED_TAGS:
        raise NotImplementedError(
            f"tag={tag!r} is not implemented yet; supported tags: {list(SUPPORTED_TAGS)}."
        )
    return Task(
        dataset=load_lab_bench_2_dataset(tag=tag, mode=mode),
        solver=solver or bare(),
        scorer=scorer_for_tag(tag),
        version=EVAL_VERSION,
    )
