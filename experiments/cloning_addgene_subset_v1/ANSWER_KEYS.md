# Scientist answer keys — Addgene subset cloning drafts

Drop this file with the JSONL. Each row is a two-fragment CDS swap.
Canonical protocols are Gibson and were checked with cloning simulator
v2 against the exact circular FASTA in `validation/`. Another
biologically valid architecture may still fail the exact-reference
scorer. Golden Gate backbones are included as destinations; the
verified key is still the Gibson product of the same CDS swap.

| # | Addgene | Backbone | Replace | Donor CDS (file) | Catalog method | bp | Verified |
| --- | ---: | --- | --- | --- | --- | ---: | --- |
| 1 | 104588 | pAAV-EFS-SpCas9 | Cas9 | EGFP (`addgene-plasmid-105539-sequence-457689.gbk`) | gibson | 4037 | yes |
| 2 | 105539 | pAAV.hSyn.eGFP.WPRE.bGH | EGFP | mCherry (`addgene-plasmid-47676-sequence-68092.gbk`) | gibson | 5122 | yes |
| 3 | 10878 | pLKO.1 - TRC cloning vector | AmpR | EYFP (`addgene-plasmid-26973-sequence-199313.gbk`) | restriction | 8760 | yes |
| 4 | 112159 | pAAV.hSynap.iGABASnFR | primary cargo | EGFP (`addgene-plasmid-83900-sequence-227749.gbk`) | gibson | 4830 | yes |
| 5 | 112168 | pAAV.CAG-FLEX.iGABASnFR.F102Y.Y137L (7028 bp map) | primary cargo | EGFP (`addgene-plasmid-128652-sequence-320737.gbk`) | gibson | 5804 | yes |
| 6 | 112168 | pAAV.CAG-FLEX.iGABASnFR.F102Y.Y137L (7025 bp map) | primary cargo | EGFP (`addgene-plasmid-128652-sequence-320737.gbk`) | gibson | 5801 | yes |
| 7 | 12259 | pMD2.G | VSV-G | mCherry (`addgene-plasmid-47676-sequence-68092.gbk`) | restriction | 4997 | yes |
| 8 | 12260 | psPAX2 | HIV-1 gag | tdTomato (`addgene-plasmid-28306-sequence-162239.gbk`) | restriction | 10640 | yes |
| 9 | 128034 | pcDNA3.1-HA | AmpR | mCherry (`addgene-plasmid-47676-sequence-68092.gbk`) | gibson | 5370 | yes |
| 10 | 128652 | pLVX-EGFP-IRES-puro | EGFP | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 8902 | yes |
| 11 | 13775 | pCAG-Cre | Cre | EGFP (`addgene-plasmid-83900-sequence-227749.gbk`) | gibson | 5597 | yes |
| 12 | 1384 | pYES2/25Q | EGFP | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 6666 | yes |
| 13 | 14148 | pAG416GPD-ccdB | AmpR | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | gibson | 7336 | yes |
| 14 | 1654 | L4440 | region between the T7 promoters | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 3316 | yes |
| 15 | 17398 | pENTR1A no ccDB (w48-1) | KanR | EYFP (`addgene-plasmid-20298-sequence-191904.gbk`) | gibson | 2204 | yes |
| 16 | 1764 | pBABE-puro | AmpR | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 4936 | yes |
| 17 | 181752 | pCMV-MMLVgag-3xNES-Cas9 | Cas9 | EYFP (`addgene-plasmid-26973-sequence-199313.gbk`) | gibson | 7402 | yes |
| 18 | 195714 | pGGAselect | CmR | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | golden_gate | 2280 | yes |
| 19 | 20297 | pAAV-EF1a-double floxed-hChR2(H134R)-mCherry-WPRE-HGHpA | ChR2(H134R) | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | gibson | 7034 | yes |
| 20 | 20298 | pAAV-EF1a-double floxed-hChR2(H134R)-EYFP-WPRE-HGHpA (7256 bp map) | ChR2(H134R) | EGFP (`addgene-plasmid-83900-sequence-227749.gbk`) | gibson | 7049 | yes |
| 21 | 20298 | pAAV-EF1a-double floxed-hChR2(H134R)-EYFP-WPRE-HGHpA (7266 bp map) | ChR2(H134R) | EGFP (`addgene-plasmid-83900-sequence-227749.gbk`) | gibson | 7059 | yes |
| 22 | 21870 | pKJ1712 | SacB | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | restriction | 8021 | yes |
| 23 | 23007 | pCMV-M1 | NeoR/KanR | tdTomato (`addgene-plasmid-28306-sequence-162239.gbk`) | gibson | 4631 | yes |
| 24 | 26973 | pAAV-hSyn-hChR2(H134R)-EYFP (6236 bp map) | ChR2(H134R) | EGFP (`addgene-plasmid-128652-sequence-320737.gbk`) | gibson | 6029 | yes |
| 25 | 26973 | pAAV-hSyn-hChR2(H134R)-EYFP (6225 bp map) | ChR2(H134R) | EGFP (`addgene-plasmid-128652-sequence-320737.gbk`) | gibson | 6018 | yes |
| 26 | 28306 | pAAV-FLEX-tdTomato | tdTomato | EGFP (`addgene-plasmid-83900-sequence-227749.gbk`) | gibson | 5734 | yes |
| 27 | 29656 | pET His6 MBP TEV LIC cloning vector (1M) | MBP | EGFP (`addgene-plasmid-105539-sequence-457689.gbk`) | gibson | 6081 | yes |
| 28 | 29663 | pET His6 GFP TEV LIC cloning vector (1GFP) | SiriusGFP | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 6069 | yes |
| 29 | 37825 | pAAV-CAG-GFP | EGFP | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 5430 | yes |
| 30 | 41819 | gRNA_GFP-T1 | NeoR/KanR | EYFP (`addgene-plasmid-20298-sequence-9545.gbk`) | oligo_gg | 3898 | yes |
| 31 | 42230 | pX330-U6-Chimeric_BB-CBh-hSpCas9 | Cas9 | EGFP (`addgene-plasmid-128652-sequence-320737.gbk`) | oligo_gg | 5123 | yes |
| 32 | 42335 | pX335-U6-Chimeric_BB-CBh-hSpCas9n(D10A) | Cas9(D10A) | EYFP (`addgene-plasmid-20298-sequence-191904.gbk`) | oligo_gg | 5049 | yes |
| 33 | 44361 | pAAV-hSyn-DIO-hM3D(Gq)-mCherry | mCherry | EYFP (`addgene-plasmid-26973-sequence-12776.gbk`) | gibson | 7324 | yes |
| 34 | 46569 | pdCas9 | unannotated CDS (76-2584) | tdTomato (`addgene-plasmid-28306-sequence-162239.gbk`) | gibson | 8249 | yes |
| 35 | 47676 | pGoldenGate-SE7 | mCherry | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | golden_gate | 7260 | yes |
| 36 | 48076 | pICH86988 | lacZ-alpha | tdTomato (`addgene-plasmid-28306-sequence-162239.gbk`) | hierarchical_gg | 10185 | yes |
| 37 | 48138 | pSpCas9(BB)-2A-GFP (PX458) | Cas9 | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | oligo_gg | 5907 | yes |
| 38 | 48856 | pGGA000 | AmpR | mCherry (`addgene-plasmid-47676-sequence-68092.gbk`) | hierarchical_gg | 3599 | yes |
| 39 | 49535 | lentiCRISPR | Cas9 | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | oligo_gg | 10069 | yes |
| 40 | 50005 | pUC19 | lacZ-alpha | EYFP (`addgene-plasmid-26973-sequence-199313.gbk`) | gibson | 3082 | yes |
| 41 | 51776 | pMDC32B-AtMIR390a-B/c | pVS1 StaA | EYFP (`addgene-plasmid-26973-sequence-199313.gbk`) | gibson | 12134 | yes |
| 42 | 52961 | lentiCRISPR v2 | Cas9 | EYFP (`addgene-plasmid-20298-sequence-191904.gbk`) | oligo_gg | 11489 | yes |
| 43 | 52962 | lentiCas9-Blast | Cas9 | EYFP (`addgene-plasmid-20298-sequence-9545.gbk`) | gibson | 9475 | yes |
| 44 | 52963 | lentiGuide-Puro | AmpR | EYFP (`addgene-plasmid-26973-sequence-12776.gbk`) | oligo_gg | 10042 | yes |
| 45 | 59176 | p201H Cas9 | Cas9 | EYFP (`addgene-plasmid-20298-sequence-191904.gbk`) | gibson | 11162 | yes |
| 46 | 60229 | AAV:ITR-U6-sgRNA(backbone)-pCBh-Cre-WPRE-hGHpA-ITR | unannotated CDS (1459-2539) | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | oligo_gg | 5992 | yes |
| 47 | 61591 | pX601-AAV-CMV::NLS-SaCas9-NLS-3xHA-bGHpA;U6::BsaI-sgRNA | SaCas9 | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | oligo_gg | 5010 | yes |
| 48 | 62988 | pSpCas9(BB)-2A-Puro (PX459) V2.0 (9171 bp map) | Cas9 | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | oligo_gg | 5790 | yes |
| 49 | 62988 | pSpCas9(BB)-2A-Puro (PX459) V2.0 (9172 bp map) | Cas9 | EGFP (`addgene-plasmid-37825-sequence-448204.gbk`) | oligo_gg | 5791 | yes |
| 50 | 65108 | pYTK001 | superfolder GFP | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | golden_gate | 2673 | yes |
| 51 | 65202 | pYTK095 | superfolder GFP | mCherry (`addgene-plasmid-47676-sequence-68092.gbk`) | hierarchical_gg | 2903 | yes |
| 52 | 66070 | DVK_FG | lacZ-alpha | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | hierarchical_gg | 3118 | yes |
| 53 | 83900 | pAAV-mDlx-GFP-Fishell-1 | EGFP | mCherry (`addgene-plasmid-44361-sequence-148598.gbk`) | gibson | 5439 | yes |
| 54 | 8454 | pCMV-VSV-G | VSV-G | tdTomato (`addgene-plasmid-28306-sequence-162239.gbk`) | gibson | 6402 | yes |
| 55 | 8455 | pCMV-dR8.2 dvpr | HIV-1 gag | EYFP (`addgene-plasmid-20298-sequence-191904.gbk`) | gibson | 12597 | yes |

