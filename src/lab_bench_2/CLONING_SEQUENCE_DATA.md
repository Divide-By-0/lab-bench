# Cloning sequence acquisition and inventory

This document describes a reproducible path from Addgene plasmid identifiers to
validated GenBank files, then from those files to model-facing feature, primer,
and restriction-enzyme inventories. It also records an audit of the LAB-Bench 2
cloning attachments available on 2026-08-27.

## What the model receives today

LAB-Bench 2 has 14 cloning questions. At the dataset revision pinned by this
repository, their official attachment set contains 30 file instances: 29
GenBank files and one FASTA file. Depending on the evaluation mode, the same
source contents are injected into the prompt, attached as files, or copied into
the retrieval sandbox. The model does not currently receive a normalized parts
list, feature-to-file index, or enzyme inventory.

The local `~/.cache/labbench2/labbench2-data-public/cloning` snapshot currently
contains 31 supported sequence files because
`addgene-plasmid-105539-sequence-457689.gbk` also has a `(1)` copy. It also
contains `Homo_sapiens_ENST00000612748_1_sequence.fa.orig`; `.orig` is not a
supported sequence extension for the inventory tool, but a generic attachment
loader may still expose it. These are local repair artifacts, not two additional
official inputs, and should not be used to infer the benchmark contract.

## Download Addgene GenBank files

The default, API-key-free route is HTTP and is meant for long plasmid lists.
Sequence ids and GenBank URLs are public. The GBK bytes are gated by Addgene's
media-edge cookie, which this tool reads from the already-signed-in Chrome
profile. Cookie values are cached at `~/.cache/lab-bench-addgene/cookies.json`
(mode 0600) and omitted from git and manifests.

```bash
uv run python tools/download_addgene_gbk.py \
  181752 https://www.addgene.org/128652/ \
  --output-dir /path/to/addgene-gbk
```

That is `--via chrome-session`. It does not open a Chrome window per plasmid,
does not go through `Downloads`, and reuses the same polite retry/cache path
as the API downloader. Sign in once at <https://www.addgene.org/> in Chrome.
`--via api` is the durable unattended route once a Catalog token exists.

An earlier AppleScript path opened one Chrome window per plasmid, scraped the
signed-in sequences page for the `.gbk` link, navigated Chrome so the file
landed in `~/Downloads`, then validated and moved it. That avoided reading the
cookie store. It does not scale (window flash, Downloads folder, no HTTP).
Deleted 2026-08-27. To regenerate: `osascript` `execute javascript` on
`https://www.addgene.org/<id>/sequences/` to collect `a[href$=.gbk]`, open that
URL in the same Chrome profile, wait for `~/Downloads/addgene-plasmid-<id>-*.gbk`.
Apple Events JS must be enabled (View → Developer). HttpOnly cookies never
appear in `document.cookie`; Cloudflare 404s `.gbk`/`.dna` without
`__Secure_media_edge_auth`.

Addgene directs bulk/programmatic use to the Developers Portal:
<https://help.addgene.org/hc/en-us/articles/44210206209549/>.
When a Catalog token is available, keep it in `ADDGENE_TOKEN`:

```bash
export ADDGENE_TOKEN="..."
uv run python tools/download_addgene_gbk.py \
  181752 https://www.addgene.org/128652/ \
  --output-dir /path/to/addgene-gbk
```

For a longer list:

```text
# plasmids.txt
181752
128652
https://www.addgene.org/105539/
```

```bash
uv run python tools/download_addgene_gbk.py \
  --ids-file plasmids.txt \
  --output-dir /path/to/addgene-gbk
```

The API downloader selects Addgene-verified full sequences before depositor
full sequences, validates every response with Biopython, writes atomically,
records a SHA-256 manifest, and reuses validated cached files. Requests are
serial with configurable jitter and bounded exponential retry. `Retry-After` is
honored. Standard `HTTPS_PROXY` and `NO_PROXY` variables or one explicit
`--proxy-url` are supported for a legitimate fixed network proxy. Proxy
rotation, CAPTCHA bypass, and credential extraction are deliberately not
supported.

