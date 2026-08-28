# Agentic-solver runs — `gemini-3.7-flash`

Traces for the runs that motivated the changes in this branch. All are Inspect `.eval`
logs; view them with the built-in viewer, no extra tooling:

```bash
uv run inspect view --log-dir experiments/traces --recursive --port 7575   # http://127.0.0.1:7575
uv run inspect log dump experiments/traces/<file>.eval                     # JSON, for grep/jq
```

Common config unless noted: `-T tags=<tag> -T mode=retrieve -T solver=agentic`,
`--model google/gemini-3.7-flash --model-role grader=google/gemini-3.7-flash`,
`--reasoning-effort high --epochs 1`.

| log | what | result |
|---|---|---|
| `seqqa2_6tasks_2epochs.eval` | 6 never-solved seqqa2 design tasks, 2 epochs | **11/12** |
| `seqqa2_primer_design_rpoC.eval` | single task, first sandbox pass | **PASS** |
| `cloning_11tasks.eval` | all gibson + golden-gate + hardest restriction-ligation | 3/11 |
| `cloning_2tasks_2epochs.eval` | 2 never-solved cloning tasks | 0/4 |
| `cloning_sorcs2_after_session_fix.eval` | `fb8fc27d` after the session/docs fixes | fail |
| `cloning_6tasks_rerun_6M.eval` | the 6 truncated tasks re-run at **6M** ⚠️ | 2/6 |
| `gpt56sol_smoke_2tasks_hinted.eval` | `gpt-5.6-sol` max effort, original prompts, 2 tasks | 0/2 |
| `gpt56sol_8tasks_method_blind.eval` | `gpt-5.6-sol` max effort, **method hint stripped**, 8 tasks | **1/8** |
| `gpt56sol_cloning_pilot_3tasks.eval` | three local Addgene 181752 × 13770 replacement tasks | **1/3** official |
| `gpt56sol_cloning_pilot_3tasks_reviewed.eval` | same answers rescored under 2-B quoted-filename normalization | **3/3**; all exact assemblies |
| `gpt56sol_cloning_inventory_hard_6tasks.eval` | six hard mixed Addgene/iGEM inventory tasks, model-selected methods | **4/6** |
| `gpt56sol_cloning_inventory_hard_6tasks_functional_v3_reviewed.eval` | same six answers, pydna simulator pipeline and functional verifier v3-B | **6/6**; 2 verdicts changed |
| `gpt56sol_8tasks_method_blind_constraint_v3_reviewed.eval` | same method-blind answers, constraint verifier v3-B | **8/8** |
| `gpt56sol_cloning_pilot_3tasks_constraint_v3_reviewed.eval` | same pilot answers, constraint verifier v3-B | **3/3** |
| `gpt56sol_smoke_2tasks_hinted_constraint_v3_reviewed.eval` | same smoke answers, constraint verifier v3-B | **2/2** |

## Cloning simulator v2 rescoring

The `*_simulator_v2_reviewed.eval` logs preserve the model answers from the runs
above and rescore them with LAB-Bench 2 version `2-A`. They are not new model
generations. Each log preserves the old verdict and explanation in score metadata
and adds an Inspect sequence-comparison event.

| Source run | Original | Simulator v2 | Changed verdicts |
| --- | ---: | ---: | ---: |
| `cloning_11tasks` | 3/11 | **6/11** | 3 |
| `cloning_2tasks_2epochs` | 0/4 | **0/4** | 0 |
| `cloning_6tasks_rerun_6M` | 2/6 | **3/6** | 1 |
| `cloning_sorcs2_after_session_fix` | 0/1 | **0/1** | 0 |
| `gpt56sol_8tasks_method_blind` | 1/8 | **6/8** | 5 |
| `gpt56sol_smoke_2tasks_hinted` | 0/2 | **2/2** | 2 |

Across these 32 stored submissions, 11 verdicts change from incorrect to correct.
The method-blind GPT-5.6-sol run includes a reference-matching Gibson result that
is candidate 3 of 14 under v2, directly demonstrating why product 1 cannot be
treated as authoritative. The unchanged PCR-based SORCS2 answer now produces an
amplicon but remains incorrect because its best final sequence similarity is
0.839761, below the 0.95 threshold.

> ⚠️ `cloning_6tasks_rerun_6M.eval` was run at `--token-limit 6000000`, above the 2M
> ceiling the rest of this work uses. **Five of its six samples exceeded 2M**, including
> both passes, so its results are not valid at the 2M configuration. Kept for reference,
> excluded from headline numbers.

## Cloning constraint verifier v3-B rescoring

The `*_constraint_v3_reviewed.eval` logs are a separate shadow rescore of the
recorded GPT-5.6-sol answers. They use scorer-owned construct constraints as the
correctness definition rather than requiring one reference sequence or one
pLannotate feature list. Each task specifies required functional modules, copy
ranges, and only biologically meaningful order/fusion relationships. Unspecified
tag positions and extra benign annotations do not affect the result. Direct
input-derived DNA/protein evidence takes priority; pLannotate is a deterministic
fallback and does not require reviewer adjudication.

| Source run | Original scorer | Constraint v3-B | Changed verdicts |
| --- | ---: | ---: | ---: |
| `gpt56sol_8tasks_method_blind` | 1/8 | **8/8** | 7 |
| `gpt56sol_cloning_pilot_3tasks` | 1/3 | **3/3** | 2 |
| `gpt56sol_smoke_2tasks_hinted` | 0/2 | **2/2** | 2 |

