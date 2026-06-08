# LABBench Evaluations

Inspect AI implementations of the **LABBench** family of biology-research
benchmarks, built for the [inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals)
registry.

This repository is the home for LABBench evaluations: it currently ships
[`lab_bench_2`](src/lab_bench_2/README.md) (LAB-Bench 2), and is structured to
host future versions and related LABBench evals alongside it, each as its own
self-contained evaluation under `src/`.

## Evaluations

| Eval | Description | Docs |
| ---- | ----------- | ---- |
| `lab_bench_2` | LAB-Bench 2 ([arXiv:2604.09554](https://arxiv.org/abs/2604.09554)) — language models and research agents on life-science tasks spanning literature reasoning, database access, figures, tables, protocols, source quality, sequence analysis, cloning, patents, and clinical trials. | [src/lab_bench_2/README.md](src/lab_bench_2/README.md) |

## Quickstart

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install dependencies
uv sync --dev --all-extras

# Run an evaluation (see the eval's README for tags, modes, and solvers)
uv run inspect eval lab_bench_2 --model openai/gpt-5-nano

# View logs
uv run inspect view

# Run tests
uv run pytest
```

If you don't want to pass `--model` each time, set it in a `.env` file:

```bash
INSPECT_EVAL_MODEL=anthropic/claude-opus-4-1-20250805
ANTHROPIC_API_KEY=<anthropic-api-key>
```

See each evaluation's README for its parameters, dataset details, and scoring —
for `lab_bench_2`, [src/lab_bench_2/README.md](src/lab_bench_2/README.md).

## Repository structure

Each evaluation lives in its own directory under `src/` and is registered via
entry points in `pyproject.toml`; its tests live in `tests/<eval_name>/`.

```text
src/
  lab_bench_2/          # LAB-Bench 2 evaluation (task, dataset, scorers, solvers)
  utils/                # Shared helpers
tests/
  lab_bench_2/          # Tests for lab_bench_2
```

## Development

Always run tooling through `uv` (not bare `python`/`pytest`/`pip`):

```bash
uv sync                       # install/sync dependencies
uv run pytest                 # run tests
uv run ruff check && uv run ruff format --check
uv run mypy src tests         # type-check source and tests
make check                    # full check suite (ruff, mypy, build, autolint, ...)
```

## CI workflows

### Standard checks (always active)

- **Checks** (`checks.yml`) — runs ruff, mypy, POSIX code check,
  unlisted-eval check, package build, autolint, generated-docs check,
  and large-file scan on every push and PR.
- **Markdown Lint** (`markdown-lint.yml`) — lints markdown files on PRs
- **PR Template Check** (`pr-template-check.yml`) — verifies PR body
  contains the required checklist
- **Sync Template** (`sync-template.yml`) — weekly sync of managed files
  from the upstream template (skips inactive repos)
- **Sync Upstream** (`sync-upstream.yml`) — weekly sync of managed files
  from [inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals)

## Template & managed files

This repository is built on the
[inspect-eval-template](https://github.com/ArcadiaImpact/inspect-eval-template).
Some files (CI workflows, quality tooling, Claude Code skills, shared docs) are
**template-managed** and kept up to date via an automated sync; your evaluation
code, tests, and READMEs are yours. See [MANAGED_FILES.md](MANAGED_FILES.md) for
the split and [AGENTS.md](AGENTS.md) for agent-assisted workflows and the
available skills.

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) — development setup, testing, and
  submission guidelines.
- [BEST_PRACTICES.md](BEST_PRACTICES.md) — evaluation design best practices
  (synced from `inspect_evals`).
- [EVALUATION_CHECKLIST.md](EVALUATION_CHECKLIST.md) — quality checklist used
  when reviewing evaluations (synced from `inspect_evals`).
- [AUTOMATED_CHECKS.md](AUTOMATED_CHECKS.md) — what `tools/run_autolint.py`
  checks, and how to suppress individual rules.
- [TASK_VERSIONING.md](TASK_VERSIONING.md) — when to bump an eval's `task`
  version.
- [AGENTS.md](AGENTS.md) — repo-wide tips for coding agents and pointers to
  the skills above.
- [MANAGED_FILES.md](MANAGED_FILES.md) — which files in this repo are
  template-managed vs. user-owned, and how the sync preserves customizations.
- [CLAUDE.md](CLAUDE.md) — project-level instructions Claude Code reads on
  every session in this repo.
