# GPT-5.6 Sol results — Addgene subset 55

Run date: 2026-08-29. Model `openai/gpt-5.6-sol`, reasoning effort `max`
(Inspect sent `xhigh`), agentic file-mode solver, Docker sandbox.

Novel-token ceiling: 100,000 per sample, enforced as `--cost-limit 0.1`
against `experiments/novel_token_costs.yaml` (input+output $1/M, cache $0).
Also `--max-tokens 64000 --message-limit 60 --token-limit 3000000 --max-connections 3 --epochs 1 --no-fail-on-error`.

Key: `devin-normal-OPENAI_API_KEY` from the normal project Keychain (account `normal`).

Trace: `experiments/traces/gpt56sol_addgene_subset_55tasks.eval`

## Headline

Raw Inspect log (edlib missing on three early scores): **38 C / 10 I / 7 error**.

After rescoring that same log with edlib installed
(`gpt56sol_addgene_subset_55tasks_edlib_rescored.eval`): the three iGABASnFR
samples all pass (similarity 0.999). Inspect accuracy **0.745 = 41/55**.

| | n |
| --- | ---: |
| Pass (exact circular match ≥ 0.95), after edlib rescore | 41 |
| Fail (protocol ran, sequence mismatch) | 10 |
| Error, OpenAI `bio_policy` | 4 |
| Total | 55 |

Graded accuracy among samples that produced a score: **41/51 (80.4%)**.
Including bio-policy errors as non-passes: **41/55 (74.5%)**.

No sample exceeded 100k novel tokens (range 12k–68k among those that generated; mean ~40k). The post-run guard flagged only `labbench2_d8062a8f` (psPAX2 HIV-1 gag) for zero sandbox tool calls — that sample was refused on the first model request.

## Failures (exact-reference scorer)

| Addgene | Payload → donor | Best similarity | Note |
| ---: | --- | ---: | --- |
| 181752 | Cas9 → EYFP | 0.606 | Cas9 wrap/fusion on pCMV-MMLVgag |
| 37825 | EGFP → mCherry | 0.660 | AAV CAG-GFP |
| 23007 | NeoR/KanR → tdTomato | 0.747 | Marker swap on pCMV-M1; flagged as wrong category |
| 65202 | sfGFP → mCherry | 0.801 | YTK cassette acceptor dropout |
| 83900 | EGFP → mCherry | 0.851 | AAV mDlx-GFP; ITR gotcha plasmid |
| 42230 | Cas9 → EGFP | 0.885 | pX330; prompt named Golden Gate, key is Gibson |
| 26973 | ChR2 → EGFP | 0.878 / 0.878 | **Both** dual maps failed similarly |
| 20298 | ChR2 → EGFP | PCR fail | 7266 bp map; other 20298 map passed |
| 48138 | Cas9 → EGFP | 0.938 | PX458 origin-wrapping Cas9; just under 0.95 |

## Errors (not cloning verdicts)

| Addgene | Kind | What happened |
| ---: | --- | --- |
| 112159, 112168 ×2 | `edlib` missing, then pass | Model finished (15–26 tool calls). Host scorer lacked edlib. Rescore: all three pass at similarity 0.999. |
| 12260 | `bio_policy` | HIV-1 gag on psPAX2. No tool calls. |
| 12259 | `bio_policy` | VSV-G on pMD2.G after some analysis. |
| 8454 | `bio_policy` | VSV-G on pCMV-VSV-G. |
| 8455 | `bio_policy` | HIV-1 gag on pCMV-dR8.2 dvpr. |

OpenAI flagged packaging-helper questions that name HIV-1 gag or VSV-G. Unscorable on this provider.

## What passed that we expected to be messy

lentiGuide AmpR, pLKO AmpR, pGGAselect CmR, pGGA000 AmpR, gRNA_GFP NeoR, unlabeled dCas9/Cre, L4440 T7 MCS, FLEX tdTomato, DIO mCherry, both PX459 maps, lentiCRISPR v1/v2 Cas9, SaCas9, plant Cas9.

## Reproduction

```bash
OPENAI_API_KEY="$(security find-generic-password -a normal -s devin-normal-OPENAI_API_KEY -w | tr -d '\r\n')" \
  .venv/bin/inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_addgene_subset_v1/questions.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max \
  --cost-limit 0.1 --model-cost-config experiments/novel_token_costs.yaml \
  --max-tokens 64000 --message-limit 60 --token-limit 3000000 \
  --max-connections 3 --epochs 1 --no-fail-on-error \
  --log-dir experiments/traces
```

```bash
.venv/bin/python tools/check_run_guards.py \
  experiments/traces/gpt56sol_addgene_subset_55tasks.eval \
  --budget 100000 --metric novel
```
