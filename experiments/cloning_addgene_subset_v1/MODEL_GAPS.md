# Model gap table — Addgene CloningQA 55

Exact-circle scorer (simulator v2, similarity ≥ 0.95). A pass is **not**
catalog-method skill: several GG/stuffer backbones still pass as CDS swaps.

| Model | Cap | Config | Score |
| --- | --- | --- | ---: |
| GPT-5.6 Sol Max | 100k novel | reasoning max / Inspect xhigh, agentic file | **41/55** (10 sequence fail, 4 OpenAI `bio_policy`) |
| Gemini 2.5 Pro | 500k novel | reasoning default, **only the 14 Sol non-passes** | **4/14** recovered |
| Gemini 3.7 Flash | 1M novel intended | reasoning high, agentic file, all 55 queued | **28/32** scored (4 sequence fail); 23 unrun |

Gemini 3.7 Flash was interrupted by Google AI Studio **monthly spend cap**
(`429 RESOURCE_EXHAUSTED`), not by Inspect `--cost-limit 1.0`. Trace:
`experiments/traces/gemini37flash_addgene_subset_55tasks_1M_high_cancelled32.eval`.
Resume after raising https://ai.studio/spend :

```bash
uv run inspect eval-retry \
  experiments/traces/gemini37flash_addgene_subset_55tasks_1M_high_cancelled32.eval
```

The three iGABASnFR Sol samples (112159, both 112168 maps) are **passes**
(0.999 after host-edlib rescore), not model misses.

## Per-task annotations

Legend: **P** pass; **F** sequence fail; **B** provider bio-policy (no
protocol); **Cap** Google monthly spend cap (no scored protocol);
**—** not run; *wrong-job* means the generated prompt is a marker/CDS
swap on a GG/stuffer/helper backbone (see `MANUAL_REVIEW.md`).