## Canonical protocols

### 104588 `679b8681-90f9-5c96-834f-20606ab0fa6f`

**File:** `addgene-plasmid-104588-sequence-200932.gbk`

PCR-amplify the addgene-plasmid-104588-sequence-200932.gbk backbone outside Cas9 (1131:5232) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-105539-sequence-457689.gbk.

- Blue-flame AAV transfer plasmid; NAR 2025 Table S4 marks a 5' ITR 11-nt C-C' loss versus the depositor map.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-104588-sequence-200932.gbk, "AGCCCCAAGAAGAAGAGA", "GGACGCTTCGACCTTGCG"),
    pcr(addgene-plasmid-105539-sequence-457689.gbk, "AAAAAGCGCAAGGTCGAAGCGTCCATGGTGAGCAAGGGCGAG", "CACCTTTCTCTTCTTCTTGGGGCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 105539 `68648490-63d2-5b52-bdae-535e91762176`

**File:** `addgene-plasmid-105539-sequence-457689.gbk`

PCR-amplify the addgene-plasmid-105539-sequence-457689.gbk backbone outside EGFP (943:1663) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-47676-sequence-68092.gbk.

- The LAB-Bench cloning cache has also contained a '(1)' copy of this GBK next to the official attachment.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-105539-sequence-457689.gbk, "AGCGGCCGCAAGCTTATC", "GGTGGCGACCGGTGGATC"),
    pcr(addgene-plasmid-47676-sequence-68092.gbk, "AGCAAGGATCCACCGGTCGCCACCATGGTGAGCAAGGGCGAG", "ATTATCGATAAGCTTGCGGCCGCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 10878 `7f080cdb-c7cd-56aa-9ccf-77a19e3c2812`

**File:** `addgene-plasmid-10878-sequence-438456.gbk`

PCR-amplify the addgene-plasmid-10878-sequence-438456.gbk backbone outside AmpR (946:1807) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-26973-sequence-199313.gbk.

Inverted cargo: replacement is reverse-complemented.

- The TRC backbone is not empty: a 1.9 kb stuffer sits between AgeI and EcoRI. A digest that 'looks linearized' can still be uncut stuffer plasmid.
- SnapGene maps often stack an ORF annotation on top of the true CDS for the same stretch of DNA.
- pLannotate found 171,828 non-canonical part instances across 51,384 fully sequenced Addgene plasmids, including AmpR and origin variants still given the canonical name.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-10878-sequence-438456.gbk, "ACTCTTCCTTTTTCAATA", "CTGTCAGACCAAGTTTAC"),
    pcr(addgene-plasmid-26973-sequence-199313.gbk, "ATATGAGTAAACTTGGTCTGACAGTTACTTGTACAGCTCGTC", "CAATAATATTGAAAAAGGAAGAGTATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 112159 `fb8ec8f8-bf2e-57e8-a676-a290398c6083`

**File:** `addgene-plasmid-112159-sequence-424312.gbk`

PCR-amplify the addgene-plasmid-112159-sequence-424312.gbk backbone outside primary cargo (684:2628) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-83900-sequence-227749.gbk.

- NAR 2025: Addgene sequencing is grossly different in the ITR relative to the depositor reference.
- NAR 2025: backbone of 112159 and 112173 also appear flipped versus the depositor maps. The live sequences page now shows only an Addgene-verified full map.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-112159-sequence-424312.gbk, "TAGAAGCTTATCGATAAT", "GGGATCCTTGCTAGCAGC"),
    pcr(addgene-plasmid-83900-sequence-227749.gbk, "ATTCAAGCTGCTAGCAAGGATCCCATGGTGAGCAAGGGCGAG", "AGGTTGATTATCGATAAGCTTCTATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 112168 `a3b91021-c3ad-5faa-b0da-027e3c9c6ab9`

**File:** `addgene-plasmid-112168-sequence-211213.gbk`

PCR-amplify the addgene-plasmid-112168-sequence-211213.gbk backbone outside primary cargo (1332:3276) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-128652-sequence-320737.gbk.

- Same study as 112159. NAR 2025 reports the ITR sequences match, unlike siblings 112159/112173, but the two full maps still differ by 3 bp.
- FLEX cassette: the sensor ORF starts inverted.
- Public depositor-full and addgene-full maps both exist.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-112168-sequence-211213.gbk, "TAGGATATCGGATCCGCT", "GATATCACCGGTGGTACC"),
    pcr(addgene-plasmid-128652-sequence-320737.gbk, "ACTAGTGGTACCACCGGTGATATCATGGTGAGCAAGGGCGAG", "AGTGCTAGCGGATCCGATATCCTATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 112168 `43c9cd83-95ca-533d-8ce2-fd7f1d4cdd78`

**File:** `addgene-plasmid-112168-sequence-213676.gbk`

PCR-amplify the addgene-plasmid-112168-sequence-213676.gbk backbone outside primary cargo (1332:3276) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-128652-sequence-320737.gbk.

- Same study as 112159. NAR 2025 reports the ITR sequences match, unlike siblings 112159/112173, but the two full maps still differ by 3 bp.
- FLEX cassette: the sensor ORF starts inverted.
- Public depositor-full and addgene-full maps both exist.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-112168-sequence-213676.gbk, "TAGGATATCGGATCCGCT", "GATATCACCGGTGGTACC"),
    pcr(addgene-plasmid-128652-sequence-320737.gbk, "ACTAGTGGTACCACCGGTGATATCATGGTGAGCAAGGGCGAG", "AGTGCTAGCGGATCCGATATCCTATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 12259 `21df0235-3fa8-55bf-af95-9697e355fb30`

**File:** `addgene-plasmid-12259-sequence-443804.gbk`

PCR-amplify the addgene-plasmid-12259-sequence-443804.gbk backbone outside VSV-G (1258:2794) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-47676-sequence-68092.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-12259-sequence-443804.gbk, "CTCAAATCCTGCACAACA", "AGTGTCAGAATTCAGATC"),
    pcr(addgene-plasmid-47676-sequence-68092.gbk, "ACGTGAGATCTGAATTCTGACACTATGGTGAGCAAGGGCGAG", "AGAATCTGTTGTGCAGGATTTGAGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 12260 `18dfe2b9-1cdc-51cb-a862-21819ff564aa`

**File:** `addgene-plasmid-12260-sequence-467229.gbk`

PCR-amplify the addgene-plasmid-12260-sequence-467229.gbk backbone outside HIV-1 gag (1808:3311) and Gibson-assemble it to the complete tdTomato CDS from addgene-plasmid-28306-sequence-162239.gbk.

- 12259 is pMD2.G (VSV-G). 12260 is psPAX2 (gag/pol). The ids are consecutive and both are 'packaging' in lab slang.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-12260-sequence-467229.gbk, "AGATAGGGGGGCAATTAA", "CTCTCACCAGTCGCCGCC"),
    pcr(addgene-plasmid-28306-sequence-162239.gbk, "GCGAGGGGCGGCGACTGGTGAGAGATGGTGAGCAAGGGCGAG", "CTTCCTTTAATTGCCCCCCTATCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 128034 `23417927-0db6-5649-8e45-43fcd4a1f21c`

**File:** `addgene-plasmid-128034-sequence-422971.gbk`

PCR-amplify the addgene-plasmid-128034-sequence-422971.gbk backbone outside AmpR (5387:728, wrapping the origin) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-47676-sequence-68092.gbk.

Inverted cargo: replacement is reverse-complemented.

- A common HA codon choice encodes a 3' splice site and is present in this Addgene empty backbone (cited 23 times in the EMBO J 2026 analysis).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-128034-sequence-422971.gbk, "AGCAAAAACAGGAAGGCA", "CTGTCAGACCAAGTTTAC"),
    pcr(addgene-plasmid-47676-sequence-68092.gbk, "ATATGAGTAAACTTGGTCTGACAGTTACTTGTACAGCTCGTC", "GCATTTTGCCTTCCTGTTTTTGCTATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 128652 `38184468-4180-586b-91d6-2a5b8c4602de`

**File:** `addgene-plasmid-128652-sequence-320737.gbk`

PCR-amplify the addgene-plasmid-128652-sequence-320737.gbk backbone outside EGFP (2868:3588) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

- IRES and nearby MCS sequences can carry cryptic splice sites that the map never labels (EMBO J 2026).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-128652-sequence-320737.gbk, "AAGGGTGGGCGCGCCGAC", "GGTGAAGGGGGCGGCCGC"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "GGCTCCGCGGCCGCCCCCTTCACCATGGTGAGCAAGGGCGAG", "AGCTGGGTCGGCGCGCCCACCCTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 13775 `5e24e60c-e5a7-5814-84ef-50647fbd0d49`

**File:** `addgene-plasmid-13775-sequence-418462.gbk`

PCR-amplify the addgene-plasmid-13775-sequence-418462.gbk backbone outside Cre (4073:5102) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-83900-sequence-227749.gbk.

Inverted cargo: replacement is reverse-complemented.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-13775-sequence-418462.gbk, "GGTGGCGGCTCAGAATTC", "GGACCGGTGGAACAAAAA"),
    pcr(addgene-plasmid-83900-sequence-227749.gbk, "AATAAGTTTTTGTTCCACCGGTCCTTACTTGTACAGCTCGTC", "GGCAAAGAATTCTGAGCCGCCACCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 1384 `6a0db3e8-496f-569f-b414-c180a07d70b3`

**File:** `addgene-plasmid-1384-sequence-373864.gbk`

PCR-amplify the addgene-plasmid-1384-sequence-373864.gbk backbone outside EGFP (459:1176) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

Inverted cargo: replacement is reverse-complemented.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-1384-sequence-373864.gbk, "CAGGGATCCCCCGGGCTG", "TCTAGAGGGCCGCATCAT"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "AATTACATGATGCGGCCCTCTAGATTACTTGTACAGCTCGTC", "CAACTGCAGCCCGGGGGATCCCTGATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 14148 `f3490a11-845c-55ba-bf25-2a71546cac1c`

**File:** `addgene-plasmid-14148-sequence-256237.gbk`

PCR-amplify the addgene-plasmid-14148-sequence-256237.gbk backbone outside AmpR (713:1574) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-14148-sequence-256237.gbk, "CTGTCAGACCAAGTTTAC", "ACTCTTCCTTTTTCAATA"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "CAATAATATTGAAAAAGGAAGAGTATGGTGAGCAAGGGCGAG", "ATATGAGTAAACTTGGTCTGACAGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 1654 `7874fd7b-074e-51ff-ac47-5f68b5162a29`

**File:** `addgene-plasmid-1654-sequence-422970.gbk`

PCR-amplify the addgene-plasmid-1654-sequence-422970.gbk backbone outside region between the T7 promoters (59:244) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-1654-sequence-422970.gbk, "CCTATAGTGAGTCGTATTAA", "CCTATAGTGAGTCGTATTAC"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "GCGCGTAATACGACTCACTATAGGATGGTGAGCAAGGGCGAGGA", "GAAATTAATACGACTCACTATAGGTTACTTGTACAGCTCGTCCA")
)
</protocol>
```

### 17398 `1e5b89b5-c469-54db-8e8a-f60b7b6f16ef`

**File:** `addgene-plasmid-17398-sequence-239091.gbk`

PCR-amplify the addgene-plasmid-17398-sequence-239091.gbk backbone outside KanR (744:1554) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-191904.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-17398-sequence-239091.gbk, "TCAGAATTGGTTAATTGG", "AACACCCCTTGTATTACT"),
    pcr(addgene-plasmid-20298-sequence-191904.gbk, "ATAAACAGTAATACAAGGGGTGTTATGGTGAGCAAGGGCGAG", "TTACAACCAATTAACCAATTCTGATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 1764 `ec68ca62-81ad-508a-a78a-f42462b1a7b2`

**File:** `addgene-plasmid-1764-sequence-331245.gbk`

PCR-amplify the addgene-plasmid-1764-sequence-331245.gbk backbone outside AmpR (4097:4958) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

Inverted cargo: replacement is reverse-complemented.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-1764-sequence-331245.gbk, "ACTCTTCCTTTTTCAATA", "CTGTCAGACCAAGTTTAC"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "ATATGAGTAAACTTGGTCTGACAGTTACTTGTACAGCTCGTC", "CAATAATATTGAAAAAGGAAGAGTATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 181752 `42e1e77d-9672-58cb-9ab9-83f15fd1fdfc`

**File:** `addgene-plasmid-181752-sequence-353936.gbk`

PCR-amplify the addgene-plasmid-181752-sequence-353936.gbk backbone outside Cas9 (1860:5961) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-26973-sequence-199313.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-181752-sequence-353936.gbk, "TCTGGCGGCTCAAAAAGA", "TGACCCCCCGCTGACTTT"),
    pcr(addgene-plasmid-26973-sequence-199313.gbk, "AAGCGGAAAGTCAGCGGGGGGTCAATGGTGAGCAAGGGCGAG", "GGCGGTTCTTTTTGAGCCGCCAGATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 195714 `60da4a9b-2f07-5e18-95b1-11603de46601`

**File:** `addgene-plasmid-195714-sequence-385697.gbk`

PCR-amplify the addgene-plasmid-195714-sequence-385697.gbk backbone outside CmR (592:1252) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

Inverted cargo: replacement is reverse-complemented.

- The dest is cut by BsaI, BsmBI, and BbsI. Picking the enzyme that still has sites in a fragment re-opens the product. Overhang fidelity collapses as fragment count hits 24 (Potapov 2018).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-195714-sequence-385697.gbk, "TTTAGCTTCCTTAGCTCC", "TTTTTTTAAGGCAGTTAT"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GCACCAATAACTGCCTTAAAAAAATTACTTGTACAGCTCGTC", "TTTTCAGGAGCTAAGGAAGCTAAAATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 20297 `dad145e9-9767-5bd1-806f-6b02c99d6a0f`

**File:** `addgene-plasmid-20297-sequence-354478.gbk`

PCR-amplify the addgene-plasmid-20297-sequence-354478.gbk backbone outside ChR2(H134R) (4897:5824) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

Inverted cargo: replacement is reverse-complemented.

- ChR2-mCherry starts inverted. Inventory 'mCherry' hits are on the wrong strand until Cre.
- lox2272×lox2272 recombination is ~10× weaker than loxP×loxP in FLEX plasmids (BMC Biotechnol 2018), so flip-excision is not symmetric on the map.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-20297-sequence-354478.gbk, "GGTGGCTAGCATAACTTC", "CCAGCGGCCGCCGTGAGC"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GCCCTTGCTCACGGCGGCCGCTGGTTACTTGTACAGCTCGTC", "TTATACGAAGTTATGCTAGCCACCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 20298 `0e992d74-220a-57d2-a2f4-f8c75691da67`

**File:** `addgene-plasmid-20298-sequence-191904.gbk`

PCR-amplify the addgene-plasmid-20298-sequence-191904.gbk backbone outside ChR2(H134R) (2304:3231) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-83900-sequence-227749.gbk.

Inverted cargo: replacement is reverse-complemented.

- Addgene-verified and depositor full maps both exist.
- EYFP is inverted relative to EF1a until Cre. 20297 is the mCherry twin; papers cite either id for 'DIO-ChR2'.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-20298-sequence-191904.gbk, "GGTGGCTAGCATAACTTC", "CCAGCGGCCGCCACCATG"),
    pcr(addgene-plasmid-83900-sequence-227749.gbk, "GCTCACCATGGTGGCGGCCGCTGGTTACTTGTACAGCTCGTC", "TTATACGAAGTTATGCTAGCCACCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 20298 `30b174e9-7773-503b-96a4-d94d02e0e018`

**File:** `addgene-plasmid-20298-sequence-9545.gbk`

PCR-amplify the addgene-plasmid-20298-sequence-9545.gbk backbone outside ChR2(H134R) (2313:3240) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-83900-sequence-227749.gbk.

Inverted cargo: replacement is reverse-complemented.

- Addgene-verified and depositor full maps both exist.
- EYFP is inverted relative to EF1a until Cre. 20297 is the mCherry twin; papers cite either id for 'DIO-ChR2'.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-20298-sequence-9545.gbk, "GGTGGCTAGCATAACTTC", "CCAGCGGCCGCCACCATG"),
    pcr(addgene-plasmid-83900-sequence-227749.gbk, "GCTCACCATGGTGGCGGCCGCTGGTTACTTGTACAGCTCGTC", "TTATACGAAGTTATGCTAGCCACCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 21870 `558b1c9d-6e32-5ca9-a980-05676db7d220`

**File:** `addgene-plasmid-21870-sequence-10053.gbk`

PCR-amplify the addgene-plasmid-21870-sequence-10053.gbk backbone outside SacB (6832:8254) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

Inverted cargo: replacement is reverse-complemented.

- Depositor notes: Fig. S5 of the paper has GAATTCTGT-C-G near BamHI; the Addgene sequence and Fig. S1 have G. Not a functional mutation — a figure typo.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-21870-sequence-10053.gbk, "CGTTCATGTCTCCTTTTT", "AAACGCAAAAGAAAATGC"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GGATCGGCATTTTCTTTTGCGTTTTTACTTGTACAGCTCGTC", "TACATAAAAAAGGAGACATGAACGATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 23007 `318f4aad-fb00-5c9f-8285-5ae42c07443d`

**File:** `addgene-plasmid-23007-sequence-237854.gbk`

PCR-amplify the addgene-plasmid-23007-sequence-237854.gbk backbone outside NeoR/KanR (1890:2685) and Gibson-assemble it to the complete tdTomato CDS from addgene-plasmid-28306-sequence-162239.gbk.

- EMBO J 2026 scored splice motifs in a pCMV MCS taken from Addgene 23007. The live record is pCMV-M1, not an empty pCMV backbone.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-23007-sequence-237854.gbk, "GCGGGACTCTGGGGTTCG", "GCGAAACGATCCTCATCC"),
    pcr(addgene-plasmid-28306-sequence-162239.gbk, "GAGACAGGATGAGGATCGTTTCGCATGGTGAGCAAGGGCGAG", "TCATTTCGAACCCCAGAGTCCCGCTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 26973 `de7e9199-5e60-52c3-a200-b99fc5379179`

**File:** `addgene-plasmid-26973-sequence-12776.gbk`

PCR-amplify the addgene-plasmid-26973-sequence-12776.gbk backbone outside ChR2(H134R) (676:1603) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-128652-sequence-320737.gbk.

- Addgene NGS vs depositor full maps: 5' ITR lost the 11 nt C-C' segment; 3' ITR unchanged (NAR 2025 Table S4).
- Both a depositor full sequence and an Addgene-verified full sequence are public; they are not the same molecule.
- Inventory must keep both full GBKs or the ITR conflict is invisible.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-26973-sequence-12776.gbk, "CCAGCGGCCGCCACCATG", "GGTGGCTCCGGAGTCGAC"),
    pcr(addgene-plasmid-128652-sequence-320737.gbk, "TCTAGAGTCGACTCCGGAGCCACCATGGTGAGCAAGGGCGAG", "GCTCACCATGGTGGCGGCCGCTGGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 26973 `c7bb21d9-0ad3-52ca-88d0-8d04a4b89225`

**File:** `addgene-plasmid-26973-sequence-199313.gbk`

PCR-amplify the addgene-plasmid-26973-sequence-199313.gbk backbone outside ChR2(H134R) (455:1382) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-128652-sequence-320737.gbk.

- Addgene NGS vs depositor full maps: 5' ITR lost the 11 nt C-C' segment; 3' ITR unchanged (NAR 2025 Table S4).
- Both a depositor full sequence and an Addgene-verified full sequence are public; they are not the same molecule.
- Inventory must keep both full GBKs or the ITR conflict is invisible.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-26973-sequence-199313.gbk, "CCAGCGGCCGCCACCATG", "GGTGGCTCCGGAGTCGAC"),
    pcr(addgene-plasmid-128652-sequence-320737.gbk, "TCTAGAGTCGACTCCGGAGCCACCATGGTGAGCAAGGGCGAG", "GCTCACCATGGTGGCGGCCGCTGGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 28306 `d18c9a55-a279-5647-9c26-e735d3796e4b`

**File:** `addgene-plasmid-28306-sequence-162239.gbk`

PCR-amplify the addgene-plasmid-28306-sequence-162239.gbk backbone outside tdTomato (1248:2679) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-83900-sequence-227749.gbk.

- The tdTomato CDS is antisense to the CAG promoter. A feature inventory that ignores strand looks like a working reporter.
- Addgene warns this FLEX plasmid recombines during amp and packaging more than their other FLEX vectors, so a minority of particles express without Cre. The map cannot show that.
- FLEX and DIO are used interchangeably in papers. This plasmid is named FLEX; 20297 is named 'double floxed'. Both invert.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-28306-sequence-162239.gbk, "GGGGATCCCTAGTATAAC", "GGTGGCGGTACCGAATTC"),
    pcr(addgene-plasmid-83900-sequence-227749.gbk, "ATACTAGAATTCGGTACCGCCACCATGGTGAGCAAGGGCGAG", "TACGAAGTTATACTAGGGATCCCCTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 29656 `b35c97bb-e820-514d-b387-09ee3ada43ba`

**File:** `addgene-plasmid-29656-sequence-237947.gbk`

PCR-amplify the addgene-plasmid-29656-sequence-237947.gbk backbone outside MBP (334:1435) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-105539-sequence-457689.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-29656-sequence-237947.gbk, "AATGGGATCGAGGAAAAC", "AGAAGAACCATGGTGATG"),
    pcr(addgene-plasmid-105539-sequence-457689.gbk, "CATCACCATCACCATGGTTCTTCTATGGTGAGCAAGGGCGAG", "GTACAGGTTTTCCTCGATCCCATTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 29663 `18307b1d-52ee-5e25-af76-9c70cef66654`

**File:** `addgene-plasmid-29663-sequence-197189.gbk`

PCR-amplify the addgene-plasmid-29663-sequence-197189.gbk backbone outside SiriusGFP (3423:4137) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-29663-sequence-197189.gbk, "GGGATCGAGGAAAACCTG", "AGAAGAACCATGGTGATG"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "CATCACCATCACCATGGTTCTTCTATGGTGAGCAAGGGCGAG", "GAAGTACAGGTTTTCCTCGATCCCTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 37825 `1bc84a14-a2b7-5746-902a-74a866b43620`

**File:** `addgene-plasmid-37825-sequence-448204.gbk`

PCR-amplify the addgene-plasmid-37825-sequence-448204.gbk backbone outside EGFP (3596:4316) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GAATTCGATATCAAGCTT", "GGTGGCGGATCCAATTCT"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "TGGCAAAGAATTGGATCCGCCACCATGGTGAGCAAGGGCGAG", "ATCGATAAGCTTGATATCGAATTCTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 41819 `84e57a5a-69f2-5b27-8ab3-084d65e67631`

**File:** `addgene-plasmid-41819-sequence-116036.gbk`

PCR-amplify the addgene-plasmid-41819-sequence-116036.gbk backbone outside NeoR/KanR (1691:2486) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-9545.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-41819-sequence-116036.gbk, "ATTATTAACGCTTACAAT", "GCGAAACGATCCTCATCC"),
    pcr(addgene-plasmid-20298-sequence-9545.gbk, "GAGACAGGATGAGGATCGTTTCGCATGGTGAGCAAGGGCGAG", "CAGGAAATTGTAAGCGTTAATAATTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 42230 `f8daa3ef-395f-538c-a79d-b21cf89247ea`

**File:** `addgene-plasmid-42230-sequence-419908.gbk`

PCR-amplify the addgene-plasmid-42230-sequence-419908.gbk backbone outside Cas9 (1373:5474) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-128652-sequence-320737.gbk.

- pX330 is nuclease Cas9. pX335 (42335) is the D10A nickase with an almost identical map. A one-letter page mixup yields nicks instead of DSBs.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-42230-sequence-419908.gbk, "AAAAGGCCGGCGGCCACG", "GGCTGCTGGGACTCCGTG"),
    pcr(addgene-plasmid-128652-sequence-320737.gbk, "GGTATCCACGGAGTCCCAGCAGCCATGGTGAGCAAGGGCGAG", "CTTTTTCGTGGCCGCCGGCCTTTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 42335 `33f0eead-82a0-5399-a788-c4bd7a494263`

**File:** `addgene-plasmid-42335-sequence-275689.gbk`

PCR-amplify the addgene-plasmid-42335-sequence-275689.gbk backbone outside Cas9(D10A) (3864:7965) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-191904.gbk.

Inverted cargo: replacement is reverse-complemented.

- SnapGene still labels the CDS Cas9. The D10A nickase is a single residue; inventory role rules that key on 'cas9' will call this a nuclease.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-42335-sequence-275689.gbk, "GGACGCTTCGACCTTGCG", "AGCCCCAAGAAGAAGAGA"),
    pcr(addgene-plasmid-20298-sequence-191904.gbk, "CACCTTTCTCTTCTTCTTGGGGCTTTACTTGTACAGCTCGTC", "AAAAAGCGCAAGGTCGAAGCGTCCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 44361 `c53e3cb4-cd7c-52f2-ac40-d5252af486a6`

**File:** `addgene-plasmid-44361-sequence-148598.gbk`

PCR-amplify the addgene-plasmid-44361-sequence-148598.gbk backbone outside mCherry (785:1496) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-26973-sequence-12776.gbk.

Inverted cargo: replacement is reverse-complemented.

- 50474 is constitutive pAAV-hSyn-hM3D(Gq)-mCherry (no DIO). 44361 is the Cre-dependent DIO version. The names differ by one token.
- hM3D-mCherry is inverted. An inventory 'mCherry' hit is not evidence the construct is on.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "GGTGGCGACCGGGGGATC", "GGCGCGCCATAACTTCGT"),
    pcr(addgene-plasmid-26973-sequence-12776.gbk, "CATTATACGAAGTTATGGCGCGCCTTACTTGTACAGCTCGTC", "TTGAAGGATCCCCCGGTCGCCACCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 46569 `d1f9475f-7a6d-5317-95ff-722be0313d1a`

**File:** `addgene-plasmid-46569-sequence-364492.gbk`

PCR-amplify the addgene-plasmid-46569-sequence-364492.gbk backbone outside unannotated CDS (76-2584) (76:2584) and Gibson-assemble it to the complete tdTomato CDS from addgene-plasmid-28306-sequence-162239.gbk.

- Dead Cas9 (D10A and H840A). Feature labels usually still say Cas9; role rules keyed on 'cas9' will not mark it catalytically dead.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-46569-sequence-364492.gbk, "AGTATATTTTAGATGAAG", "TCCTTCAGTAACATATTT"),
    pcr(addgene-plasmid-28306-sequence-162239.gbk, "AAGGTCAAATATGTTACTGAAGGAATGGTGAGCAAGGGCGAG", "AATAATCTTCATCTAAAATATACTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 47676 `75618592-3401-52ff-a165-8df7a7b1e383`

**File:** `addgene-plasmid-47676-sequence-68092.gbk`

PCR-amplify the addgene-plasmid-47676-sequence-68092.gbk backbone outside mCherry (1676:2387) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-47676-sequence-68092.gbk, "AGCGGCCGCCCGGCTGCA", "GGATCCGACGTTGGCAGC"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "AGAAGTGCTGCCAACGTCGGATCCATGGTGAGCAAGGGCGAG", "ACGATCTGCAGCCGGGCGGCCGCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 48076 `803c2322-7def-5dba-9099-5b7c981a6723`

**File:** `addgene-plasmid-48076-sequence-69076.gbk`

PCR-amplify the addgene-plasmid-48076-sequence-69076.gbk backbone outside lacZ-alpha (7912:8236) and Gibson-assemble it to the complete tdTomato CDS from addgene-plasmid-28306-sequence-162239.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-48076-sequence-69076.gbk, "TTAAGCCAGCCCCGACAC", "AGCTGTTTCCTGTGTGAA"),
    pcr(addgene-plasmid-28306-sequence-162239.gbk, "AACAATTTCACACAGGAAACAGCTATGGTGAGCAAGGGCGAG", "TGGCGGGTGTCGGGGCTGGCTTAATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 48138 `6d535e7c-25d3-5391-940b-51698839afb5`

**File:** `addgene-plasmid-48138-sequence-418767.gbk`

PCR-amplify the addgene-plasmid-48138-sequence-418767.gbk backbone outside Cas9 (6013:826, wrapping the origin) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

- Zhang mammalian PX plasmids use BbsI. Lentiviral CRISPR plasmids from the same lab use BsmBI. Protocols copied across backbones silently fail.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-48138-sequence-418767.gbk, "AAAAGGCCGGCGGCCACG", "GGCTGCTGGGACTCCGTG"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GGTATCCACGGAGTCCCAGCAGCCATGGTGAGCAAGGGCGAG", "CTTTTTCGTGGCCGCCGGCCTTTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 48856 `15094822-9b51-56a8-9f9b-ced76c7082b8`

**File:** `addgene-plasmid-48856-sequence-71280.gbk`

PCR-amplify the addgene-plasmid-48856-sequence-71280.gbk backbone outside AmpR (200:1061) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-47676-sequence-68092.gbk.

- GreenGate modules keep BsaI sites with module-specific overhangs. An internal BsaI in a plant CDS silently drops that module (Lampropoulos 2013).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-48856-sequence-71280.gbk, "CTGTCAGACCAAGTTTAC", "ACTCTTCCTTTTTCAATA"),
    pcr(addgene-plasmid-47676-sequence-68092.gbk, "CAATAATATTGAAAAAGGAAGAGTATGGTGAGCAAGGGCGAG", "ATATGAGTAAACTTGGTCTGACAGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 49535 `89a9dc8d-990d-5887-93e5-9ab9754e6e77`

**File:** `addgene-plasmid-49535-sequence-73924.gbk`

PCR-amplify the addgene-plasmid-49535-sequence-73924.gbk backbone outside Cas9 (4470:8571) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

- Same lab, same gRNA protocol, ~10-fold lower titer than v2. Inventories that merge 'lentiCRISPR' labels hide which backbone the user actually has.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-49535-sequence-73924.gbk, "AAGCGTCCTGCTGCTACT", "GGCTGCTGGGACTCCGTG"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GGTATCCACGGAGTCCCAGCAGCCATGGTGAGCAAGGGCGAG", "TTTCTTAGTAGCAGCAGGACGCTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 50005 `ba2cfd67-c43a-5a8a-8247-c096aafc42ff`

**File:** `addgene-plasmid-50005-sequence-513490.gbk`

PCR-amplify the addgene-plasmid-50005-sequence-513490.gbk backbone outside lacZ-alpha (986:1310) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-26973-sequence-199313.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-50005-sequence-513490.gbk, "TTAAGCCAGCCCCGACAC", "AGCTGTTTCCTGTGTGAA"),
    pcr(addgene-plasmid-26973-sequence-199313.gbk, "AACAATTTCACACAGGAAACAGCTATGGTGAGCAAGGGCGAG", "TGGCGGGTGTCGGGGCTGGCTTAATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 51776 `4608588f-23c0-5691-ba90-70f939d034f5`

**File:** `addgene-plasmid-51776-sequence-80341.gbk`

PCR-amplify the addgene-plasmid-51776-sequence-80341.gbk backbone outside pVS1 StaA (4324:4954) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-26973-sequence-199313.gbk.

Inverted cargo: replacement is reverse-complemented.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-51776-sequence-80341.gbk, "GCGTTCCCCTTGCGTATT", "GTTAATGAGGTAAAGAGA"),
    pcr(addgene-plasmid-26973-sequence-199313.gbk, "TCATTTTCTCTTTACCTCATTAACTTACTTGTACAGCTCGTC", "TAAACAAATACGCAAGGGGAACGCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 52961 `512cf469-37e1-563a-8c6e-7dd96e41d68e`

**File:** `addgene-plasmid-52961-sequence-244694.gbk`

PCR-amplify the addgene-plasmid-52961-sequence-244694.gbk backbone outside Cas9 (4492:8596) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-191904.gbk.

- gRNA cloning is BsmBI (Esp3I), not the BbsI used on PX330/PX458/PX459. The unused slot is a filler, not an empty MCS.
- lentiCRISPR (49535) is the older lower-titer v1 with a different map. Papers still cite 'lentiCRISPR' for v2.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-52961-sequence-244694.gbk, "AAGCGACCTGCCGCCACA", "GGTGGCAGCGCTCTAGAA"),
    pcr(addgene-plasmid-20298-sequence-191904.gbk, "GACCGGTTCTAGAGCGCTGCCACCATGGTGAGCAAGGGCGAG", "CTTCTTTGTGGCGGCAGGTCGCTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 52962 `f078dad8-8a7f-5833-a621-4369eef4a754`

**File:** `addgene-plasmid-52962-sequence-322376.gbk`

PCR-amplify the addgene-plasmid-52962-sequence-322376.gbk backbone outside Cas9 (7199:11303) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-9545.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-52962-sequence-322376.gbk, "AAGCGACCTGCCGCCACA", "GGTGGCAGCGCTCTAGAA"),
    pcr(addgene-plasmid-20298-sequence-9545.gbk, "GACCGGTTCTAGAGCGCTGCCACCATGGTGAGCAAGGGCGAG", "CTTCTTTGTGGCGGCAGGTCGCTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 52963 `37248e38-5fbd-5844-9059-eb10c7ae1637`

**File:** `addgene-plasmid-52963-sequence-331247.gbk`

PCR-amplify the addgene-plasmid-52963-sequence-331247.gbk backbone outside AmpR (6544:7405) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-26973-sequence-12776.gbk.

- BsmBI oligo cloning, not BbsI. Pairing this backbone with a PX458 oligo design leaves the wrong overhangs.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-52963-sequence-331247.gbk, "CTGTCAGACCAAGTTTAC", "ACTCTTCCTTTTTCAATA"),
    pcr(addgene-plasmid-26973-sequence-12776.gbk, "CAATAATATTGAAAAAGGAAGAGTATGGTGAGCAAGGGCGAG", "ATATGAGTAAACTTGGTCTGACAGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 59176 `d8a0f28f-5744-5c9a-9b6a-781c56866c4c`

**File:** `addgene-plasmid-59176-sequence-120424.gbk`

PCR-amplify the addgene-plasmid-59176-sequence-120424.gbk backbone outside Cas9 (9699:13803) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-191904.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-59176-sequence-120424.gbk, "AGCAGGGCTGACCCCAAG", "GCTAGCGGTCGAGAGAGA"),
    pcr(addgene-plasmid-20298-sequence-191904.gbk, "AATCTATCTCTCTCGACCGCTAGCATGGTGAGCAAGGGCGAG", "CTTCTTCTTGGGGTCAGCCCTGCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 60229 `c5b31aee-cd7d-5389-ae89-b6988d8ba448`

**File:** `addgene-plasmid-60229-sequence-419029.gbk`

PCR-amplify the addgene-plasmid-60229-sequence-419029.gbk backbone outside unannotated CDS (1459-2539) (1459:2539) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

- Four plasmids from one deposit (60226, 60227, 60229, 60231) share the same 11-bp 5' ITR C-C' deletion versus depositor maps.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-60229-sequence-419029.gbk, "GAATTCGATATCAAGCTT", "GGTGGCACCGGTCCAACC"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "TTTTCAGGTTGGACCGGTGCCACCATGGTGAGCAAGGGCGAG", "ATCGATAAGCTTGATATCGAATTCTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 61591 `72d7080c-ce1f-52fb-982c-471d00905d6c`

**File:** `addgene-plasmid-61591-sequence-421040.gbk`

PCR-amplify the addgene-plasmid-61591-sequence-421040.gbk backbone outside SaCas9 (5134:844, wrapping the origin) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

Inverted cargo: replacement is reverse-complemented.

- sgRNA cloning is BsaI, not the BbsI/BsmBI used on SpCas9 PX and lentiCRISPR plasmids. HA-tagged SaCas9 plus ITRs on one map is easy to inventory as 'just Cas9'.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-61591-sequence-421040.gbk, "GGCTGCTGGGACTCCGTG", "AAAAGGCCGGCGGCCACG"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "CTTTTTCGTGGCCGCCGGCCTTTTTTACTTGTACAGCTCGTC", "GGTATCCACGGAGTCCCAGCAGCCATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 62988 `6a6ec1d5-1746-5698-9c84-1a3162f15579`

**File:** `addgene-plasmid-62988-sequence-456946.gbk`

PCR-amplify the addgene-plasmid-62988-sequence-456946.gbk backbone outside Cas9 (927:5028) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

- Addgene lists two Addgene-verified full sequences (9171 vs 9172 bp). Preferred download keeps only the first.
- BbsI-EcoRI screening of PX459 sgRNA clones can match the expected two-band pattern even when the oligo failed to insert or a BbsI site survived (PMC8606105).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-62988-sequence-456946.gbk, "AAAAGGCCGGCGGCCACG", "GGCTGCTGGGACTCCGTG"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GGTATCCACGGAGTCCCAGCAGCCATGGTGAGCAAGGGCGAG", "CTTTTTCGTGGCCGCCGGCCTTTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 62988 `42d532e2-09e2-599e-9fdc-93c7914b7676`

**File:** `addgene-plasmid-62988-sequence-518638.gbk`

PCR-amplify the addgene-plasmid-62988-sequence-518638.gbk backbone outside Cas9 (928:5029) and Gibson-assemble it to the complete EGFP CDS from addgene-plasmid-37825-sequence-448204.gbk.

- Addgene lists two Addgene-verified full sequences (9171 vs 9172 bp). Preferred download keeps only the first.
- BbsI-EcoRI screening of PX459 sgRNA clones can match the expected two-band pattern even when the oligo failed to insert or a BbsI site survived (PMC8606105).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-62988-sequence-518638.gbk, "AAAAGGCCGGCGGCCACG", "GGCTGCTGGGACTCCGTG"),
    pcr(addgene-plasmid-37825-sequence-448204.gbk, "GGTATCCACGGAGTCCCAGCAGCCATGGTGAGCAAGGGCGAG", "CTTTTTCGTGGCCGCCGGCCTTTTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 65108 `de285689-e1fb-5b45-9a9d-395f985ae543`

**File:** `addgene-plasmid-65108-sequence-110161.gbk`

PCR-amplify the addgene-plasmid-65108-sequence-110161.gbk backbone outside superfolder GFP (177:891) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

- Entry cloning uses BsmBI. The part is supposed to keep inward BsaI sites for the next (8-part cassette) level. Digesting the entry clone with BsaI looks like a failed insert.
- Parts with internal BsaI or BsmBI must be domesticated before MoClo; leftover sites re-cut the cassette (ACS Synth Biol 2022).


```text
<protocol>
gibson(
    pcr(addgene-plasmid-65108-sequence-110161.gbk, "TGACCAGGCATCAAATAA", "CTAGTATTTCTCCTCTTT"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "CTAGAGAAAGAGGAGAAATACTAGATGGTGAGCAAGGGCGAG", "TTCGTTTTATTTGATGCCTGGTCATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 65202 `6eac9af2-863d-5a65-826e-8ad46db270ef`

**File:** `addgene-plasmid-65202-sequence-110255.gbk`

PCR-amplify the addgene-plasmid-65202-sequence-110255.gbk backbone outside superfolder GFP (2058:2772) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-47676-sequence-68092.gbk.

- Cassette assembly is BsaI. Using BsmBI (the entry enzyme) on this acceptor does not drop the GFP dropout.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-65202-sequence-110255.gbk, "TGACCAGGCATCAAATAA", "CTAGTATTTCTCCTCTTT"),
    pcr(addgene-plasmid-47676-sequence-68092.gbk, "CTAGAGAAAGAGGAGAAATACTAGATGGTGAGCAAGGGCGAG", "TTCGTTTTATTTGATGCCTGGTCATTACTTGTACAGCTCGTC")
)
</protocol>
```

### 66070 `617f989b-12e9-5ab0-b1eb-cb4b0760f527`

**File:** `addgene-plasmid-66070-sequence-114499.gbk`

PCR-amplify the addgene-plasmid-66070-sequence-114499.gbk backbone outside lacZ-alpha (2710:303, wrapping the origin) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

Inverted cargo: replacement is reverse-complemented.

- CIDAR destinations are named by overhang pair (AE, EF, FG, GH). DVK_FG will not accept an AE-flanked part; the map looks like a generic dest.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-66070-sequence-114499.gbk, "AGCTGTTTCCTGTGTGAA", "AAGCGGCCGCGAATTCCA"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "GATTTCTGGAATTCGCGGCCGCTTTTACTTGTACAGCTCGTC", "AACAATTTCACACAGGAAACAGCTATGGTGAGCAAGGGCGAG")
)
</protocol>
```