Anonymous `curl` of a GenBank media URL still returns 404. The public
collection API returns the URL; the signed-in Chrome media-edge cookie is what
actually fetches the file. Cookie values stay in process memory and are omitted
from manifests.

The downloader takes plasmid identifiers, not arbitrary primer names. A primer
name is not a globally unique Addgene key. If the input really is a list of
primers, first build the local inventory below and query
`primer_label_to_files`; use sequence alignment when a primer sequence rather
than a label is supplied.

## Generate the inventories

Install the `lab_bench_2` extra so Biopython is present, then run:

```bash
uv run python tools/inventory_cloning_sequences.py \
  ~/.cache/labbench2/labbench2-data-public/cloning \
  --root ~/.cache/labbench2/labbench2-data-public/cloning \
  --output cloning-sequence-inventory.json
```

The JSON contains:

- A per-file and per-record inventory with file and sequence hashes, format,
  length, topology, raw feature count, non-`source` annotation count, biological
  part count, and primer count.
- A parts list for every non-source, non-primer GenBank feature: raw structural
  type, coordinates, strand, source qualifiers, normalized label,
  deterministic functional roles, and a conservative prompt-ready description.
- A primer list with labels, coordinates, strand, and the binding sequence in
  5-prime-to-3-prime orientation.
- Reverse indexes from feature label, functional role, primer label, sequence
  hash, and NEB enzyme to files.
- Duplicate-sequence groups, captured parser warnings, parse errors, files with
  no biological part features, and files with no primers.
- A Biopython restriction-enzyme catalog for supplier code `N` (New England
  Biolabs), with recognition/cut geometry and zero-, single-, and multi-cutter
  file indexes.

The NEB inventory is computational metadata from the installed Biopython
version. Commercial availability changes, so check the live
<https://enzymefinder.neb.com/> catalog before treating it as a purchasing
list.

## Keep structure and function separate

GenBank's `CDS` is a structural annotation: it says that a region encodes a
protein or peptide. It does not by itself say what that product is for. For
example, the downloaded plasmid 181752 GBK represents `SV40 NLS`, `FLAG`, and
`Cas9` as CDS features, but their useful functional roles are localization
signal, epitope tag, and genome-editing effector. The inventory therefore
preserves both dimensions:

```json
{
  "feature_type": "CDS",
  "label": "SV40 NLS",
  "functional_roles": ["coding_sequence", "localization_signal"],
  "functional_description": "SV40 NLS: protein-coding sequence, subcellular localization signal"
}
```

The initial deterministic vocabulary includes promoters, enhancers,
terminators/polyadenylation signals, origins, selection markers, reporters,
genome editors, localization signals, epitope and affinity tags, translation
control, viral packaging/expression elements, recombination sites, binding
sites, introns/splicing elements, coding sequences, and primer-binding sites.
Raw annotations remain the source of truth; multiple functional roles are
allowed.

## Current cloning attachment audit

The generated inventory parses all 31 supported files in the current local
cache. Ignoring the local duplicate leaves the 30 official attachment
instances. The sole file with no biological part features is:

- `61e4b666-1ee5-4046-b304-d57e183c8593/Homo_sapiens_ENST00000612748_1_sequence.fa`

The official attachment instances with no primer annotations are:

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
official GenBank instances, 21 contain `primer_bind` features. The original
records contain 313 primer annotations and 50 distinct labels before normalized
aliases are collapsed.

Biopython warns that a few source records encode origin-wrapping locations in a
nonstandard form and repairs them while parsing. The inventory captures those
warnings per file; it does not silently rewrite benchmark inputs.

## Plasmid 181752 inspection

The Addgene `.gbk` downloaded to `Downloads` is a 10,783 bp circular record with
40 total features: one `source`, 21 other biological parts, and 18
`primer_bind` annotations. Parts include truncated gag, three NES elements,
FLAG, two SV40 NLS elements, Cas9, beta-globin polyadenylation and intron
features, AmpR and its promoter, two origins, lac/T7/CMV regulatory features,
and several protein-binding sites. The 18 primers include pLXSN 5-prime, pBABE
5-prime, Bglob-pA-R, rbglobpA-R, M13 variants, L4440, pBR322ori-F, Amp-R,
F1ori-F/R, T7, CMV-F, and LNCX.

