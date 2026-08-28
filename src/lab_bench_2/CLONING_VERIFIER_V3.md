# Cloning verifier v3

Verifier v3 is a shadow/rescoring verifier for cloning traces. Version 3-B adds
a deterministic constraint mode in which scorer-owned truth describes an
acceptable construct family rather than one exact reference sequence:

1. Required functional modules are matched using direct input-derived DNA or
   translated protein evidence, permitting synonymous coding variants.
2. Each module has an explicit copy range. Overlapping annotations are
   deduplicated, and intentionally repeated modules are counted as physical
   placements rather than overlapping k-mers.
3. Only explicitly specified order and fusion relationships are checked.
   Unspecified tags, linkers, absolute locations, and annotation ordering do not
   affect the result.
4. pLannotate is a deterministic annotation fallback when a module has no
   sequence template. Its entire call set is never compared with the reference
   and does not need human adjudication.
5. Whole-reference similarity and reference-derived feature/repeat differences
   remain diagnostic in constraint mode. Topology and a configured restriction
   digest remain physical hard gates.

The legacy reference-derived mode remains available for logs without a
`construct_spec`, but it should not be used as ground truth for tasks that allow
multiple valid construct variants.

## Design

### Two answer layers

The model answer remains an executable cloning DSL expression inside
`<protocol>` tags. The simulator executes that expression and produces one or
more physical candidate molecules. The scorer answer is a hidden
`ConstructSpec`: it describes the family of biologically acceptable products.
It is not a canonical plasmid sequence and is not exposed to the model.

Keeping these layers separate lets the benchmark score the constructed product
without requiring the model to choose the same assembly route, synonymous CDS,
tag variant, linker, or circular origin as a single ideal answer.

### Constraint schema

Specifications are keyed by question id for historical rescoring, or stored
directly under scorer-only `validator_params.construct_spec` in a dataset:

```json
{
  "name": "CAG-5x-mCherry expression plasmid",
  "topology": "circular",
  "modules": [
    {
      "id": "cag",
      "description": "CAG promoter",
      "source_features": {
        "file": "pcag-golden-gate-destination",
        "label": "chicken beta-actin promoter",
        "feature_type": "promoter"
      },
      "match": "dna",
      "copies": 1
    },
    {
      "id": "mcherry",
      "description": "complete mCherry protein",
      "source_features": {
        "file": "pcmv-ha-mcherry",
        "label": "mCherry",
        "feature_type": "CDS"
      },
      "match": "protein",
      "copies": 5
    },
    {
      "id": "polya",
      "description": "bGH polyadenylation signal",
      "source_features": {
        "file": "pcag-golden-gate-destination",
        "label": "bGH poly(A) signal",
        "feature_type": "polyA_signal"
      },
      "match": "dna",
      "copies": 1
    }
  ],
  "ordered": [["cag", "mcherry", "polya"]]
}
```

Each module supports:

- `source_features`: one or more annotated task-input features that provide
  accepted sequence templates. Selecting multiple features expresses accepted
  biological variants.
- `match`: `dna`, `protein`, `either`, or `annotation`. Protein matching accepts
  synonymous coding sequences; DNA matching is appropriate for promoters,
  origins, IRES elements, and other sequence-defined noncoding modules.
- `copies`, or `min_copies` plus `max_copies`: the allowed number of complete,
  deduplicated physical placements. A `0..0` range can express explicit absence.
- `dna_sequences` and `protein_sequences`: inline accepted templates when no
  suitable source annotation exists.
- `annotation_aliases`: accepted pLannotate names used only by the annotation
  fallback.

Relations are deliberately separate from module presence:

- `ordered` defines a partial circular order over only the listed modules.
  Unlisted modules may occur anywhere.
- `fusions` defines an explicitly requested left-to-right fusion and can enforce
  strand, maximum linker length, reading frame, and absence of internal stops.
- Tag position is therefore irrelevant unless the task authors an order or
  fusion constraint for that tag.

### Evidence and verdict flow

For every simulator product, the verifier:

1. Checks the configured physical topology and optional restriction digest.
2. Extracts selected templates from the task's GenBank inputs.
3. Searches the candidate directly for complete DNA modules or translated
   protein modules on either strand, including across a circular origin.
4. Deduplicates overlapping annotations and accepted variants that describe the
   same physical placement.
5. Uses matching pLannotate calls only when a module has no direct sequence hit.
6. Checks each copy range and only the explicitly authored order/fusion
   relations.
7. Passes when one simulator product satisfies every hard constraint.

Direct evidence always wins over pLannotate evidence. Consequently duplicate or
differently named pLannotate calls cannot turn one directly detected protein
into multiple copies, and the candidate's full annotation list never needs a
reviewer to reconcile it with a reference annotation list.

The Inspect explanation reports every module's observed and expected copy count,
its evidence source, each explicit relationship, topology/digest status, and the
final verdict. The prior score and explanation remain in metadata rather than
being presented as part of the new verdict.

### Authoring principles

- Encode the biological requirement, not incidental structure copied from an
  ideal plasmid.
- Prefer protein matching for complete CDS requirements and DNA matching for
  sequence-defined regulatory parts.
- Enumerate accepted variants instead of weakening identity thresholds globally.
- Constrain copy count, order, fusion, or tag location only when the prompt makes
  that property meaningful.
- Use whole-reference similarity and reference-derived annotations as audit
  diagnostics, never as hidden hard gates in constraint mode.

### Current limitation

An order such as `cag -> mcherry -> polya` succeeds when a valid choice of those
module placements occurs in that order. Combined with `copies: 5`, it requires
five complete mCherry copies but does not yet prove that all five form one
contiguous repeat block between the promoter and poly(A). Tasks needing that
stronger statement should add a future repeat-block or `all_between` relation;
the current specifications do not claim to enforce it.

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
  --require-plannotate --download-missing --all-cloning-references-circular \
  --constraint-specs experiments/cloning_construct_constraints_v1.json
```

The tool preserves each original answer and score, adds the complete v3 report
to metadata, and writes a CSV summary. It does not call a model and does not
replace the production scorer; promotion should follow review of the shadow
results and adversarial fixtures.

For benchmark integration, store the same specification under scorer-only
`validator_params.construct_spec`. The external JSON flag exists for immutable
historical-log rescoring and does not make a model call.