### 83900 `534f8eec-3a1e-5687-9c55-ad5a314e5f2b`

**File:** `addgene-plasmid-83900-sequence-227749.gbk`

PCR-amplify the addgene-plasmid-83900-sequence-227749.gbk backbone outside EGFP (1029:1749) and Gibson-assemble it to the complete mCherry CDS from addgene-plasmid-44361-sequence-148598.gbk.

- NAR 2025 Table S4: 5' ITR lost the 11 nt highlighted in Fig. 3A.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-83900-sequence-227749.gbk, "AGGCGCGCCACCCCTGCA", "GGTGGCTACTAGTTTCTT"),
    pcr(addgene-plasmid-44361-sequence-148598.gbk, "GCTCTTAAGAAACTAGTAGCCACCATGGTGAGCAAGGGCGAG", "ATTCCCTGCAGGGGTGGCGCGCCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 8454 `c6d7042d-a95c-5480-b170-b569ce373f93`

**File:** `addgene-plasmid-8454-sequence-404044.gbk`

PCR-amplify the addgene-plasmid-8454-sequence-404044.gbk backbone outside VSV-G (4606:6142) and Gibson-assemble it to the complete tdTomato CDS from addgene-plasmid-28306-sequence-162239.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-8454-sequence-404044.gbk, "CTCAAATCCTGCACAACA", "AGTGTCAGAATTCCTCGA"),
    pcr(addgene-plasmid-28306-sequence-162239.gbk, "GATCCCTCGAGGAATTCTGACACTATGGTGAGCAAGGGCGAG", "AGAATCTGTTGTGCAGGATTTGAGTTACTTGTACAGCTCGTC")
)
</protocol>
```

### 8455 `9eb7e8d6-f9a2-541b-ba01-15d5edd10f7a`

**File:** `addgene-plasmid-8455-sequence-370240.gbk`

PCR-amplify the addgene-plasmid-8455-sequence-370240.gbk backbone outside HIV-1 gag (854:2357) and Gibson-assemble it to the complete EYFP CDS from addgene-plasmid-20298-sequence-191904.gbk.


```text
<protocol>
gibson(
    pcr(addgene-plasmid-8455-sequence-370240.gbk, "AGATAGGGGGGCAATTAA", "CTCTCACCAGTCGCCGCC"),
    pcr(addgene-plasmid-20298-sequence-191904.gbk, "GCGAGGGGCGGCGACTGGTGAGAGATGGTGAGCAAGGGCGAG", "CTTCCTTTAATTGCCCCCCTATCTTTACTTGTACAGCTCGTC")
)
</protocol>
```

