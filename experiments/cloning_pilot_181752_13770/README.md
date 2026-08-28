# Addgene 181752 × 13770 cloning pilot

This directory contains three quick CloningQA-style tasks. Each task uses
`pCMV-MMLVgag-3xNES-Cas9` (Addgene #181752) as the destination and
`pCALNL-GFP` (Addgene #13770) as the source. The complete 6,027 bp
MMLV-Gag-3xNES-Cas9 fusion ORF is replaced with one complete source CDS.

| Task | Task ID | Source CDS | Reference size |
| --- | --- | --- | ---: |
| CMV-EGFP | `777f42d4-f239-5979-8a6e-e13daceba2a3` | EGFP, 720 bp | 5,476 bp |
| CMV-AmpR | `a641ec71-1142-5e19-a1c5-354142bcc6c4` | AmpR/bla, 861 bp | 5,617 bp |
| CMV-NeoR/KanR | `02e631d2-19f5-50f9-a43a-af5e7440fb7d` | NeoR/KanR, 795 bp | 5,551 bp |

All references are circular. They retain destination bases 6,028–10,783,
which include the CMV promoter across the circular origin, the beta-globin
poly(A) signal, the bacterial origin, and the original bacterial AmpR marker.
The inserted CDS includes its native start and stop codons.

## Contents

- `questions.jsonl` contains upload-ready LabBench2 question records.
- `cloning/<task-id>/` contains the two renamed input GenBank files.
- `validation/<task-id>_assembled.fa` is the sequence-only scoring reference.
- `validation/<task-id>_assembled.gbk` is a circular, annotated review copy.
- `canonical_protocols/<task-id>.txt` contains a two-amplicon Gibson protocol.
- `manifest.json` records source hashes, coordinates, primers, lengths, and
  canonical validation results.

The question records use relative object-store prefixes and are not added to the
gated Hugging Face dataset. They can be run directly with the task's
`dataset_path` option; the local loader resolves each input directory and hidden
reference relative to `questions.jsonl`. To deploy them, upload each
`cloning/<task-id>/` directory and the corresponding validation FASTA under the
same conventions as the existing CloningQA data.

## Generation and validation

Regenerate the package from the downloaded Addgene files with:

```bash
uv run --extra lab_bench_2 python tools/generate_cloning_pilot.py \
  --destination /path/to/addgene-plasmid-181752-sequence-353936.gbk \
  --source /path/to/addgene-plasmid-13770-sequence-7759.gbk
```

The generator builds each reference by direct sequence replacement, separately
designs a canonical two-fragment Gibson protocol, executes that protocol with
simulator v2, and fails unless there is exactly one exact circular match. No
digest validator parameters are added.

The source files used for this checked-in generation had these SHA-256 hashes:

- Addgene #181752: `f7d8fd6b2aa1a7b8694a77cac6652d66d5669d2b81f9c433edcfbd65d430a01a`
- Addgene #13770: `cada641a2462f018be374032cd73ec3a40b3287e45678ff81fb0b6f06d5f38e0`

## GPT-5.6-sol pilot run

The three questions were run together on 2026-08-27 with the agentic solver,
file mode, `openai/gpt-5.6-sol`, maximum reasoning effort, and an OrbStack Docker
context. The $0.10 cost guard used $1 per million uncached input/output tokens
and $0 for cache reads, imposing a 100,000-novel-token ceiling per sample.

| Task | Inspect sample | Official result | Novel tokens | Tool calls | Diagnostic sequence result |
| --- | --- | --- | ---: | ---: | --- |
| CMV-EGFP | `labbench2_c7ea2dd4` | pass | 30,144 | 10 | exact, 1.000000 |
| CMV-AmpR | `labbench2_524243f7` | fail | 29,031 | 13 | exact after filename-only syntax repair |
| CMV-NeoR/KanR | `labbench2_4ea2fad5` | fail | 17,199 | 9 | exact after filename-only syntax repair |

The two failures quoted the `.gbk` arguments to `pcr`. In this DSL, an unquoted
token ending in `.gbk` is a file reference, while a quoted token is literal DNA.
The strict verifier therefore rejected both protocols before assembly. For
review only, the enriched trace unquotes strings that exactly match files in the
sample directory and reruns the protocol for the visualization. Both repaired
assemblies are circular, have the expected length, and match their references
exactly. This does not alter their official incorrect verdicts.

The raw and reviewed traces are
`experiments/traces/gpt56sol_cloning_pilot_3tasks.eval` and
`experiments/traces/gpt56sol_cloning_pilot_3tasks_reviewed.eval`. The reviewed
copy retains the original messages and scores and adds the diagnostic maps to
the transcript and scoring explanation.

The essential run arguments were:

```bash
inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_pilot_181752_13770/questions.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max \
  --cost-limit 0.1 --max-tokens 64000 --message-limit 60 \
  --token-limit 3000000 --max-connections 3 --epochs 1
```

## Pilot caveats

The AmpR task deliberately creates a second copy of the same bla CDS already
present in the destination backbone. Because the two CDS sequences are
identical, sequence-only scoring cannot prove that a model sourced the inserted
copy from Addgene #13770 rather than from the destination plasmid. The task is
still useful for testing sequence construction, but not source provenance.

CMV-driven AmpR and NeoR/KanR are artificial constructs. The tasks exercise the
cloning operation, not whether those are desirable mammalian expression
designs. As with the existing verifier, exact sequence agreement also does not
enforce the named assembly method or experimental feasibility independently.

Source pages: [Addgene #181752](https://www.addgene.org/181752/) and
[Addgene #13770](https://www.addgene.org/13770/).