The `.dna` file is the SnapGene representation of the same 10,783 bp sequence.
It carries the map/features and richer primer objects; the GenBank file is the
portable text representation that the benchmark and Biopython can consume.
Manual inspection of the signed-in Addgene sequence map agreed with the parsed
GBK, so uploading this private copy to Benchling was unnecessary. Benchling is
still a reasonable optional visual QA step for selected files, not the source
of inventory truth.

## Addgene inventory subset

LAB-Bench cloning attachments are not a survey of Addgene. For inventories of a
broader, still-small slice of the repository, use the curated catalog in
`src/lab_bench_2/addgene_inventory_subset.py`. Full-sequence plasmids only (no
Sanger partials), spanning hosts and a Gibson/Golden Gate complexity ladder
from 2-fragment inserts through 8-part YTK cassettes to the 24-fragment
pGGAselect destination.

Gotchas in that catalog come from public reports, including traps that a length
check will not catch:

- Conflicting Addgene-verified vs depositor full maps, including the 11-bp 5'
  ITR C-C' deletion on popular AAV plasmids (Xie et al., *NAR* 2025
  [gkaf697](https://doi.org/10.1093/nar/gkaf697); Table S4 lists 26973,
  60229, 83900, 104588; 112159/112173 also reported backbone flips; 112168 is
  the match control from that deposit, still 3 bp apart).
