# LABBench2

LABBench2 evaluates language models and research agents on life-science tasks spanning literature reasoning, database access, figures, tables, protocols, source quality, sequence analysis, cloning, patents, and clinical trials.

<!-- Contributors: Automatically Generated -->
Contributed by [@iphan](https://github.com/iphan), [@ItsTania](https://github.com/ItsTania), [@lewtun](https://github.com/lewtun), [@Sunishchal](https://github.com/Sunishchal)
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

### Additional Usage Notes

The `cloning` tag scorer runs a PCR (Polymerase Chain Reaction) simulation using
a small Go binary that labbench2 compiles on first use, so a
Go toolchain (1.21+) must be available on the host the first time you score
`cloning`; the compiled binary is then cached inside the installed package and
reused. To install Go: `brew install go` (macOS), `sudo apt install golang-go` (Linux),
or <https://go.dev/dl/>.

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

- `tags` (str | list[str] | None): Which LAB-Bench 2 subset(s) to run. Supported tags: ``cloning``, ``dbqa2``, ``figqa2`` (and ``figqa2-img`` / ``figqa2-pdf``), ``litqa3``, ``patentqa``, ``protocolqa2``, ``seqqa2``, ``sourcequality``, ``suppqa2``, ``tableqa2`` (and ``tableqa2-img`` / ``tableqa2-pdf``), ``trialqa``., A single tag (e.g. ``"litqa3"``) runs just that subset and reports one accuracy., A list (e.g. ``["litqa3", "cloning"]``) or ``None`` (the default, meaning every tag) runs the subsets together at the chosen ``mode``, reporting accuracy per tag plus an overall aggregate. (default: `None`)
- `mode` (Mode): How a question's data files are delivered to the model. A no-op for tags without files (such as litqa3). Options: ``file``: Files uploaded via API. PDFs/images attached as context; other files as document attachments., ``inject``: Text file contents concatenated into the prompt as text., ``retrieve``: Only file names/stems are given; prompt instructs the agent to retrieve the necessary sequences or data from a source of its choosing. File contents are withheld. (default: `'file'`)
- `solver` (SolverType): The solver to run. Options: ``bare``: a plain single-turn `generate()`., ``tools``: the server-side agentic configuration. The model is given provider-native, **server-side** tools — WebSearch and CodeExecution — and runs Inspect's tool-use loop., ``agentic``: the client-side agentic configuration. The model is given ``python``/``bash`` (and, with an external provider key, ``web_search``) tools in a Docker sandbox. (default: `'bare'`)
<!-- /Parameters: Automatically Generated -->

### Reference run configs

The benchmark's two headline configurations — `bare` and `tools` at high
reasoning effort — are checked in as Inspect [run configs](https://inspect.aisi.org.uk/task-configuration.html#run-config)
under [`run_configs/`](run_configs/), one file per (solver × mode) combination.
Each pins the solver, the file-delivery `mode`, the mode's tag subset, and the
generation config taken from the reference implementation
(`max_tokens: 64000` and `timeout: 3600` — see
`evals/llm_configs.py` in [`EdisonScientific/labbench2`](https://github.com/EdisonScientific/labbench2) —
plus `reasoning_effort: high` for the tools configs). The `file` and `inject`
configs also pin the default `grader` model role; the `retrieve` configs omit it
because their tags (`cloning`, `seqqa2`) are scored deterministically. The model
under test is left to the CLI:

```bash
# bare solver, inject-mode tags
uv run inspect eval --run-config src/lab_bench_2/run_configs/bare_inject.yaml \
  --model openai/gpt-5-nano

# tools solver at high reasoning, file-mode tags
uv run inspect eval --run-config src/lab_bench_2/run_configs/tools_high_file.yaml \
  --model anthropic/claude-opus-4-1-20250805
```

| Config file                 | Solver | Mode       | Tags                                                                                            |
| --------------------------- | ------ | ---------- |-------------------------------------------------------------------------------------------------|
| `bare_file.yaml`            | bare   | `file`     | cloning, figqa2-img, figqa2-pdf, protocolqa2, seqqa2, sourcequality, tableqa2-img, tableqa2-pdf |
| `bare_inject.yaml`          | bare   | `inject`   | cloning, dbqa2, figqa2, litqa3, patentqa, seqqa2, suppqa2, tableqa2, trialqa                    |
| `bare_retrieve.yaml`        | bare   | `retrieve` | cloning, seqqa2                                                                                 |
| `tools_high_file.yaml`      | tools  | `file`     | (same as `bare_file.yaml`)                                                                      |
| `tools_high_inject.yaml`    | tools  | `inject`   | (same as `bare_inject.yaml`)                                                                    |
| `tools_high_retrieve.yaml`  | tools  | `retrieve` | (same as `bare_retrieve.yaml`)                                                                  |

## Solvers

The benchmark can run each model in three configurations, selected via the `solver`
parameter:

- **`bare`** (default): a plain single-turn `generate()` — no tools.
- **`tools`**: the server-side agentic configuration. The model is given provider-native,
  **server-side** tools — WebSearch and CodeExecution — and runs Inspect's
  tool-use loop, which drives each provider's server-side tool round-trips. The
  internal provider is auto-selected for the active model, so no external search
  keys or local sandbox are required.
- **`agentic`**: the client-side agentic configuration. The model is given **sandboxed**
  `python` / `bash` tools (plus `web_search` when an external provider key is set —
  `TAVILY_API_KEY`, `EXA_API_KEY`, or `GOOGLE_CSE_API_KEY`) inside a **Docker sandbox**,
  and must call `submit()` to answer. A question's data files are copied into the sandbox
  working directory. The initial docker image build should take ~ 2 minutes on a standard personal computer.

Reasoning effort is set with Inspect's built-in `--reasoning-effort` flag (it
applies to the model under test only, not the grader). The paper's "tools,high"
case is:

```bash
uv run inspect eval lab_bench_2/lab_bench_2 -T tags=litqa3 -T solver=tools --reasoning-effort high
```

### WebFetch is omitted

The reference benchmark's tool set also includes a **WebFetch** tool (Anthropic
`web_fetch`, Google `url_context`) for retrieving the full content of a specific
URL. It is **omitted here because Inspect has no native `web_fetch` wrapper** in
any release, and no mechanism to pass a raw provider-native tool through. The
capability exists at the providers — it simply is not surfaced through Inspect.
Revisit if Inspect adds a web-fetch tool.

One consequence: under `solver=tools`, `mode="retrieve"` (where the model is given
only file names and must obtain the data itself) is degraded, since the model
cannot reliably fetch a specific record's full content — prefer `inject` or `file`.
This limitation does not apply to `solver=agentic`: the question's files are copied
into the sandbox, so `mode="retrieve"` (filenames in the prompt, contents on disk) is
the recommended pairing there.

## Dataset

This eval uses the public `EdisonScientific/labbench2` dataset on Hugging Face, pinned to a specific commit for reproducibility.

### Supported tags

| Tag             | Samples | File-bearing | `mode` to use          | Notes                                  |
| --------------- | ------- | ------------ | ---------------------- |----------------------------------------|
| `cloning`       | 14      | Yes          | any (all modes)        | Cloning protocols; reward-scored.      |
| `dbqa2`         | 86      | No           | any (mode is a no-op)  | Database access; recall judge.         |
| `figqa2`        | 101     | No           | any (mode is a no-op)  | Figure QA; exact-match judge.          |
| `figqa2-img`    | 101     | Yes          | `file`                 | Figure QA with image files.            |
| `figqa2-pdf`    | 101     | Yes          | `file`                 | Figure QA with PDF files.              |
| `litqa3`        | 168     | No           | any (mode is a no-op)  | Literature reasoning.                  |
| `patentqa`      | 121     | No           | any (mode is a no-op)  | Patent comprehension.                  |
| `protocolqa2`   | 125     | Yes          | `file`                 | Lab protocols.                         |
| `seqqa2`        | 400     | Yes          | `file` / `inject`      | Sequence QA; deterministic validators. |
| `sourcequality` | 150     | Yes          | `file`                 | Source quality assessment.             |
| `suppqa2`       | 125     | No           | any (mode is a no-op)  | Supplement QA; exact-match.            |
| `tableqa2`      | 100     | No           | any (mode is a no-op)  | Table QA; exact-match judge.           |
| `tableqa2-img`  | 100     | Yes          | `file`                 | Table QA with image files.             |
| `tableqa2-pdf`  | 100     | Yes          | `file`                 | Table QA with PDF files.               |
| `trialqa`       | 120     | No           | any (mode is a no-op)  | Clinical trial QA.                     |

For file-bearing tags, the loader filters out questions that don't opt into
the requested `mode` (per each question's `QuestionMode` flags in the HF
data).

#### Selecting one, several, or all tags

The `tags` parameter accepts a single tag, a list of tags, or `None`:

```bash
# A single tag — one accuracy, scored by that tag's scorer
uv run inspect eval lab_bench_2 -T tags=litqa3 --model openai/gpt-5-nano

# Several tags — Inspect splits the comma-separated value into a list
uv run inspect eval lab_bench_2 -T tags=litqa3,cloning --model openai/gpt-5-nano

# Every tag — omit -T tags (defaults to None)
uv run inspect eval lab_bench_2 --model openai/gpt-5-nano
```

When more than one tag runs together (a list or the `None` default), accuracy and
stderr are reported **per tag and overall**: the scorer dispatches each sample to
its tag's scorer and aggregates with Inspect's `grouped()` metric, keyed on each
sample's `tag` metadata, which adds an overall `all` row alongside the per-tag
rows.

#### Relationship between the tag and mode parameters

Tags describe groups of samples/questions whilst mode describes how data files are uploaded.
Not every sample is compatible with each mode of data uploading; if incompatible they are not loaded into the eval.
Each sample in the dataset contains flags for compatible modes - this may change and sample counts
can be verified by running with the configuration you intend before drawing conclusions from sample counts.

For most tags, those that use files requires the `file` mode. For example;

`uv run inspect eval lab_bench_2 -T tags=sourcequality -T mode=retrieve`

 Will result in no samples being loaded in. This is also true for tags `protocolqa2`,`sourcequality`,`figqa2-img`,`figqa2-pdf`,`tableqa2-img`,`tableqa2-pdf`.

Note that the base `figqa2`, `tableqa2`, and `suppqa2` tags have no files (mode is a no-op). Their image/PDF variants do have files and are impacted by the above.

`seqqa2` is the exception: all of its samples are compatible with `file` and `inject`, while only a
subset of this tag can be used with `retrieve` (so `mode="retrieve"` loads fewer samples).

## Scoring

There are different scoring methods for the tags.
Some tags are scored deterministically (see `cloning` and `seqqa2`) but most are graded by an LLM judge.

### LLM judge scorers

The judge compares the solver's answer to the reference, accepting semantically
or numerically equivalent answers, and returns one of `correct` / `incorrect` / `unsure`;
a `correct` verdict scores 1.0 and everything else (including unparseable or empty judgements)
scores 0.0. Reported metrics are `accuracy` and `stderr`.

The judge requests **structured output** (a typed `result` / `rationale`
schema), so the verdict is read from a typed field rather than scraped from
prose. If the grader's provider doesn't support structured output, it falls back
to parsing a `result:` line from the response.

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

### Deterministic scorers

The `cloning` tag is not graded by an LLM judge: it is scored deterministically
by labbench2's reward pipeline, which parses the submitted protocol, executes it
(including Polymerase Chain Reaction simulation), and compares the result to the
reference assembly via sequence-similarity and restriction-digest checks.
PCR simulation requires that Go be available on the host. Without Go,
protocol execution fails gracefully: PCR-based samples score 0.0 with an explanatory
reason rather than crashing the run.

The `seqqa2` tag is also scored deterministically. A
per-question validator (selected by the question's `type`) checks the answer
extracted via that question's `answer_regex`; extraction tolerates line-wrapped
or whitespace-separated sequences.

## Attribution

This evaluation depends on the reference implementation's
[`labbench2`](https://github.com/EdisonScientific/labbench2) package for its
deterministic scientific scoring functions (used by the sequence and cloning
tags). That code is licensed **CC BY-SA 4.0**. We pull it in as a dependency —
pinned to a specific commit in `pyproject.toml` (`[tool.uv.sources]`) — rather
than vendoring (copying) the code into this repository.

## Evaluation Report

Model under test: **GPT-5.2** (`gpt-5.2`). The **Paper acc (GPT-5.2)** column is
the reference accuracy from the original LAB-Bench 2 reports
([arXiv:2604.09554](https://arxiv.org/abs/2604.09554)), matched per case to the
nearest paper run configuration. The **Accuracy**, **Stderr**, and **Time**
columns are from our runs.

| tag         | mode     | solver  | Paper config matched |     N |  Paper acc | Accuracy | Stderr |     Time |
| ----------- | -------- | ------- | -------------------- |------:|-----------:|---------:|-------:|---------:|
| litqa3      | N/A      | tools   | `@tools,high`        |  168† |      0.815 |    0.799 |  0.032 |    9m59s |
| dbqa2       | N/A      | bare    | `bare`               |    86 |      0.070 |    0.058 |  0.025 |    1m51s |
| cloning     | inject   | tools   | `@tools,high`        |   14§ |      0.286 |    0.286 |  0.125 | 1h41m39s |
| figqa2-img  | file     | bare    | `bare`               |   101 |      0.564 |    0.525 |  0.050 |    1m10s |
| seqqa2      | retrieve | bare    | `bare`               |   200 |      0.095 |    0.115 |  0.023 |    2m31s |
| protocolqa2 | file     | agentic | `@tools,high`\*      |  125‡ |      0.416 |    0.447 |  0.045 |    6m18s |

\* The paper has no client-side-sandbox (`agentic`) config; `@tools,high`
(server-side tools) is the closest augmented baseline.

† `litqa3`: 9 of the 168 grader calls were blocked by the content filter (see
the refusals note below) and excluded as unscored; the reported accuracy and
stderr are over the 159 scored samples.

‡ `protocolqa2`: 2 of the 125 grader calls were blocked by the content filter
(see the refusals note below) and excluded as unscored; the reported
accuracy and stderr are over the 123 scored samples.

§ `cloning`: its low score is partly a refusal artifact, not pure capability.
The model under test declined ~40% of this small 14-question set on biosecurity
grounds (refusing to give actionable cloning protocols), plus 1 OpenAI API-level
content-filter block.

### Notes

- Every GPT-5.2 run tracks its matched paper reference within stderr (≤ ~1
  stderr).
- Grader refusals are excluded from the results. The LLM judge
  (`claude-sonnet-4-5`) is occasionally blocked by Anthropic's content filter on
  biosecurity-adjacent questions, which returns an empty response with
  `stop_reason=content_filter`. The sample is retried up to 3× and, if still
  blocked, marked **unscored** (`verdict_source="refusal"`) rather than counted
  wrong.
- LLM-judge tags (`litqa3`, `dbqa2`, `figqa2-img`, `protocolqa2`) are graded by
  `claude-sonnet-4-5`; deterministic tags (`seqqa2`, `cloning`) use no grader,
  so they are unaffected by *grader* refusals.

### Reproducibility

- **Model under test:** `openai/gpt-5.2`. **Grader (LLM-judge tags only):**
  `anthropic/claude-sonnet-4-5` — the eval default; deterministic tags
  (`seqqa2`, `cloning`) use no grader.
- **Eval version:** `1-A`. **Dataset:** `EdisonScientific/labbench2`, split
  `train`, pinned to revision `27d12d72af24e3f70db8a99df63e567366cbdb80`.
- **Samples:** each row runs its full set of mode-compatible samples (the `N`
  column); `seqqa2` `retrieve` is the retrieve-compatible subset (~200 of 400).
- **Date:** June 2026.
- **Reasoning effort:** `bare` rows use the model default; the `@tools,high`
  rows (to fill) use `--reasoning-effort high` to match the paper's augmented
  configuration.

Commands (one per row):

```bash
# Bare runs
uv run inspect eval lab_bench_2 -T tags=dbqa2 -T solver=bare --model openai/gpt-5.2
uv run inspect eval lab_bench_2 -T tags=figqa2-img -T mode=file -T solver=bare --model openai/gpt-5.2
uv run inspect eval lab_bench_2 -T tags=seqqa2 -T mode=retrieve -T solver=bare --model openai/gpt-5.2

# @tools,high runs
uv run inspect eval lab_bench_2 -T tags=litqa3 -T solver=tools \
  --model openai/gpt-5.2 --reasoning-effort high
uv run inspect eval lab_bench_2 -T tags=cloning -T mode=inject -T solver=tools \
  --model openai/gpt-5.2 --reasoning-effort high
uv run inspect eval lab_bench_2 -T tags=protocolqa2 -T mode=file -T solver=agentic \
  --model openai/gpt-5.2 --reasoning-effort high
```

## Changelog

### [1-A] - 2026-06-05

- Add the initial implementation of LABBench2, which supports 15 tags, 3 file processing
modes, 5 scorers and 3 solvers
