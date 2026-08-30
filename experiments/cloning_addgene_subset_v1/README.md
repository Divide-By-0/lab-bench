# Addgene subset cloning drafts

55 two-fragment CDS-swap CloningQA questions
generated from `src/lab_bench_2/addgene_inventory_subset_gbk` (55 verified with cloning
simulator v2 / pydna).

Each record uses the shared inventory in `cloning/shared/`
(all 55 tracked GBKs plus the 16-enzyme stock). Exact circular
references live in `validation/<id>_assembled.fa`. Scientist
keys: `ANSWER_KEYS.md` and `answer_keys.tsv`.

Run with GPT-5.6-sol:

```bash
uv run inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_addgene_subset_v1/questions.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max
```

Regenerate:

```bash
uv run --extra lab_bench_2 python tools/generate_addgene_subset_questions.py
```

