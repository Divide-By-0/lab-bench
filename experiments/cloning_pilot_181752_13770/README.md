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

The question records use relative object-store prefixes. They are not added to
the gated Hugging Face dataset or automatically registered as an Inspect task.
To deploy them, upload each `cloning/<task-id>/` directory and the corresponding
validation FASTA under the same conventions as the existing CloningQA data.

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
