# Why the 14 Soul Max non-passes failed

The generator **did** have a working answer before the model saw the
task. That does not mean the model saw that answer.

## What the model never gets

The canonical protocol is built *first*, then hidden:

1. Pick one exact GBK and one exact CDS interval (coordinates).
2. Design primers whose 3' 15 bp are unique on that template.
3. Run cloning simulator v2; keep the product only if it matches the
   intended circle.
4. Write that circle to `validation/<id>_assembled.fa`.

The model gets a natural-language request plus **all 55 GBKs**. It is
not told the filename, coordinates, or primer set. The scorer demands
near-identity to *that one circle* (0.95), not “any EGFP swap that a
lab would accept.”

So a Gibson of EGFP into *a different* AAV reporter, or Cas9→EGFP on
PX459 instead of pX330, is a real cloning design and still **fails**.

## The 14, grouped

### A. Wrong lookalike plasmid (7)

Prompt says “one of our X plasmids.” Several inventory files match X.

| Addgene intended | What Sol actually PCR'd | Similarity | Why |
| ---: | --- | ---: | --- |
| 181752 Cas9→EYFP | PX459 `62988` Cas9 + a different EYFP map | 0.606 | “mammalian Cas9 expression” also matches PX plasmids |
| 23007 NeoR→tdTomato | pcDNA3.1-HA `128034` | 0.747 | both CMV / NeoR mammalian plasmids |
| 65202 sfGFP→mCherry | pYTK001 `65108` | 0.801 | sibling YTK GFP-dropout parts |
| 42230 pX330 Cas9→EGFP | PX459 `62988` | 0.885 | Zhang CRISPR family (pX330/PX458/PX459) |
| 48138 PX458 Cas9→EGFP | PX459 `62988` | 0.938 | same family; origin-wrapping Cas9 vs V2.0 map |
| 83900 mDlx EGFP→mCherry | pAAV.hSyn.eGFP `105539` | 0.851 | several AAV EGFP reporters in the bag |
| 37825 CAG-GFP EGFP→mCherry | same `105539` | 0.660 | same |

The model did a 2-fragment Gibson of the named cargo. It picked the
wrong physical file, so the rest of the backbone (promoter, ITRs,
origin wrap) is not the reference.

### B. Right plasmid, wrong junctions / donor (3)

| Addgene | Similarity / error | What differed |
| ---: | --- | --- |
| 26973 6225 bp ChR2→EGFP | 0.878 | Correct map. Donor was `105539` EGFP, not `128652`. Primers also ate extra MCS (`GAATTCGATATCAAGCTT…`) so the product is not a clean CDS replacement. |
| 26973 6236 bp ChR2→EGFP | 0.878 | Same pattern on the other ITR-length map. Dual-map trap did **not** cause a file mixup here; both maps failed the same extra-flank way. |
| 20298 7266 bp inverted ChR2→EGFP | PCR no product | Reverse primer `CCAGCGGCCGCCAC` is 14 bp; pydna's anneal limit is 15. Canonical uses 18 bp. Donor was `105539` not `83900`. The other 20298 map (7256 bp) **passed**. |

### C. OpenAI bio-policy, no protocol (4)

| Addgene | Payload | Novel tokens | Tools |
| ---: | --- | ---: | ---: |
| 12260 psPAX2 | HIV-1 gag → tdTomato | 0 | 0 |
| 12259 pMD2.G | VSV-G → mCherry | 14,823 | 5 |
| 8454 pCMV-VSV-G | VSV-G → tdTomato | 20,058 | 7 |
| 8455 pCMV-dR8.2 | HIV-1 gag → EYFP | 12,195 | 3 |

Scorer: “Format invalid: no protocol tags.” The model was refused
(`bio_policy`) on packaging-helper HIV-1 gag / VSV-G wording. Not a
junction error.

## How a precomputed key can still be missed

| Generator (hidden) | Model |
| --- | --- |
| Knows plasmid id and sequence-id filename | Sees 55 unlabeled-as-role GBKs |
| Knows exact CDS `[start,end]` (and origin wrap) | Must parse features; Cas9 is often split / fused / wrapped |
| Picks one donor file’s complete CDS | Several EGFP/mCherry alleles; any complete copy is “from inventory” |
| Primers unique at pydna’s 15 bp 3' footprint | Short primers fail PCR; extra MCS flanks change the circle |
| Product stored as the only correct FASTA | 0.95 identity to that FASTA, rotation/RC allowed, extra bases not |

The key is a *witness* that the request is solvable from the attached
files, not a string the model is shown. Ambiguous prompts (“one of our
AAV reporter plasmids”, “one of our mammalian CRISPR plasmids”) make
several circles biologically reasonable and only one graded correct.

## Gemini 2.5 Pro on the same 14 (500k novel-token cap)

Inspect in this checkout does not know `google/gemini-3.7-flash`. Ran
`google/gemini-2.5-pro` with `--cost-limit 0.5` (500k novel). Trace:
`experiments/traces/gemini25pro_addgene_sol_fail14.eval`.

**4/14 pass.** Mean ~33k novel tokens; nobody hit 500k.

| Addgene | Sol | Gemini | What changed |
| ---: | --- | --- | --- |
| 12259 pMD2.G VSV-G | bio_policy | **pass 1.000** | Gemini was allowed to answer |
| 8454 pCMV-VSV-G | bio_policy | **pass 0.993** | same |
| 20298 7266 bp inverted ChR2 | PCR fail (14 bp primer) | **pass 0.952** | Valid PCR this time |
| 26973 6236 bp ChR2 | 0.878 extra MCS | **pass 1.000** | Clean CDS swap on the intended map |
| 12260 / 8455 HIV-1 gag | bio_policy | fail (PCR / 0.67) | No provider refuse; still wrong product |
| 181752, 23007, 65202, 42230, 48138, 83900, 37825, 26973 6225 bp | fail lookalike or flanks | fail | Same sibling-plasmid / PCR-break pattern |

Gemini does **not** fix the inventory-ambiguity failures. Extra budget
was unused. It mainly recovers the OpenAI-refused envelope plasmids and
one of the two ITR-length ChR2 maps.
