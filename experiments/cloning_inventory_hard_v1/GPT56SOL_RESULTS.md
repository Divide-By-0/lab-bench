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
