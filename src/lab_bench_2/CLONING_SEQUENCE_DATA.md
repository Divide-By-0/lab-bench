# Cloning sequence data and enrichment

This document describes how the LAB-Bench 2 cloning attachments reach a model,
what is present in those files, and how to build separate, provenance-preserving
inventories from Biopython, REBASE, the iGEM Registry, and pLannotate. The audit
and live-source counts below were collected on 2026-08-27.

## What cloning models receive

LAB-Bench 2 has 14 cloning questions. At the dataset revision pinned by this
repository, their official attachment set contains 30 file instances: 29
GenBank files and one FASTA file. Depending on evaluation mode, the same raw
source contents are injected into the prompt, attached as files, or copied into
the retrieval sandbox.

The model does not currently receive a normalized parts list, a functional
feature inventory, a feature-to-file index, a primer index, an enzyme catalog,
or external annotations. The tools here generate those structures for analysis
and future dataset design; they do not silently change the existing evaluation.

The local `~/.cache/labbench2/labbench2-data-public/cloning` snapshot contains
31 supported sequence files because one official GenBank file has a `(1)` copy.
It also contains one `.fa.orig` repair artifact, which this inventory ignores.
Those local artifacts are not additional official inputs.

## Data layers

Keep structural annotations, inferred function, and external matches separate:

| Layer | Data | Trust and use |
| --- | --- | --- |
| Source GBK/FASTA | Sequence, coordinates, feature type, qualifiers, annotated primers | Ground truth for what the benchmark supplied |
| Biopython | Parsed records, feature/primer indexes, sequence hashes, restriction sites | Deterministic computation from the source file |
| REBASE | Current restriction-enzyme records with supplier codes | Live catalog evidence; supplier `N` is New England Biolabs |
| iGEM Registry | Specific published parts, descriptions, roles, sequences, and vocabulary | External cross-reference with explicit match evidence |
| pLannotate | SnapGene, FPbase, Swiss-Prot, and Rfam sequence-search hits | Sequence-derived enrichment candidate, kept in separate outputs |
| LLM | Prompt-ready functional description | Inference only; retain model, prompt, evidence, and confidence |

For example, `CDS` says that a region encodes a protein or peptide. It does not
say whether that product is Cas9, a localization signal, an epitope tag, or a
selection marker. The inventory therefore preserves both dimensions:

```json
{
  "feature_type": "CDS",
  "label": "SV40 NLS",
  "functional_roles": ["coding_sequence", "localization_signal"],
  "functional_description": "SV40 NLS: protein-coding sequence, subcellular localization signal"
}
```

## Fetch the independent source data

No Addgene login or API token is involved in this workflow. Fetch the public
vocabularies and current enzyme catalog once; subsequent runs use a validated
local cache:

```bash
uv run --extra lab_bench_2 python tools/fetch_cloning_source_data.py \
  ~/.cache/labbench2/labbench2-data-public/cloning \
  --output cloning-external-sources.json
```

The fetcher is serial, rate-aware, retried, HTTPS-only, host-allowlisted, and
atomically cached. Each response records its URL, retrieval time, SHA-256, and
selected response headers.

The live result used for this audit contains:

- REBASE release 608, dated July 31, 2026: 234 restriction enzymes whose
  supplier codes include `N` (New England Biolabs).
- Biopython 1.87 supplier `N`: 238 enzymes. It directly supports 233 of the 234
  live REBASE names. The spelling difference `CviKI-1` versus `CviKI_1` accounts
  for one mismatch; five names remain only in Biopython's supplier set.
- iGEM Registry API 1.0: 88,418 published parts, 283 nondeprecated Sequence
  Ontology roles, 329 categories, and 53 `//function/...` categories.

