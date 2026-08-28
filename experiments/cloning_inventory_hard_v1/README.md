# Hard Addgene cloning inventory pilot

This package preserves the easier `cloning_inventory_pilot_v1` set and adds six genuinely harder underlying constructs. These are not merely prompt-redacted versions of two-fragment swaps.

| Construct | Canonical components | Inventory files |
| --- | ---: | ---: |
| TCF/LEF EGFP-P2A-PuroR reporter | 3 | 12 |
| Lentiviral mCherry with G418 selection | 4 | 12 |
| Cre-dependent tdTomato-P2A-PuroR reporter | 3 | 12 |
| Cas9-P2A-mCherry with kanamycin propagation | 5 | 12 |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | 4 | 12 |
| Guide-vector mCherry-P2A-NeoR replacement | 4 | 12 |

## What makes these harder

- No assembly method, backbone, insert source, plasmid name, or exact coordinates are disclosed.
- Each task supplies 12 accession-only GenBank files, including close architectural decoys.
- The exact products require three to five PCR-derived components.
- All six tasks require frame-sensitive coding or tag junctions; three require two coding changes, and two require reverse-orienting a bacterial marker.
- The prompts impose retained-architecture and component-count constraints so whole-vector redesign is not an equivalent answer.

The existing sequence verifier remains usable because every prompt still defines one smallest-change final construct. `validation/` contains exact circular FASTA references and annotated GenBank review references. Every base is covered by an assembly-component provenance annotation.

## Regeneration

```bash
uv run --extra lab_bench_2 python tools/generate_cloning_inventory_hard_questions.py \
  --input-dir /path/to/addgene-genbank-files \
  --output experiments/cloning_inventory_hard_v1
```

## Running

```bash
inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_inventory_hard_v1/questions.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max
```
