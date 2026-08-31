# GPT-5.6 Sol OrbStack results

All six base questions were evaluated on 2026-08-28 with the agentic solver in
file mode. Docker used the `orbstack` context. The model was
`openai/gpt-5.6-sol` at maximum reasoning effort.

The run used a 100,000-novel-token ceiling per sample. Inspect enforced this as
`--cost-limit 0.1` with input and output priced at $1 per million tokens and
cache reads priced at zero. The other established run settings were
`--max-tokens 64000`, `--message-limit 60`, `--token-limit 3000000`, three
concurrent connections, and one epoch.

Before the paid run, a mock Inspect evaluation exercised the same OrbStack
sandbox and file-copy solver on the first sample. It confirmed that the model
working directory contained all 46 task files: 12 Addgene plasmids, eight iGEM
carrier plasmids, eight iGEM element records, 16 enzyme stocks, and two inventory
indexes.

## Results

| Question | Inspect sample | Result | Best similarity | Novel tokens | Tool calls |
| --- | --- | ---: | ---: | ---: | ---: |
| TCF/LEF EGFP-P2A-PuroR reporter | `labbench2_2232bca1` | pass | 1.000000 | 43,724 | 15 |
| Lentiviral mCherry with G418 selection | `labbench2_9f412c80` | pass | 0.999396 | 39,137 | 14 |
| Cre-dependent tdTomato-P2A-PuroR reporter | `labbench2_6ba1f4d2` | pass | 0.998904 | 34,013 | 12 |
| Cas9-P2A-mCherry with kanamycin propagation | `labbench2_279127bc` | fail | 0.946678 | 57,939 | 14 |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | `labbench2_efec1039` | fail | 0.744138 | 36,550 | 14 |
| Guide-vector mCherry-P2A-NeoR replacement | `labbench2_15a9c379` | pass | 0.998793 | 45,791 | 17 |

The raw deterministic cloning result is **4/6 (66.7%)**. Both failures produced
one assessable candidate and failed the 0.95 sequence-similarity threshold; no
sample was a refusal, infrastructure error, duplicate, or token-limit failure.

The complete trace is
`experiments/traces/gpt56sol_cloning_inventory_hard_6tasks.eval`. Every sample
contains an Inspect `InfoEvent` with the annotated candidate/reference sequence
comparison and provenance visualization.

## Pydna and functional-verifier review

The raw score above is preserved as the original run result, but it is not the
preferred biological review. The same recorded protocols were re-executed with
`execute_cloning_protocol_v2`, whose PCR, Gibson, Golden Gate, and restriction-
ligation operations use pydna. They were then scored by verifier v3-B with one
scorer-owned functional `ConstructSpec` per question. Whole-reference similarity
is diagnostic rather than a hard gate in this mode.

The reviewed trace records the complete simulator manifest at log and sample
level: molecular engine `pydna`, pydna version `5.5.16`, protocol executor
`execute_cloning_protocol_v2`, verifier version `v3-B`, and
`constraint_mode=true`.

| Question | Raw sequence score | Functional v3-B | Functional finding |
| --- | ---: | ---: | --- |
| TCF/LEF EGFP-P2A-PuroR reporter | pass | pass | All nine modules and three explicit relationships pass. |
| Lentiviral mCherry with G418 selection | pass | pass | The complete supplied Addgene 27705 NeoR/KanR allele provides the requested G418 selection. |
| Cre-dependent tdTomato-P2A-PuroR reporter | pass | pass | All nine modules and three explicit relationships pass. |
| Cas9-P2A-mCherry with kanamycin propagation | fail | pass | All ten modules and four explicit relationships pass; 0.946678 whole-reference similarity is advisory. |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | fail | pass | All eleven modules and four explicit relationships pass; 0.744138 whole-reference similarity is advisory. |
| Guide-vector mCherry-P2A-NeoR replacement | pass | pass | The Addgene 27705 NeoR allele is in frame after P2A, has no internal stop, and has a terminal stop; omission of the standalone initiating methionine is permitted in this polyprotein context. |

The functional result is **6/6**, with two verdict changes relative to the raw
sequence-threshold score. NeoR is matched against both functional alleles in the
supplied inventory (Addgene 13031 and 27705). Only the P2A-linked NeoR task
allows the protein template without its standalone initiating methionine; this
allowance is explicit in the task's construct specification rather than applied
globally. The reviewed artifacts are:

- `construct_constraints_v1.json`: six functional specifications.
- `gpt56sol_functional_v3_rescore.csv`: compact per-sample audit results.
- `experiments/traces/gpt56sol_cloning_inventory_hard_6tasks_functional_v3_reviewed.eval`:
  complete reviewed Inspect trace, retaining every original model message and
  score in metadata.

## Reproduction

```bash
OPENAI_API_KEY="$(tr -d '\r\n' < /path/to/openai-key.txt)" \
  .venv/bin/inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_inventory_hard_v1/questions.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max \
  --cost-limit 0.1 --model-cost-config experiments/novel_token_costs.yaml \
  --max-tokens 64000 --message-limit 60 --token-limit 3000000 \
  --max-connections 3 --epochs 1 --no-fail-on-error \
  --log-dir experiments/traces
```

The post-run guard was:

```bash
.venv/bin/python tools/check_run_guards.py \
  experiments/traces/gpt56sol_cloning_inventory_hard_6tasks.eval \
  --budget 100000 --metric novel
```

It reported that all six samples were within budget, unique, and used sandbox
tools.

The functional rescore used:

```bash
PYTHONPATH=src .venv/bin/python tools/rescore_cloning_traces_v3.py \
  <directory-containing-only-the-raw-trace> experiments/traces \
  --cache-dir <cache-dir> --reference-dir <reference-dir> \
  --all-cloning-references-circular \
  --constraint-specs \
    experiments/cloning_inventory_hard_v1/construct_constraints_v1.json \
  --suffix _functional_v3_reviewed \
  --report-csv \
    experiments/cloning_inventory_hard_v1/gpt56sol_functional_v3_rescore.csv
```
