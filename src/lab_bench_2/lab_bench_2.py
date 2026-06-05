"""LAB-Bench 2: a benchmark of biology research tasks (arXiv:2604.09554).

A single parameterized task selects one or more dataset `tags` and a
file-delivery `mode`, and accepts an optional `solver` (defaulting to the
benchmark's "bare" single-turn `generate()`).
"""

from __future__ import annotations

from inspect_ai import Task, task
from inspect_ai.dataset import Dataset
from inspect_ai.scorer import Scorer

from lab_bench_2.dataset import load_lab_bench_2_dataset, load_multi_tags_dataset
from lab_bench_2.prompt_composer import Mode
from lab_bench_2.scorers import multi_tags_scorer, scorer_for_tag
from lab_bench_2.solvers import SolverType, sandbox_for_solver, solver_for_type
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
    tags: str | list[str] | None = None,
    mode: Mode = "file",
    solver: SolverType = "bare",
) -> Task:
    """LAB-Bench 2 evaluation task.

    Args:
        tags: Which LAB-Bench 2 subset(s) to run. Supported tags: ``cloning``,
            ``dbqa2``, ``figqa2`` (and ``figqa2-img`` / ``figqa2-pdf``),
            ``litqa3``, ``patentqa``, ``protocolqa2``, ``seqqa2``,
            ``sourcequality``, ``suppqa2``, ``tableqa2`` (and ``tableqa2-img`` /
            ``tableqa2-pdf``), ``trialqa``.

            - A single tag (e.g. ``"litqa3"``) runs just that subset and reports
              one accuracy.
            - A list (e.g. ``["litqa3", "cloning"]``) or ``None`` (the default,
              meaning every tag) runs the subsets together at the chosen
              ``mode``, reporting accuracy per tag plus an overall aggregate.
        mode: How a question's data files are delivered to the model. A no-op
            for tags without files (such as litqa3). Options:

            - ``file``: Files uploaded via API. PDFs/images attached as
              context; other files as document attachments.
            - ``inject``: Text file contents concatenated into the prompt as
              text.
            - ``retrieve``: Only file names/stems are given; prompt instructs
              the agent to retrieve the necessary sequences or data from a
              source of its choosing. File contents are withheld.
        solver: The solver to run. Options:

            - ``bare``: a plain single-turn `generate()`.
            - ``tools``: the server-side agentic configuration. The model
            is given provider-native, **server-side** tools — WebSearch and
            CodeExecution — and runs Inspect's tool-use loop.
            - ``agentic``: the client-side agentic configuration. The model is
            given ``python``/``bash`` (and, with an external provider
            key, ``web_search``) tools in a Docker sandbox.
    """
    dataset: Dataset
    scorer: Scorer
    if isinstance(tags, str):
        _ensure_supported([tags])
        dataset = load_lab_bench_2_dataset(tag=tags, mode=mode)
        scorer = scorer_for_tag(tags)
    else:
        if tags is None:
            selected = list(SUPPORTED_TAGS)
        else:
            selected = list(tags)
            _ensure_supported(selected)
        dataset = load_multi_tags_dataset(selected, mode=mode)
        scorer = multi_tags_scorer()
    return Task(
        dataset=dataset,
        solver=solver_for_type(solver),
        scorer=scorer,
        sandbox=sandbox_for_solver(solver),
        version=EVAL_VERSION,
    )


def _ensure_supported(tags: list[str]) -> None:
    """Validate a non-empty selection of supported tags, or raise."""
    if not tags:
        raise ValueError(
            "tags must contain at least one tag (or be None to run every tag)."
        )
    unknown = [tag for tag in tags if tag not in SUPPORTED_TAGS]
    if unknown:
        raise NotImplementedError(
            f"Unsupported tag(s): {unknown}; supported tags: {list(SUPPORTED_TAGS)}."
        )
