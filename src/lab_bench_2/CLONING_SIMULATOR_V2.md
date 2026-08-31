# Cloning simulator v2 design and audit

## Molecular implementation

Current cloning evaluation uses `pydna` 5.5.x for PCR, Gibson assembly,
restriction digestion/ligation, and Golden Gate assembly. `pydna.Dseqrecord`
retains both strands and the sequence, polarity, and strand of each sticky end.
The protocol DSL still returns its existing `BioSequence` type; a private pydna
record is carried through nested intermediates so that conversion does not
discard molecular state.

Edlib supplies exact unit-cost edit distance for verification. Its infix mode
compares all circular origins in one pass. Sequence scoring treats a molecule
and its reverse complement as the same double-stranded DNA molecule.

## Findings and changes

- PCR: the Go-backed simulator could miss products crossing circular coordinate
  0, and its fallback used a separate handwritten binding model. One pydna PCR
  path now handles linear and circular templates, inverse/origin-crossing PCR,
  5' tails, IUPAC matching, and non-specific amplification.
- Restriction digest: the prior adapter represented sticky ends as two unsigned
  lengths and produced incorrect origin-straddling circular fragments. pydna now
  performs Watson/Crick cuts and preserves signed sticky-end geometry.
- Restriction ligation: failed ligation returned two unassembled inputs, and
  self-ligation could hide insert-containing products. pydna now returns only
  physically compatible circles; input subsets expose both one- and two-input
  products, while failed ligation returns no product.
- Golden Gate: the handwritten pairwise walk could not reliably represent Type
  IIS cut geometry. pydna uses each selected enzyme's actual cut positions; all
  input subsets are considered and ranked by retained sites and input count.
- Gibson: handwritten depth-first search could omit products, overrun its bound,
  and depend on generated fragment names. pydna finds homologous assemblies;
  bounded subset enumeration retains competitors and SEGUIDs deduplicate them.
- Sequence similarity: exact-anchor guesses missed valid circular near-matches,
  and reverse complements were not equivalent. Edlib now computes exact linear
  or circular edit distance and checks both strand representations.
- Digest verification: sorting equal-length fragments and zipping could compare
  the wrong pair. Thresholded bipartite matching now finds any complete
  one-to-one fragment assignment.
- Final scoring: comparing only product 1 caused false negatives. Every top-level
  candidate is now assessed, and one candidate must pass all enabled validators.

Archived upstream wrappers remain in `lab_bench_2.cloning_simulators.legacy`
only to reproduce old traces. New scoring does not call them and PCR no longer
requires Go.

## Product-selection and safety semantics

A physical reaction can produce more than one compatible molecule. Each
assembly method evaluates every non-empty subset of its top-level inputs so
dropout/self-ligation products are not silently suppressed. Molecules are
deduplicated with pydna's topology-, origin-, and strand-aware double-stranded
SEGUID. Candidate output is bounded at 256, input-subset reactions at 1,024,
and pydna independently bounds assembly paths. A limit violation is an explicit
execution error, never silent truncation.

Multiple products are allowed only at the protocol's top level. If a nested
operation is ambiguous, execution stops because the DSL has no product-selection
operation. The hidden reference ranks final candidates for scoring but never
changes simulation or chooses an intermediate.

## Tests and evidence

Synthetic tests cover circular-origin PCR with primer tails, non-specific PCR,
competing Gibson products and safety limits, three-input BsaI Golden Gate,
EcoRI sticky-end ligation and failed ligation, reverse-complement equivalence,
circular near-matches without exact anchors, and unordered equal-size digest
fragments.

Integration tests use the checked-in copies of Addgene plasmids 181752 and
13770. Their SHA-256 values are checked against the pilot manifest. The three
canonical PCR-to-Gibson protocols must each produce exactly one circular product
that exactly matches its independently constructed 5,476 bp, 5,617 bp, or
5,551 bp reference.

The tests do not establish wet-lab yield or efficiency. The model does not
simulate methylation, star activity, incomplete digestion, enzyme buffer or
temperature compatibility, primer thermodynamics beyond annealing identity,
secondary structure, molar ratios, transformation, toxicity, colony sampling,
or stochastic abundance. Golden Gate and Gibson output therefore means
sequence-level molecular compatibility, not that a product will dominate an
experiment.

## Reproducible rescoring

`tools/rescore_cloning_traces_v2.py` reuses the answer recorded in an Inspect
log, runs it through the current evaluator, and preserves the old score and
explanation in metadata. This isolates verifier changes without another model
call. Reviewed copies can also include the annotated sequence-comparison event
used by Inspect View.
