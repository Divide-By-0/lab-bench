# Cloning simulator v2 design and audit

## Product-selection semantics

The simulator can produce more than one biologically compatible molecule. There
is no biological reason to treat the first item in that set as the only outcome,
so the verifier evaluates every top-level product and accepts the submission if
one product passes both the global sequence and digest checks.

This rule does not apply silently to intermediates. If a nested operation returns
multiple products, execution stops with an `Ambiguous intermediate` error. The
protocol DSL has no product-selection operator, so arbitrarily feeding product 1
to the next step would make the result depend on enumeration order. A future DSL
version could make such selection explicit by sequence, length, or candidate ID.

Using the hidden reference to assess final products is intentionally limited to
scoring. It does not alter simulation or choose intermediates. To reduce the risk
that over-generation makes scoring too lenient, candidates must be produced by
exact overlap or cohesive-end compatibility, candidate counts are bounded, and
the same candidate must pass every enabled validator.

## Findings and changes

| Operation | Pinned behavior | Failure | v2 behavior |
| --- | --- | --- | --- |
| PCR | Go-backed primer simulation | A valid amplicon crossing coordinate 0 can be reported as absent | Retain the pinned engine; on its no-amplicon result only, recover a unique exact primer pair on a circular template, including primer tails |
| Golden Gate | Pairwise ligation requires both junctions to close immediately | Three-or-more-fragment products cannot form; returned product 1 may be empty vector | Build one compatible junction at a time, enumerate circular products, retain empty-vector products, and prefer products with fewer restored Type IIS sites and more fragments |
| Gibson | Record circles only at terminal search nodes and track used fragments by generated name | A valid circle is omitted if another extension is possible; equal names alias distinct inputs; reverse-complement duplicates remain | Test circularization at every node, track input positions, and deduplicate rotations and reverse complements |
| Sticky-end assembly | Return immediately if the backbone self-ligates | A compatible insert-containing product is never returned | Enumerate both self-ligation and insert-containing circles, preferring products that use more inputs |
| Final scoring | Compare only `result[0]` | A correct non-first product is a false negative | Compare all top-level products and report the selected candidate index and total count |

The original behavior remains available through
`lab_bench_2.cloning_simulators.legacy`, which delegates to the upstream source
pinned at commit `c028ecdcf144b55ffcd92b68be45081df5628c20`.

## Modeling boundaries

These simulators test sequence feasibility, not experimental yield. They do not
model enzyme efficiency, methylation, molar ratios, transformation, colony
sampling, or stochastic product abundance. In particular, Golden Gate
empty-vector/dropout reassembly is retained because it is a compatible product;
products that restore Type IIS sites are ranked lower because they can be recut,
but they are not assigned a quantitative frequency.

Gibson still requires exact overlaps of 10–60 bases. PCR's origin fallback
requires a unique exact 3-prime annealing suffix of at least 15 bases and fails
closed on ambiguous binding sites. Restriction digestion continues to use
Biopython through the pinned `enzyme_cut` primitive; the audit found no benchmark
failure that required replacing that cut-site calculation.

Candidate enumeration has a 256-product safety limit. Exceeding it is an explicit
execution failure rather than a silently truncated search that might exclude the
correct product.

## Reproducible rescoring

`tools/rescore_cloning_traces_v2.py` reuses the model answer already recorded in
each Inspect log, runs it through v2, and preserves the original score and
explanation in metadata. Thus a score difference isolates verifier behavior; it
does not spend model tokens or generate a new answer. The reviewed trace copies
also contain the annotated sequence-comparison event used by Inspect View.
