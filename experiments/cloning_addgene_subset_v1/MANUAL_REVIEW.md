# Scientist flags — Addgene subset drafts (pre-run)

LM pass over the 55 generated questions against the catalog, maps, and
canonical Gibson keys. These are **not** model-run results. Flagged rows
are the ones a scientist should look at first; the rest are ordinary
two-fragment cargo swaps (Cas9/EGFP/mCherry/ChR2/VSV-G) that match the
plasmid's advertised payload.

Scoring still uses one exact circular FASTA. A biologically nicer
architecture can fail even when the prompt is fair.

## Flag for manual review

| Priority | Addgene | Question as generated | Why it may be the wrong category |
| --- | ---: | --- | --- |
| high | 10878 | Replace AmpR on pLKO.1 with EYFP | Catalog job is AgeI/EcoRI stuffer→shRNA. AmpR is the bacterial marker, not the cloning slot. Inversion language is about AmpR strand, not the stuffer. |
| high | 52963 | Replace AmpR on lentiGuide-Puro | Real cloning job is BsmBI oligo Golden Gate into the filler. AmpR swap ignores the sgRNA slot and the Puro cassette. Prompt still names Golden Gate. |
| high | 195714 | Replace CmR on pGGAselect | Catalog job is 24-fragment lac cassette Golden Gate. CmR is the bacterial marker; the dest is not a CDS-swap backbone. |
| high | 48856 | Replace AmpR on pGGA000 | GreenGate promoter-module **entry**. Typical work is BsaI part cloning, not AmpR replacement. |
| high | 41819 | Replace NeoR/KanR on gRNA_GFP-T1 | Drosophila gRNA plasmid; catalog job is BbsI oligo Golden Gate. Marker swap is the wrong slot. |
| high | 23007 | Replace NeoR/KanR on pCMV-M1 | Catalog says 2-fragment Gibson of a CDS into the CMV cassette. The live record is pCMV-M1, not an empty backbone; this swaps the mammalian marker instead of M1. |
| high | 51776 | Replace pVS1 StaA on pMDC32B-AtMIR390a-B/c | Plant miRNA backbone. StaA is a binary-vector stability protein, not the miRNA cargo. |
| high | 12260 | Replace HIV-1 gag on psPAX2 | Catalog: used as-is; not a cloning destination. Gag/pol packaging helper. Consecutive-id trap with 12259 is the point, not a gag swap. |
| high | 12259 | Replace VSV-G on pMD2.G | Same: envelope helper, used as-is. VSV-G swap is a real construct people make, but it is not how this plasmid is used in the subset. |
| high | 8455 | Replace HIV-1 gag on pCMV-dR8.2 dvpr | 3rd-gen packaging helper. Catalog note is cassette rearrangement around LTRs, not a single gag ORF. |
| medium | 128034 | Replace AmpR on pcDNA3.1-HA | Empty HA-tag backbone. Intended job is insert a CDS after HA (splice-motif gotcha). AmpR is last-resort because HA is a 27 bp tag. |
| medium | 17398 | Replace KanR on pENTR1A no ccDB | Gateway entry with ccdB already gone. Intended: att-flanked CDS insert, not KanR. |
| medium | 1764 | Replace AmpR on pBABE-puro | Retroviral empty backbone. Intended: CDS into the MCS. AmpR last-resort; Puro is the mammalian marker and was avoided. |
| medium | 14148 | Replace AmpR on pAG416GPD-ccdB | Yeast Gateway dest. Counterselection is ccdB dropout, not AmpR. |
| medium | 21870 | Replace SacB on pKJ1712 | Gotcha is a figure typo near BamHI, not SacB. Catalog job is oligo clone into BamHI. |
| medium | 46569 | Replace unannotated CDS (76-2584) on pdCas9 | That interval is the unlabeled dCas9 ORF. Prompt does not say dead Cas9; inventory labels still read Cas9. Fair trap, opaque payload name. |
| medium | 60229 | Replace unannotated CDS (1459-2539) on AAV-Cre | Unlabeled Cre between NLS and HA. Prompt names Golden Gate (sgRNA slot) but the key Gibson-swaps Cre. Two different cloning jobs mixed. |
| medium | 112159 / 112168 ×2 | Replace "primary cargo" on iGABASnFR plasmids | Sensor is split across leader/Myc/TM annotations. Span is a generator invention. Dual 112168 maps differ by 3 bp (7028 vs 7025). |
| medium | 28306 | Replace tdTomato on pAAV-FLEX-tdTomato | Feature is **plus-strand** on this map, so the prompt does **not** ask to keep inversion. Catalog gotcha is an inverted ORF vs CAG. Scientist should confirm whether this map is already drawn antisense. |
| medium | 44361 | Replace mCherry (minus strand) on DIO hM3Dq | Prompt asks to keep inversion. Cargo is hM3D-mCherry fusion; replacing only mCherry may leave hM3D. |
| medium | 20297 / 20298 ×2 | Replace ChR2(H134R) (minus strand) on DIO opsins | Keeps inversion. Does not swap the fused EYFP/mCherry. Dual 20298 maps (7256 vs 7266). |
| medium | 42335 | Replace Cas9(D10A) on pX335 | Correct nickase payload. Prompt still offers Golden Gate (BbsI sgRNA slot) while the key Gibson-swaps the nuclease CDS. |
| medium | 62988 ×2 | Replace Cas9 on PX459 V2.0 (9171 vs 9172 bp) | Dual maps. Catalog job is BbsI oligo GG, key is Cas9→EGFP Gibson. Same split as other PX plasmids. |
| low | 48076 / 66070 / 50005 | Replace lacZ-alpha | Dropout, not a protein of interest. Reasonable dest-emptying task; not a cargo swap. |
| low | 65108 / 65202 | Replace superfolder GFP | YTK GFP dropout. Fair dest-clearing task; leftover Type IIS is the real gotcha. |
| low | 13775 | Replace Cre (minus strand) on pCAG-Cre | Cre is the real cargo. Strand is minus on this file; inversion wording may be map-orientation, not biology. |
| low | all 18 GG-catalog items | Prompt names Golden Gate or Gibson; canonical protocol is Gibson | Exact-reference scorer accepts any method that yields the same circle. A scientist who wants a true oligo-GG item should reject these keys. |