This is 13/13 stored samples across 11 unique tasks; the two smoke tasks duplicate
tasks in the method-blind run and must not be pooled as independent observations.
All 13 explanations enumerate observed versus expected module copies and explicit
relationship checks. Whole-reference similarity and the sequence-difference
visualization remain diagnostic rather than overriding the constraint verdict.

## What these traces show

**The sandbox solves the seqqa2 design tasks outright.** `gibson_primers` had **0 passes in
119 graded attempts** across every published model and mode — never solved by anything — and
went 6/6 here on the three longest genes in the set. `primer_design` went 6/7. Those subtypes
were not hard; they were strangled by the environment (77% and 71% of published attempts never
reached the validator at all).

**Cloning is a different story, but the measurement is not clean yet.** Of the 8 failures in
`cloning_11tasks.eval`, **6 hit the token limit** rather than answering. Their novel-token
counts (392k–548k) are all *below* the 616k that `5cf2e092` spent while passing — they were cut
off on transcript length, not on work done. `--token-limit` counts cache reads, and that run
burned 14.6M cache against 5.0M novel. Only `0a4f4de7` (digest mismatch) and `21e4def0`
(accuracy) are genuine failures so far.

## Why the changes in this branch

Measured across 691 tool calls in 24 agentic samples:

| finding | change |
|---|---|
| 94 of 125 tool errors were `NameError` from state loss | `python_session` (persistent namespace) |
| agents read pydna's source and web-searched for its API | pydoc baked into `/opt/docs` |
| 1 sample spent 6 calls on DuckDuckGo, then hit the limit | web search scoped in the prompt |
| container had outbound network; dataset `ideal` answers are public on HF | `network_mode: "none"` |
| `mode=file` + `agentic` attached files already in the sandbox | attachments skipped for agentic |

Network use was rare — 6 calls in 691 (0.9%), all in one sample — so `network_mode: none` is
cheap insurance against the answer-key path rather than a fix for a widespread problem.

## Patched tasks — not comparable to published numbers

`tools/patch_broken_cloning_tasks.py` repairs three tasks that were unsolvable for environment
reasons. Report them separately from the rest.

| task | defect | fix | result |
|---|---|---|---|
| `61e4b666` | insert template is an 11-record FASTA the loader rejects (upstream #16) | keep record 0, `ENST00000612748.1` | **PASS** — 0/27 published |
| `31d22b22` | reference omits the BlastR cassette the prompt requires (upstream #32) | splice the 454 bp BSD region in after the IRES | truncated |
| `a4bf037c` | filename contains a space; the DSL cannot express it (upstream #34) | drop the browser `(1)` suffix, keep the Addgene ids | truncated |

Record 0 is provably the right template for `61e4b666`: it appears in the reference at offset
2868 with exactly one mismatch, position 295 C→A — which is the C295A mutation the prompt asks
for. That patch alone turned a task nothing had ever solved into a pass.


## gpt-5.6-sol vs gemini-3.7-flash on cloning

Config: `--reasoning-effort max`, `--cost-limit 0.1` against
`experiments/novel_token_costs.yaml` (input+output at $1/M, cache at $0, so the limit is
**100,000 novel tokens**), `--max-tokens 64000`, `--message-limit 60`.

**Every one of the 8 ran to completion — no truncations.** These are the first clean
verdicts on tasks Gemini could never finish.

| | gemini-3.7-flash | gpt-5.6-sol |
|---|---|---|
| novel tokens per cloning sample | 347k – 661k | **22k – 76k** (mean 46k) |
| tool calls per sample | 46 – 59 | 10 – 31 |
| samples truncated | 6 of 11 | **0 of 8** |

Roughly **10x cheaper**, and it finishes what Gemini could not.

### Stripping the method hint changed nothing

`-T strip_method_hint=true` removes every phrase naming the assembly method. All 7
failures still selected the **correct** method from the biology alone:

| task | true method | chose | correct |
|---|---|---|---|
| `0a4f4de7` `dff28bd4` `fb8fc27d` `bc918101` | gibson | `gibson(` | yes |
| `21e4def0` `3a6704ab` `31d22b22` | golden-gate | `goldengate(` | yes |

So the hint was doing no work, and the failures are downstream — junctions, overhangs,
fragment boundaries — not strategy selection. Caveat: the tasks are only *method-weaker*,
not method-blind. `BsaI-MCS` and `BsmBI` remain in the golden-gate prompts and are
unmistakable Type IIS tells.

The original scorer's single pass, `a4bf037c`, is the odd one: it used
`restriction_assemble` on a task whose reference is a Gibson assembly, and still
matched at >=95%. Constraint v3-B accepts all 8 completed products because they
satisfy their task-specific functional constraints; the assembly route itself is
not scored when it produces an acceptable plasmid.

### Duplicate guard

`tools/check_run_guards.py` flagged `0a4f4de7` and `3a6704ab` as appearing in both the
smoke and the 8-task run. They have two results each (hinted and method-blind) and must
not be pooled. Both failed under the original scorer and pass under constraint v3-B in
both conditions, so the duplicate-handling conclusion does not change.