The [REBASE monthly EMBOSS files](https://rebase.neb.com/rebase/rebase.files.html)
provide recognition and cut geometry separately from supplier records. This is
better evidence for current NEB availability than treating Biopython's bundled
supplier list as a purchasing catalog. Biopython remains the computation engine
for finding sites in each sequence.

The [iGEM Registry API](https://api.registry.igem.org/docs) exposes published
part searches, individual JSON/FASTA/GenBank/SBOL records, roles, and categories
without authentication. Its one-shot `/v1/parts/export.fasta` endpoint currently
requires login, so this workflow fetches the complete small vocabularies and
uses targeted part lookups rather than pretending an anonymous bulk sequence
mirror exists.

## Generate the source inventory

```bash
uv run --extra lab_bench_2 python tools/inventory_cloning_sequences.py \
  ~/.cache/labbench2/labbench2-data-public/cloning \
  --root ~/.cache/labbench2/labbench2-data-public/cloning \
  --external-sources cloning-external-sources.json \
  --output cloning-sequence-inventory.json
```

The JSON contains:

- A per-file and per-record inventory with file and sequence hashes, format,
  length, topology, raw feature count, biological-part count, primer count,
  parser warnings, and errors.
- A separate parts list for each non-source, non-primer feature: structural
  type, coordinates, strand, raw qualifiers, normalized label, deterministic
  functional roles, and a conservative prompt-ready description.
- A primer list with labels, coordinates, strand, and binding sequence in
  5-prime-to-3-prime orientation.
- Reverse indexes from feature label, functional role, primer label, sequence
  hash, selected iGEM part/role, and restriction enzyme to files.
- Duplicate-sequence groups and explicit lists of files with no biological
  parts or no annotated primers.
- Biopython's restriction metadata plus per-record zero-, single-, and
  multi-cutter results.

iGEM enrichment keeps three different concepts separate:

- `feature_type` is GenBank syntax such as `CDS`, `promoter`, or
  `protein_bind`. It is copied from the source and is never used as an iGEM
  role.
- `functional_roles` are conservative, deterministic prompt terms such as
  `epitope_tag`, `localization_signal`, or `selection_marker` inferred from the
  source label and qualifiers.
- `specific_parts[].role` is the role attached by iGEM to one particular
  published part record. It is shown only with that part's title, useful
  description, URL, and nucleotide/protein match evidence.

For each unique source feature signature, the fetcher searches the anonymous
published-part API by source label and exact source length. It retrieves the
best candidate details, checks the candidate's actual iGEM role against the
source-derived functional role, and auto-selects at most one part only when the
nucleotide sequence or translated peptide is exact. A small auditable alias
table resolves especially ambiguous canonical names such as `FLAG`, but the
same role and sequence-evidence gate still applies. Unverified search results
remain review candidates rather than selected cross-references. Exact source
label lookup against iGEM's role/category vocabulary is retained separately as
a low-confidence aid; GenBank structural types are not fed into that lookup.

On `addgene-plasmid-181752-sequence-353936.gbk`, 12 of 20 unique feature
signatures have a selected specific iGEM part; because some signatures occur
more than once, this covers 13 of 21 source feature instances. For example,
source `FLAG` is a GenBank `CDS`, has local function `epitope_tag`, and maps to
[BBa_K4587111](https://registry.igem.org/parts/bba-k4587111), whose iGEM role is
`Tag` (`SO:0000324`). The source DNA and iGEM DNA are only 83.333% identical,
but both translate exactly to `DYKDDDDK`, so the match is protein-verified and
not falsely presented as a nucleotide-identical part.

## Run pLannotate separately

```bash
uv run --extra lab_bench_2 python tools/annotate_cloning_sequences.py \
  ~/.cache/labbench2/labbench2-data-public/cloning \
  --output-dir cloning-plannotate
```

If pLannotate is absent, the tool automatically creates a cached conda
environment pinned to pLannotate 2.0.0, downloads its checksum-validated
database bundle, and records the complete database manifest. Fast mode uses
SnapGene and FPbase; `--full` also searches Swiss-Prot and Rfam. Original
attachments are never modified. Generated GBK/CSV files and their hashes live
in a separate directory with a source-file manifest. Automatic setup requires
an installed conda, mamba, or micromamba executable; this machine already has
conda, so the validated run required no manual setup.

The installed pLannotate v2 database used here was built July 5, 2026 and
records SnapGene, FPbase, UniProtKB/Swiss-Prot 2026_02, and Rfam 15.1 sources.
See the [pLannotate repository](https://github.com/mmcguffi/pLannotate) for its
search and nested-feature policies.

Short peptide tags expose an important limitation. The selected Addgene
example contains a source-annotated FLAG feature with DNA
`GATTACAAAGACGATGACGATAAG`. pLannotate's SnapGene database contains a FLAG
reference with DNA `GATTACAAGGACGACGATGACAAG`. These 24 bp encodings are only
83.333% identical, below the configured SnapGene BLAST threshold of 95%
nucleotide identity, while both translate exactly to `DYKDDDDK`. Fast mode
therefore omits FLAG even though the peptide function is the same. The specific
iGEM lookup retains both DNA and translated-peptide evidence so this synonymous
codon case is visible rather than silently lost or falsely called
nucleotide-identical.

Real validation on the sole featureless FASTA found one 16 bp SnapGene fragment
at 100% identity but only 3.67% reference coverage. pLannotate correctly marked
it as a fragment. That is not enough evidence to promote it into source truth,
and it illustrates why the CSV evidence, fragment flag, identity, and coverage
must remain visible to models and dataset authors.

On a pET-28b GenBank attachment, the same fast pass found 20 candidate
annotations: 14 non-fragments and ten exact full-length matches. Exact calls
included the bacterial origin, f1 origin, rop, lacI promoter, T7 promoter and
terminator, T7 tag, lac operator, RBS, and thrombin site. Lower-coverage TcR,
AmpR-promoter, SET1, polyhistidine, and capTEV calls remained visibly marked as
fragments. This is the useful case for pLannotate: filling or checking a plasmid
parts inventory while preserving the match evidence.

## Current attachment audit

All 31 supported files in the local cache parse with Biopython. Ignoring the
local duplicate leaves the 30 official attachment instances. The sole file
without biological part annotations is:

- `61e4b666-1ee5-4046-b304-d57e183c8593/Homo_sapiens_ENST00000612748_1_sequence.fa`

The official attachment instances with no annotated primers are:

- `4fb34135-1416-4b17-8bb9-c3a4dd3a2da7/NM_002478.5.gb`
- `4fb34135-1416-4b17-8bb9-c3a4dd3a2da7/pivt-fluc-bxb.gb`
- `5e7bf2b5-5d04-48c6-83d4-38d97ea8542c/pMBP-bdSUMO-dArc1.gb`
- `61e4b666-1ee5-4046-b304-d57e183c8593/Homo_sapiens_ENST00000612748_1_sequence.fa`
- `a4bf037c-2477-4cca-9ca3-12c5ee63c44f/npas4-201-enst00000311034.gb`
- `ad7daee9-2b65-43dc-906b-42ecb07f58b1/pet-28b.gb`
- `ae62bcdb-197b-4815-991f-cb7a9c151ff6/pet-28b.gb`
- `dff28bd4-89ea-401e-a3c1-ce8733512b79/pMBP-bdSUMO-dArc1.gb`
- `fb8fc27d-592a-40e8-a65f-9e1a60b7a708/sorcs2-201-ensmust00000037370.gb`

That is nine attachment instances but seven unique filenames. Across the 29
official GenBank instances, 21 contain `primer_bind` features. The source
records contain 313 primer annotations and 50 distinct original labels before
normalized aliases are collapsed.

Biopython warns that six local files encode origin-wrapping locations in a
nonstandard form and repairs them while parsing. The inventory captures all ten
warnings; it does not rewrite the benchmark inputs.

## Model-facing inventory and question difficulty

For a cloning prompt, provide only the slice needed for the question:

1. Candidate source files and exact source features.
2. Functional-role candidates with their provenance and review status.
3. Relevant primers or the explicit fact that no primers are annotated.
4. Relevant enzyme sites and whether the enzyme is in the live REBASE/NEB set.
5. External sequence-search evidence only when it materially resolves an
   annotation gap.

Represent difficulty as an evidence graph. Nodes include requested functions,
files, features, fragments, primers, enzymes, edits, junctions, and the final
construct. Typed edges record the necessary connection: prompt function to
role, role to feature, feature to boundary, fragment to junction, junction to
primer or edit, and enzyme to compatible recognition site/overhang.

A useful raw vector is:

```json
{
  "inventory_gaps": 0,
  "semantic_resolution_edges": 2,
  "candidate_branches": 1,
  "fragment_selection_edges": 2,
  "junctions": 1,
  "primers_to_design": 2,
  "sequence_edits": 0,
  "enzyme_constraints": 3,
  "external_provenance_hops": 0,
  "required_connection_count": 10
}
```

The connection count should describe the smallest validated reasoning path,
not every possible option. Keep the raw vector even if it is later mapped to a
coarse D0-D4 label, so difficulty changes remain explainable.
