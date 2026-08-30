# LAB-Bench 2 cloning verifier faults (Addgene subset)

These notes travel with the Harbor taskset. They are about the **host
scorer**, not about whether a molecular biologist would accept the
construct.

The Harbor tasks bake `edlib` into the image and score with cloning
simulator v2 / exact circular similarity ≥ 0.95. That matches the
production Inspect scorer (`cloning_scorer` → `cloning_reward_v2`).
It does **not** use verifier v3 constraint mode.

## Host scoring hole (fixed here, still a lab-bench-2 issue)

`sequence_similarity_v2` imports `edlib` inside the distance functions.
If the **host** Python that Inspect uses to score does not have the
`lab_bench_2` extra, a finished protocol raises
`ModuleNotFoundError: edlib` and the sample is recorded as an error,
not as a pass or fail.

Soul Max on this 55-pack: the three iGABASnFR samples (Addgene 112159
and both 112168 maps) completed 15–26 sandbox tool calls, then died on
missing host edlib. Rescoring the same answers with edlib installed
gave similarity **0.999** on all three. Those are not model failures.

Harbor tests install edlib in the environment image so this hole cannot
recur on DataVendor. The Inspect eval still needs
`uv sync --extra lab_bench_2` on the scoring host.

## Exact-circle 0.95 is not a construct-family scorer

The hidden answer is one FASTA in `validation/<id>_assembled.fa`.
Rotation and reverse-complement are allowed. Extra bases, a sibling
plasmid, a different EGFP allele, or a slightly longer homology flank
are fails even when the biology is a reasonable CDS swap.

Verifier v3 (`ConstructSpec`, synonymous protein match, copy counts)
exists in `src/lab_bench_2/cloning_simulators/` and is **not** wired
into `cloning_scorer`. These Harbor tasks keep v2 so scores stay
comparable to the Soul Max run.

Consequences observed on Soul Max (10 sequence fails):

| Addgene | Similarity | What the scorer punished |
| ---: | ---: | --- |
| 181752 | 0.606 | Cas9 fusion/wrap; model used a PX plasmid instead |
| 37825 | 0.660 | AAV CAG-GFP; model used sibling reporter 105539 |
| 23007 | 0.747 | Marker swap on pCMV-M1; model used pcDNA3.1-HA |
| 65202 | 0.801 | YTK cassette dest; sibling pYTK001 |
| 83900 | 0.851 | AAV mDlx-GFP; sibling 105539 |
| 42230 | 0.885 | pX330 Cas9; model used PX459 |
| 26973 ×2 | 0.878 | Right maps; extra MCS flanks + different EGFP donor |
| 48138 | 0.938 | PX458 origin-wrapping Cas9; **just under 0.95** |

0.938 is a near-miss that a family scorer would likely accept. The
0.95 cutoff is a real cliff.

## Sibling-plasmid / dual-map ambiguity

The prompt says “one of our X plasmids.” The inventory contains every
tracked GBK. Dual maps (26973 6236 vs 6225, 20298, 112168, 62988) are
disambiguated only by a bp-length clause. The scorer still has exactly
one circle. A Gibson of the named cargo into the wrong physical file
is a legitimate cloning design and a fail.

## Empty digest gate

`validator_params` on this pack is `{}`. Stage 4 of `cloning_scorer`
(restriction digest vs expected fragments) never runs. Scoring is
format → execute → circular similarity only.

## PCR 15 bp anneal limit

pydna rejects primers whose 3' footprint is shorter than 15 bp. Soul
Max’s 7266 bp 20298 attempt used a 14 bp reverse primer and got “PCR
no product.” The canonical key uses 18 bp. That is a simulator
constraint, not a wet-lab rule.

## DSL has no product selection

Gibson can enumerate competing circles. The scorer ranks every
top-level product and accepts **any** one at ≥ 0.95. Intermediate
operations must still return exactly one sequence
(`Ambiguous intermediate`). Agents cannot write `product[1]`.

## Wrong-job drafts still pass the exact FASTA

The generator swapped a CDS (often AmpR/CmR/NeoR/StaA) even when the
Addgene catalog job is oligo Golden Gate, a stuffer, or a helper used
as-is. Soul Max solved several of those generated questions:

- pLKO.1 AmpR (10878)
- lentiGuide-Puro AmpR (52963)
- pGGAselect CmR (195714)
- pGGA000 AmpR (48856)
- gRNA_GFP-T1 NeoR (41819)

Those passes measure “can the model do the generated two-fragment
Gibson,” **not** oligo-GG or stuffer skill. Rewrite those prompts
before publishing the number as a method benchmark. See
`MANUAL_REVIEW.md`.

## OpenAI `bio_policy` is not a verifier fault

psPAX2 HIV-1 gag (12260), pMD2.G VSV-G (12259), pCMV-VSV-G (8454),
pCMV-dR8.2 gag (8455) returned provider refusals. 12260 never made a
tool call. The scorer then reports “Format invalid: no protocol tags.”
Unscorable on that provider; the Harbor oracle still has a working key.

## What these Harbor tests actually prove

Each task’s oracle protocol, run with simulator v2 against the hidden
circle, has similarity 1.0. Pytest covers that for all 55 IDs in
`tests/lab_bench_2/test_generated_addgene_subset_questions.py`.
That is necessary for a well-posed task. It is not sufficient for
“the prompt asks the catalog cloning job.”
