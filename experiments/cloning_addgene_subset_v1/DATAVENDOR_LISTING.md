# DataVendor listing copy

Title (≤60): `Addgene CloningQA 55 Harbor tasks`

One-liner (≤100): `55 Addgene CDS-swap cloning tasks. Exact-circle Harbor tests; documented scorer holes.`

## Description

Harbor-format CloningQA pack: 55 two-fragment CDS swaps over a shared
inventory of 55 tracked Addgene GenBank maps plus a 16-enzyme stock.

Each task is a Harbor directory (`instruction.md`, `task.toml`,
`environment/Dockerfile`, hidden `tests/reference.fa`, oracle
`solution/protocol.txt`). The agent writes `/app/protocol.txt` as a
single `<protocol>` DSL expression (PCR / Gibson / Golden Gate /
restriction). The verifier runs lab-bench-2 cloning simulator v2
(pydna + edlib) and passes only if a circular product matches the
hidden FASTA at similarity ≥ 0.95.

**Local tests that pass before upload**

- `tests/lab_bench_2/test_generated_addgene_subset_questions.py` —
  all 55 canonical protocols reproduce the hidden circle at
  similarity 1.0 (pydna / simulator v2).
- `tests/lab_bench_2/test_cloning_simulators_v2.py` — PCR, Gibson
  competing products, Golden Gate sticky ends, edlib circular
  similarity, candidate-aware reward.
- `tests/lab_bench_2/test_cloning_verifier_v3.py` and
  `test_cloning_constraints_v3.py` — v3 family scorer, **not** used
  by these tasks.
- `tests/lab_bench_2/test_scorers.py` — Inspect `cloning_scorer`
  wiring, including the missing-reference and fail paths.
- `tests/lab_bench_2/test_harbor_addgene_pack.py` — Harbor layout,
  oracle reward 1.0, wrong protocol reward 0.0.

Draft PR with traces: https://github.com/Divide-By-0/lab-bench/pull/3

**Soul Max (gpt-5.6-sol, reasoning max / Inspect xhigh, 100k novel
tokens, agentic file mode):** 41/55 after edlib rescore (10 wrong
sequence, 4 OpenAI bio_policy on HIV-1 gag / VSV-G helpers). First
three iGABASnFR samples were host `edlib` errors, then 0.999 on
rescore — not model fails.

**Gemini 3.7 Flash (reasoning high, 1M novel intended, all 55
queued):** 28/32 scored (accuracy 0.875) before Google AI Studio
monthly spend cap (`429 RESOURCE_EXHAUSTED`). Four sequence fails
match Sol’s sibling-plasmid misses (181752 0.611, 23007 0.747,
26973-6225 PCR, 37825 0.660). Recovers Sol/2.5 Pro misses 12260
(HIV-1 gag) and 42230 (pX330; Sol used PX459). 23 tasks unrun —
not model fails. Trace:
`experiments/traces/gemini37flash_addgene_subset_55tasks_1M_high_cancelled32.eval`.

Scientist-facing annotations: `MODEL_GAPS.md`. Compact view of
where scored models fall short:

| Addgene | Job | Sol | Gemini 2.5 Pro | Gemini 3.7 Flash |
| ---: | --- | --- | --- | --- |
| 12259 pMD2.G | VSV-G→mCherry | bio_policy | P 0.993 | P 1.000 |
| 12260 psPAX2 | HIV-1 gag→tdTomato | bio_policy | F | **P 1.000** |
| 181752 MMLVgag-Cas9 | Cas9→EYFP | F 0.606 | F | F 0.611 |
| 20298 DIO 7266 | ChR2→EGFP | F PCR | P 0.952 | P 1.000 |
| 23007 pCMV-M1 | NeoR→tdTomato | F 0.747 | F | F 0.747 |
| 26973 6225 | ChR2→EGFP | F 0.878 | F | F PCR |
| 26973 6236 | ChR2→EGFP | F 0.878 | P 1.000 | P 1.000 |
| 37825 CAG-GFP | EGFP→mCherry | F 0.660 | F | F 0.660 |
| 42230 pX330 | Cas9→EGFP | F 0.885 | F | **P 1.000** |
| 48138 PX458 | Cas9→EGFP | F 0.938 | F | unrun (spend cap) |
| 65202 pYTK095 | sfGFP→mCherry | F 0.801 | F | unrun (spend cap) |
| 83900 mDlx-GFP | EGFP→mCherry | F 0.851 | F | unrun (spend cap) |
| 8454 pCMV-VSV-G | VSV-G→tdTomato | bio_policy | P 0.993 | unrun (spend cap) |
| 8455 pCMV-dR8.2 | HIV-1 gag→EYFP | bio_policy | F 0.67 | unrun (spend cap) |

**Do not read the score as Golden Gate / stuffer skill.** Several
wrong-job drafts (pLKO AmpR, lentiGuide AmpR, pGGAselect CmR, gRNA
NeoR) still pass the exact FASTA because the generated job is a CDS
swap. Catalog method is often oligo GG. See MANUAL_REVIEW.md.

**Verifier faults shipped with the pack** (full note in the notes
zip): host edlib hole; exact-circle cliff (PX458 Cas9 at 0.938);
sibling-plasmid scorer; empty digest gate; pydna 15 bp PCR limit;
DSL has no product selection; v3 constraint mode unused.

Addgene source URLs are in each question. Maps are depositor
GenBank files used as benchmark inputs, not a redistribution of
Addgene’s catalog UI.
