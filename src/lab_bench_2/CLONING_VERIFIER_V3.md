# Cloning verifier v3

Verifier v3 is a shadow/rescoring verifier for cloning traces. It keeps the
existing pydna execution and candidate-aware sequence/digest checks, then adds
reference-derived structural checks:

1. GenBank feature integrity and ordering (including circular-origin rotation
   and global reverse-complement equivalence).
2. A relative repeat gate: direct or inverted 50-bp exact repeats introduced by
   the candidate, but absent from the reference, fail.
3. Optional external pLannotate calls. The pLannotate annotation multiset and
   circular feature order must agree with the reference. In the production
   rescore command this gate is required; missing databases or a failed CLI is
   recorded as a verifier error rather than a biological pass.

The pLannotate dependency is intentionally kept outside this MIT-licensed
repository. pLannotate 2.0.0 is GPL-3.0-only and depends on external BLAST,
DIAMOND, and Infernal binaries plus a separately installed database bundle.
`PlannotateAnnotator` invokes its CLI, records the executable/version/database
manifest, and caches annotations by sequence hash. This isolates the license
and native-tool boundary while making rescoring reproducible.

## Rescoring

Install pLannotate and its database bundle in an isolated environment, then run
the v3 rescorer over the original (not already-reviewed) logs:

```bash
PYTHONPATH=src .venv/bin/python tools/rescore_cloning_traces_v3.py <source> <output> \
  --cache-dir <cache> --reference-dir <references> \
  --plannotate-executable <env>/bin/plannotate \
  --require-plannotate --download-missing --all-cloning-references-circular
```

The tool preserves each original answer and score, adds the complete v3 report
to metadata, and writes a CSV summary. It does not call a model and does not
replace the production scorer; promotion should follow review of the shadow
results and adversarial fixtures.

The structural policy is deliberately reference-derived for this first pass.
For new benchmark tasks, a future schema should make required feature identities,
allowed copy numbers, ordering, and repeat policy explicit rather than inferred
from one reference construct.
