# LABBench2

LABBench2 evaluates language models and research agents on life-science tasks spanning literature reasoning, database access, figures, tables, protocols, source quality, sequence analysis, cloning, patents, and clinical trials.

<!-- Contributors: Automatically Generated -->
Contributed by [@iphan](https://github.com/iphan)
<!-- /Contributors: Automatically Generated -->

<!-- Usage: Automatically Generated -->
## Usage

First, install dependencies:

```bash
uv sync
```

Then run evaluations:

```bash
uv run inspect eval lab_bench_2/lab_bench_2 --model openai/gpt-5-nano
```

You can also import tasks as Python objects:

```python
from inspect_ai import eval
from lab_bench_2 import lab_bench_2
eval(lab_bench_2)
```

After running evaluations, view logs with:

```bash
uv run inspect view
```

If you don't want to specify `--model` each time, create a `.env` file:

```bash
INSPECT_EVAL_MODEL=anthropic/claude-opus-4-1-20250805
ANTHROPIC_API_KEY=<anthropic-api-key>
```
<!-- /Usage: Automatically Generated -->

<!-- Options: Automatically Generated -->
## Options

You can control a variety of options from the command line. For example:

```bash
uv run inspect eval lab_bench_2/lab_bench_2 --limit 10
uv run inspect eval lab_bench_2/lab_bench_2 --max-connections 10
uv run inspect eval lab_bench_2/lab_bench_2 --temperature 0.5
```

See `uv run inspect eval --help` for all available options.
<!-- /Options: Automatically Generated -->

<!-- Parameters: Automatically Generated -->
## Parameters

### `lab_bench_2`

- `tag` (str): Which LAB-Bench 2 subset to run. Supported tags: ``dbqa2``, ``figqa2`` (and ``figqa2-img`` / ``figqa2-pdf``), ``litqa3``, ``patentqa``, ``protocolqa2``, ``sourcequality``, ``suppqa2``, ``tableqa2`` (and ``tableqa2-img`` / ``tableqa2-pdf``), ``trialqa``. (default: `'litqa3'`)
- `mode` (Mode): How a question's data files are delivered to the model. A no-op for tags without files (such as litqa3). Options: ``file``: Files uploaded via API. PDFs/images attached as context; other files as document attachments., ``inject``: Text file contents concatenated into the prompt as text., ``retrieve``: Only file names/stems are given; prompt instructs the agent to retrieve the necessary sequences or data from a source of its choosing. File contents are withheld. (default: `'inject'`)
- `solver` (Solver | None): The solver to run. Defaults to ``bare()`` (the benchmark's "bare" configuration: a plain single-turn ``generate()``) when not provided. Pass any Inspect solver to override, e.g. ``-T solver=bare`` on the CLI. (default: `None`)
<!-- /Parameters: Automatically Generated -->

## Dataset

This eval uses the public `EdisonScientific/labbench2` dataset on Hugging Face, pinned to a specific commit for reproducibility.

### Supported tags

| Tag             | Samples | File-bearing | `mode` to use          | Notes                          |
| --------------- | ------- | ------------ | ---------------------- |--------------------------------|
| `dbqa2`         | 86      | No           | any (mode is a no-op)  | Database access; recall judge. |
| `figqa2`        | 101     | No           | any (mode is a no-op)  | Figure QA; exact-match judge.  |
| `figqa2-img`    | 101     | Yes          | `file`                 | Figure QA with image files.    |
| `figqa2-pdf`    | 101     | Yes          | `file`                 | Figure QA with PDF files.      |
| `litqa3`        | 168     | No           | any (mode is a no-op)  | Literature reasoning.          |
| `patentqa`      | 121     | No           | any (mode is a no-op)  | Patent comprehension.          |
| `protocolqa2`   | 125     | Yes          | `file`                 | Lab protocols.                 |
| `sourcequality` | 150     | Yes          | `file`                 | Source quality assessment.     |
| `suppqa2`       | 125     | No           | any (mode is a no-op)  | Supplement QA; exact-match.    |
| `tableqa2`      | 100     | No           | any (mode is a no-op)  | Table QA; exact-match judge.   |
| `tableqa2-img`  | 100     | Yes          | `file`                 | Table QA with image files.     |
| `tableqa2-pdf`  | 100     | Yes          | `file`                 | Table QA with PDF files.       |
| `trialqa`       | 120     | No           | any (mode is a no-op)  | Clinical trial QA.             |

For file-bearing tags, the loader filters out questions that don't opt into
the requested `mode` (per each question's `QuestionMode` flags in the HF
data). At the time of writing every file-bearing tag (`protocolqa2`,
`sourcequality`, `figqa2-img`, `figqa2-pdf`, `tableqa2-img`, `tableqa2-pdf`)
opts into `file` only, so passing any other `mode` would load zero samples.
Note that the base `figqa2`, `tableqa2`, and `suppqa2` configs carry no files
(mode is a no-op); the image/PDF variants are the file-bearing ones. The mode
flags live in the dataset and may change — verify by running with the
configuration you intend before drawing conclusions from sample counts.

## Scoring

Answers are graded by an LLM judge. The judge compares the model's answer to
the reference, accepting semantically or numerically equivalent answers, and
returns one of `correct` / `incorrect` / `unsure`; a `correct` verdict scores
1.0 and everything else (including unparseable or empty judgements) scores 0.0.
Reported metrics are `accuracy` and `stderr`.

The judge prompt varies by tag: most tags use the default semantic prompt;
`dbqa2` (database access) uses a recall-based variant that marks an answer
correct when it recovers the expected reference values; and the figure, table,
and supplement tags (`figqa2*`, `tableqa2*`, `suppqa2`) use an exact-match
variant for numeric answers.

The judge model is selected via the `grader` model role and defaults to
`anthropic/claude-sonnet-4-5` at temperature 0. Override it on the command line,
for example:

```bash
uv run inspect eval lab_bench_2/lab_bench_2 \
  --model openai/gpt-5-nano \
  --model-role grader=anthropic/claude-opus-4-1-20250805
```

## Attribution

This evaluation depends on the reference implementation's
[`labbench2`](https://github.com/EdisonScientific/labbench2) package for its
deterministic scientific scoring functions (used by the sequence and cloning
tags). That code is licensed **CC BY-SA 4.0**. We pull it in as a dependency —
pinned to a specific commit in `pyproject.toml` (`[tool.uv.sources]`) — rather
than vendoring (copying) the code into this repository.

## Evaluation Report

TODO: A brief summary of results for your evaluation implementation compared against a standard set of existing results.

## Changelog
