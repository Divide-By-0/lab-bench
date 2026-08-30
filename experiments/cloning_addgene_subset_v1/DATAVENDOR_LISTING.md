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