## Probably fine (not flagged)

Cas9→EGFP/EYFP on AAV/lenti/PX/lentiCRISPR/pX330/SaCas9/plant Cas9; EGFP↔mCherry reporter swaps (105539, 128652, 1384, 37825, 83900, 47676); MBP/SiriusGFP bacterial expression; L4440 T7–T7 insert; VSV-G on pCMV-VSV-G (8454) as an envelope swap people actually do.

## Category mix vs catalog intent

| Catalog method | n | What the draft actually tests |
| --- | ---: | --- |
| gibson | 33 | Mostly honest 2-fragment CDS swaps |
| oligo_gg | 11 | Prompt mentions GG enzyme; key is still Gibson CDS swap. Several hit AmpR/NeoR instead of the oligo slot. |
| hierarchical_gg | 4 | Dropout (GFP/lacZ) or AmpR, not 6–8-part cassette assembly |
| golden_gate | 3 | One GFP dropout (pYTK001), one mCherry dest (SE7), one CmR (pGGAselect) |
| restriction | 4 | All Gibson in the key. Two helpers used-as-is (12259/12260), pLKO AmpR, pKJ1712 SacB |

## Dual-map pairs (keep both; specify length)

26973 6236 vs 6225 (ITR 11 bp), 20298 7256 vs 7266, 112168 7028 vs 7025, 62988 9171 vs 9172. Shared inventory contains **both** files. The prompt names the bp length so the exact FASTA is identifiable. Still easy for a model to assemble the sibling map and fail.

## Live Soul Max run notes (in progress)

Host scoring needed `edlib` (`lab_bench_2` extra). The first two dual-map
iGABASnFR samples finished generation and then error'd on
`ModuleNotFoundError: edlib`. That package is now installed in the venv;
later samples should score. Those two should be **rescored from the log**,
not treated as model failures.

OpenAI `bio_policy` 400s (not a cloning error):

- 12260 psPAX2 HIV-1 gag → tdTomato
- 12259 pMD2.G VSV-G → mCherry (same request family)

Packaging-helper questions that name HIV-1 gag or VSV-G can be refused
before a protocol is produced. Flag as unscorable on this provider, not as
wrong biology.

## Suggested scientist actions

1. Reject or rewrite the **high** rows before treating scores as cloning skill.
2. On GG/oligo backbones, either drop "Golden Gate" from the prompt or replace the key with a real Type IIS oligo/part assembly.
3. On FLEX/DIO plasmids, confirm whether "keep inversion" matches the map drawing.
4. Empty backbones: replace the last-resort marker swap with an MCS/stuffer insert.
5. Leave the dual-map length wording; that is the inventory trap working as designed.