| Addgene | Backbone | Swap | Catalog | Sol 100k | Gemini 2.5 Pro 500k | Gemini 3.7 Flash 1M | Why a miss is interesting |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 104588 | pAAV-EFS-SpCas9 | Cas9→EGFP | gibson | P | — | **P 1.000** | honest CDS swap |
| 105539 | pAAV.hSyn.eGFP | EGFP→mCherry | gibson | P | — | **P 1.000** | LAB-Bench attachment plasmid |
| 10878 | pLKO.1 | AmpR→EYFP | restriction | P | — | **P 1.000** | *wrong-job* stuffer; Sol still solves AmpR |
| 112159 | iGABASnFR | cargo→EGFP | gibson | P | — | **P 1.000** | edlib host hole, then 0.999 |
| 112168 | FLEX iGABASnFR 7028 | cargo→EGFP | gibson | P | — | **P 1.000** | dual map; edlib hole then pass |
| 112168 | FLEX iGABASnFR 7025 | cargo→EGFP | gibson | P | — | **P 1.000** | dual map; edlib hole then pass |
| 12259 | pMD2.G | VSV-G→mCherry | restriction | B | **P 0.993** | **P 1.000** | OpenAI refuse; both Geminis allowed |
| 12260 | psPAX2 | HIV-1 gag→tdTomato | restriction | B | F | **P 1.000** | OpenAI refuse; 2.5 Pro wrong; 3.7 Flash recovered |
| 128034 | pcDNA3.1-HA | AmpR→mCherry | gibson | P | — | **P 1.000** | empty HA backbone, last-resort marker |
| 128652 | pLVX-EGFP | EGFP→mCherry | gibson | P | — | **P 1.000** | |
| 13775 | pCAG-Cre | Cre→EGFP | gibson | P | — | **P 1.000** | minus-strand cargo |
| 1384 | pYES2/25Q | EGFP→mCherry | gibson | P | — | **P 1.000** | |
| 14148 | pAG416GPD-ccdB | AmpR→EGFP | gibson | P | — | **P 1.000** | Gateway dest; ccdB not the slot |
| 1654 | L4440 | T7–T7 insert→mCherry | gibson | P | — | **P 1.000** | MCS emptying |
| 17398 | pENTR1A no ccdB | KanR→EYFP | gibson | P | — | **P 1.000** | Gateway entry |
| 1764 | pBABE-puro | AmpR→mCherry | gibson | P | — | **P 1.000** | empty retroviral backbone |
| 181752 | pCMV-MMLVgag-Cas9 | Cas9→EYFP | gibson | F 0.606 | F | **F 0.611** | fusion/wrap; still a PX lookalike |
| 195714 | pGGAselect | CmR→EGFP | golden_gate | P | — | **P 1.000** | *wrong-job* 24-part dest; Sol solves CmR |
| 20297 | DIO ChR2-mCherry | ChR2→EGFP | gibson | P | — | **P 1.000** | keep inversion |
| 20298 | DIO ChR2-EYFP 7256 | ChR2→EGFP | gibson | P | — | **P 1.000** | dual map |
| 20298 | DIO ChR2-EYFP 7266 | ChR2→EGFP | gibson | F PCR | **P 0.952** | **P 1.000** | 14 bp primer vs 15 bp pydna limit |
| 21870 | pKJ1712 | SacB→EGFP | restriction | P | — | **P 1.000** | BamHI oligo gotcha, not SacB |
| 23007 | pCMV-M1 | NeoR→tdTomato | gibson | F 0.747 | F | **F 0.747** | *wrong-job* marker; same pcDNA3.1 miss |
| 26973 | hSyn-ChR2 6225 | ChR2→EGFP | gibson | F 0.878 | F | **F PCR** | extra MCS flanks, 15 bp anneal miss |
| 26973 | hSyn-ChR2 6236 | ChR2→EGFP | gibson | F 0.878 | **P 1.000** | **P 1.000** | sibling ITR-length map recovered |
| 28306 | FLEX-tdTomato | tdTomato→EGFP | gibson | P | — | **P 1.000** | plus-strand on this map |
| 29656 | pET MBP | MBP→EGFP | gibson | P | — | **P 1.000** | |
| 29663 | pET SiriusGFP | SiriusGFP→mCherry | gibson | P | — | **P 1.000** | |
| 37825 | AAV-CAG-GFP | EGFP→mCherry | gibson | F 0.660 | F | **F 0.660** | sibling reporter 105539 |
| 41819 | gRNA_GFP-T1 | NeoR→EYFP | oligo_gg | P | — | **P 1.000** | *wrong-job* BbsI oligo slot |
| 42230 | pX330 | Cas9→EGFP | oligo_gg | F 0.885 | F | **P 1.000** | Sol/2.5 Pro used PX459; 3.7 Flash recovered |
| 42335 | pX335 nickase | Cas9(D10A)→EYFP | oligo_gg | P | — | Cap | spend cap mid-sample |
| 44361 | DIO hM3Dq-mCherry | mCherry→EYFP | gibson | P | — | **P 1.000** | fusion cargo |
| 46569 | pdCas9 | unlabeled dCas9→tdTomato | gibson | P | — | Cap | spend cap mid-sample |
| 47676 | pGoldenGate-SE7 | mCherry→EGFP | golden_gate | P | — | Cap | spend cap mid-sample |
| 48076 | pICH86988 | lacZα→tdTomato | hierarchical_gg | P | — | Cap | not started |
| 48138 | PX458 | Cas9→EGFP | oligo_gg | F 0.938 | F | Cap | origin-wrapping Cas9; cliff under 0.95 |
| 48856 | pGGA000 | AmpR→mCherry | oligo_gg | P | — | Cap | *wrong-job* GreenGate entry |
| 49535 | lentiCRISPR | Cas9→EGFP | oligo_gg | P | — | Cap | not started |
| 50005 | pUC19 | lacZα→EYFP | hierarchical_gg | P | — | Cap | dest emptying |
| 51776 | pMDC32B | StaA→EYFP | gibson | P | — | Cap | *wrong-job* stability protein |
| 52961 | lentiCRISPR v2 | Cas9→EYFP | oligo_gg | P | — | Cap | not started |
| 52962 | lentiCas9-Blast | Cas9→EYFP | gibson | P | — | Cap | not started |
| 52963 | lentiGuide-Puro | AmpR→EYFP | oligo_gg | P | — | Cap | *wrong-job* BsmBI oligo filler |
| 59176 | p201H Cas9 | Cas9→EYFP | gibson | P | — | Cap | plant Cas9 |
| 60229 | AAV-Cre | unlabeled Cre→mCherry | oligo_gg | P | — | Cap | GG prompt, Gibson Cre swap |
| 61591 | pX601 SaCas9 | SaCas9→EGFP | oligo_gg | P | — | Cap | not started |
| 62988 | PX459 V2.0 9171 | Cas9→EGFP | oligo_gg | P | — | Cap | dual map |
| 62988 | PX459 V2.0 9172 | Cas9→EGFP | oligo_gg | P | — | Cap | dual map |
| 65108 | pYTK001 | sfGFP→mCherry | golden_gate | P | — | Cap | YTK GFP dropout |
| 65202 | pYTK095 | sfGFP→mCherry | hierarchical_gg | F 0.801 | F | Cap | sibling pYTK001 |
| 66070 | DVK_FG | lacZα→mCherry | hierarchical_gg | P | — | Cap | dest emptying |
| 83900 | AAV-mDlx-GFP | EGFP→mCherry | gibson | F 0.851 | F | Cap | ITR gotcha; sibling 105539 |
| 8454 | pCMV-VSV-G | VSV-G→tdTomato | gibson | B | **P 0.993** | Cap | OpenAI refuse; Gemini 2.5 Pro allowed |
| 8455 | pCMV-dR8.2 | HIV-1 gag→EYFP | gibson | B | F 0.67 | Cap | OpenAI refuse; Gemini 2.5 Pro still wrong |

## Where models fall short

1. **Sibling-plasmid inventory** (181752, 37825, 23007, 26973 6225 bp still
   fail on Gemini 3.7 Flash; 65202, 83900, 48138 unrun): the prompt says
   “one of our X plasmids.” Extra tokens do not fix picking the wrong file.
   **42230 pX330 is the exception** — Sol and Gemini 2.5 Pro used PX459
   (0.885 / fail); Gemini 3.7 Flash scored **P 1.000**.
2. **0.95 cliff** (PX458 48138 at 0.938 on Sol): origin-wrapping Cas9. A
   family scorer (v3) would likely pass; v2 exact-circle does not. Unrun
   on Gemini 3.7 Flash.
3. **PCR 15 bp anneal** (20298 7266): Sol’s 14 bp primer died; both Geminis
   used a valid primer and passed. 26973 6225 still PCR-fails on 3.7 Flash.
4. **OpenAI bio_policy** (12259, 12260, 8454, 8455): packaging helpers
   naming HIV-1 gag / VSV-G. Gemini 3.7 Flash recovered **both** 12259 and
   12260 at 1.000. 8454/8455 were not reached.
5. **Wrong-job passes** (pLKO AmpR, lentiGuide AmpR, pGGAselect CmR,
   pGGA000 AmpR, gRNA NeoR): models can do the generated CDS swap even
   when the catalog job is oligo GG or a stuffer. Do not read those as
   GG skill.

Do **not** treat the 23 Cap cells as model fails. They are Google spend-cap
interruptions. The real Gemini 3.7 Flash misses among scored tasks are
181752, 23007, 26973 6225, and 37825.
