# Agentic-solver runs — `gemini-3.7-flash`

Traces for the runs that motivated the changes in this branch. All are Inspect `.eval`
logs; view them with the built-in viewer, no extra tooling:

```bash
uv run inspect view --log-dir experiments/logs --recursive --port 7575   # http://127.0.0.1:7575
uv run inspect log dump experiments/logs/<file>.eval                     # JSON, for grep/jq
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