- Two Addgene-verified full sequences on one plasmid page (62988 PX459 V2.0).
- FLEX/DIO inverted ORFs and packaging leak: [28306](https://www.addgene.org/28306/)
  recombines more than other FLEX vectors (Addgene comments);
  lox2272 x lox2272 is about 10x weaker than loxP
  ([BMC Biotechnol 2018](https://bmcbiotechnol.biomedcentral.com/articles/10.1186/s12896-018-0462-x)).
- BbsI vs BsmBI vs BsaI cloning enzyme mixups across Zhang PX plasmids,
  lentiCRISPR v2, and pX601 (SaCas9).
- pX330 nuclease vs pX335 D10A nickase vs pdCas9; maps still say Cas9.
- pLKO.1 1.9 kb stuffer that is not an empty MCS.
- Leftover Type IIS sites in YTK/MoClo/GreenGate (entry BsmBI, cassette BsaI).
- Paper figure vs Addgene sequence typo on [21870 pKJ1712](https://www.addgene.org/21870/notes/).
- Splice-prone HA codon in empty backbone [128034](https://www.addgene.org/128034/)
  (LaFleur et al., *EMBO J* 2026).
- SnapGene ORF stacked on CDS ([BioStars](https://www.biostars.org/p/230001))
  and uncatalogued part variants across Addgene (Mante et al., *NAR* 2023
  [gkad187](https://doi.org/10.1093/nar/gkad187)).
- Local `(1)` duplicate of plasmid 105539 in the LAB-Bench cloning cache.

Build it (GBKs stay in `~/.cache`, not git):

```bash
uv run python tools/build_addgene_inventory_subset.py \
  --inventory-out ~/.cache/lab-bench-addgene/inventory-subset/inventory.json \
  --no-enzymes
```

Plasmids tagged `sequence_source="all"` download every public full map so the
inventory can see same-id, different-sha256 conflicts. Preferred download of
those plasmids would hide the ITR mismatch. Cookie handling is the same
chrome-session path as `tools/download_addgene_gbk.py`.

## Enrichment plan

Use a provenance-preserving, three-layer pipeline:

1. **Source layer:** exact sequence, coordinates, structural feature type, and
   qualifiers from the original file. Never overwrite these fields.
2. **Deterministic layer:** normalized aliases, role rules, primer sequences,
   restriction sites, duplicates, and indexes generated by this repository.
3. **Enrichment layer:** proposed annotations, each with method, database and
   version, match coordinates, identity/coverage, confidence, and review state.

Run [pLannotate](https://github.com/mmcguffi/pLannotate) only as an optional
second pass on files with absent or sparse annotations. Its SnapGene,
Swiss-Prot, FPbase, and Rfam searches can recover familiar plasmid parts, but a
similarity match is an enrichment candidate rather than source truth. Record
the pLannotate version/database and keep its output separate.

The current iGEM Registry beta API at <https://api.registry.igem.org/docs> can
cross-reference exact or high-confidence synthetic-part sequence matches. It is
most useful for standardized promoters, RBSs, coding parts, and terminators; it
will not cover every mammalian gene, tag, backbone, or Addgene construct.

An LLM can turn labels, products, notes, neighboring parts, and trusted database
matches into concise descriptions such as “nuclear-localization tag” or
“constitutive mammalian promoter.” It must not invent sequence identity,
coordinates, primer compatibility, or enzyme sites. Store LLM text as inferred,
with model/prompt version and confidence, and retain the evidence fields used.

## Difficulty as connection count

Represent each cloning question as a small evidence graph rather than one
opaque difficulty number. Nodes are requested functions, candidate source
files, source features, chosen fragments, primers, enzymes, transformations,
junctions, and the final construct. Typed edges capture the reasoning step:

- prompt function to functional role;
- functional role to candidate feature;
- source feature to selected fragment boundary;
- fragment to junction;
- junction to primer or synthesis edit;
- enzyme to recognition site and compatible overhang;
- final adjacency to validation evidence.

Store this raw difficulty vector per question:

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

`required_connection_count` should count the minimal validated path, not every
possible candidate. Keep the components so later weights can be learned from
model error rates instead of chosen by intuition. A useful initial grouping is:

- D0: inspect or retrieve one directly named feature/primer.
- D1: map one requested function to one clearly annotated source feature.
- D2: select and join two directly annotated parts with local constraints.
- D3: multi-part design with primer design, internal-site checks, edits, or
  multiple plausible sources.
- D4: sparse/missing annotations requiring pLannotate, external registry
  evidence, or manual review before the construct can be grounded.

The next benchmark-data change should generate this graph alongside each
question, then compare the vector with empirical pass/fail trajectories before
using a weighted score in reports.

## Public-mirror coverage

No comprehensive public Addgene GBK mirror was found. The useful Zenodo hit,
[Supplementary File S2](https://zenodo.org/records/2536105), is one paper's
archive containing seven GenBank files: `pDG101.gb`, `pJS101.gb`, `pJS102.gb`,
`pZH501.gb`, `pZH509.gb`, `pZH713.gb`, and `ZHX99.gb`. Only three are explicitly
mapped to Addgene: pJS101 (118280), pJS102 (118281), and pZH509 (102664).

Those three cover none of LAB-Bench 2's six explicitly Addgene-named official
GBKs, none of its 30 official cloning attachments, and not plasmid 181752. They
represent roughly 0.0017% of Addgene's current approximately 175,860-plasmid
catalog. Other Zenodo search hits mostly mention Addgene IDs in papers or data
descriptions rather than publishing the corresponding GBK, so Zenodo is a
sparse per-publication fallback rather than a source for arbitrary IDs.

## Prior implementations reviewed

The downloader design borrows the supported API pattern from
[dbikard/seqmake-parts](https://github.com/dbikard/seqmake-parts), while
[longevity-genie/addgene-mcp](https://github.com/longevity-genie/addgene-mcp),
[tlambert03/fpseq](https://github.com/tlambert03/fpseq), and
[Drjackxiaoyuchen/Addgene-Kit-Crawler](https://github.com/Drjackxiaoyuchen/Addgene-Kit-Crawler)
demonstrate older HTML-scraping approaches.
[OpenCloning/OpenCloning_backend](https://github.com/OpenCloning/OpenCloning_backend)
also contains an authenticated web scraper. HTML selectors and browser login
flows are more fragile than the approved API, so they are references rather
than the production path. Any implementation intended to evade Cloudflare or
rotate identities was excluded.
