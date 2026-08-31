# Addgene cloning inventory difficulty pilot

This package contains six underlying cloning designs rendered at three matched
difficulty levels, for a total of 18 questions. Every difficulty variant for a
construct uses the same task ID, six attached plasmids, hidden circular
reference, and scoring policy. Only the information exposed in the question
changes.

| Construct | Baseline design decision | Reference size |
| --- | --- | ---: |
| Lentiviral mCherry | Replace EGFP in pLJM1-EGFP while retaining PuroR | 8,074 bp |
| TCF/LEF-responsive EGFP | Replace TOPFlash luciferase and preserve its Kozak context | 4,051 bp |
| Cre-dependent mCherry | Replace conditional EGFP while retaining the loxP-stop architecture | 6,835 bp |
| Lentiviral EGFP with NeoR | Replace the hPGK-driven PuroR coding region | 8,278 bp |
| Cas9-P2A-PuroR | Replace T2A-EGFP while preserving the Cas9 frame and U6 cassette | 9,174 bp |
| T7 tdTomato-6xHis | Replace MBP without a stop codon to retain the C-terminal tag | 6,222 bp |

## Difficulty levels

| Question file | Method | Materials | Architecture |
| --- | --- | --- | --- |
| `questions.jsonl` | Gibson specified | Backbone and source named | Exact replacement stated |
| `questions_method_blind.jsonl` | Model chooses | Backbone and source named | Exact replacement stated |
| `questions_inventory_functional.jsonl` | Model chooses | Six-item inventory with decoys | Biological functions stated |

The functional questions deliberately retain a smallest-change or
backbone-preservation rule. This keeps each question tied to one intended final
sequence so that the existing sequence verifier remains meaningful. Removing
that rule would create multiple valid architectures and require a multi-answer
or function-aware verifier.

## Package contents

- `cloning/<task-id>/` contains the six-question inventory as renamed GenBank
  files.
- `validation/<task-id>_assembled.fa` contains the hidden circular sequence
  reference used for scoring.
- `validation/<task-id>_assembled.gbk` is an annotated review reference with
  insert, retained-backbone, functional-feature, and sequence-provenance labels.
- `canonical_protocols/<task-id>.txt` contains one validated Gibson solution.
- `manifest.json` records input hashes, coordinates, primers, inventory
  membership, reference sizes, and difficulty settings.

Each canonical protocol is executed by simulator v2 during generation. The
generator fails unless it produces exactly one circular product matching the
independently spliced reference sequence exactly. The canonical method is only
a construction witness; method-blind and inventory-functional model answers may
use any supported method that produces the reference construct.

## Regeneration

Place the 21 downloaded Addgene GenBank files in one directory using their
original `addgene-plasmid-<id>-sequence-<sequence-id>.gbk` names, then run:

```bash
uv run --extra lab_bench_2 python tools/generate_cloning_inventory_questions.py \
  --input-dir /path/to/addgene-genbank-files \
  --output experiments/cloning_inventory_pilot_v1
```

## Running a question set

Substitute any of the three question filenames for `dataset_path`:

```bash
inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_inventory_pilot_v1/questions_inventory_functional.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max
```

The inventory includes real decoys such as packaging plasmids, alternative
reporters, conditional and inducible vectors, and incompatible expression
contexts. It does not yet include a clean domesticated Golden Gate destination
or standalone BlastR/HygroR parts.
