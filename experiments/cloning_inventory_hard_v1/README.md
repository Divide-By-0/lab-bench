# Hard Addgene cloning inventory pilot

This package preserves the easier `cloning_inventory_pilot_v1` set and adds six genuinely harder underlying constructs. These are not merely prompt-redacted versions of two-fragment swaps.

| Construct | Canonical components | Inventory files |
| --- | ---: | ---: |
| TCF/LEF EGFP-P2A-PuroR reporter | 3 | 12 |
| Lentiviral mCherry with G418 selection | 4 | 12 |
| Cre-dependent tdTomato-P2A-PuroR reporter | 3 | 12 |
| Cas9-P2A-mCherry with kanamycin propagation | 5 | 12 |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | 4 | 12 |
| Guide-vector mCherry-P2A-NeoR replacement | 4 | 12 |

## What makes these harder

- No assembly method, backbone, insert source, plasmid name, or exact coordinates are disclosed.
- Each task supplies 12 accession-only GenBank files, including close architectural decoys.
- The exact products require three to five PCR-derived components.
- All six tasks require frame-sensitive coding or tag junctions; three require two coding changes, and two require reverse-orienting a bacterial marker.
- The prompts impose retained-architecture and component-count constraints so whole-vector redesign is not an equivalent answer.

The existing sequence verifier remains usable because every prompt still defines one smallest-change final construct. `validation/` contains exact circular FASTA references and annotated GenBank review references. Every base is covered by an assembly-component provenance annotation.

## Primer and enzyme inventory subset

`questions_reagent_inventory.jsonl` contains three representative tasks: the 3-component TCF/LEF reporter, 4-component two-locus lentiviral edit, and 5-component Cas9/marker edit. Each has an equal number of canonical and decoy primer stocks plus eight enzyme stocks. Primer filenames and enzyme filenames are opaque; the model must select them by inspecting `reagent_inventory.tsv` or the individual stock files. Novel primers are not permitted in these variants. Both canonical and decoy primer stocks are drawn deterministically from primer designs against the attached Addgene sequence inventory rather than random DNA strings.

Each reagent task also includes eight QC-valid plasmids sampled from the 2026 iGEM distribution kit: a promoter, RBS, terminator, three unrelated CDS parts, a fluorescent-protein decoy, and a Type IIS destination backbone. Only the circular GenBank files and a filtered `igem_inventory.tsv` are attached. The FASTA copies are sequence-identical and therefore redundant; the full 573-record manifests and raw JSON are useful for dataset curation but unnecessarily large for an individual model task. The filtered TSV preserves the useful plate, role, assembly, flanking-overhang, resistance, and QC metadata. The source kit does not provide nucleotide coordinates for the named parts, so the model still has to inspect the whole-plasmid sequence.

The reagent-inventory prompt adds the following rule to the corresponding question shown below:

> Use only stocked `primer-*.txt` files as PCR primers. Some are decoys. If an enzyme-based operation is selected, use only a stocked `enzyme-*.txt`; enzyme use is optional for methods that do not require it. Eight QC-valid `igem-*.gbk` plasmids listed in `igem_inventory.tsv` are also available.

## Reagent-inventory questions for review (3 of 6)

These are the exact task-specific question texts from `questions.jsonl`; the shared protocol-syntax suffix is not repeated here.

### TCF/LEF EGFP-P2A-PuroR reporter

Build a beta-catenin/TCF-responsive mammalian reporter that produces EGFP and puromycin resistance as separate proteins from one transcript. Select all starting molecules by inspecting the attached GenBank sequences and annotations; the inventory filenames deliberately provide only accession numbers.

Available inventory:
- `addgene-12456.gbk`
- `addgene-13031.gbk`
- `addgene-13770.gbk`
- `addgene-19319.gbk`
- `addgene-21915.gbk`
- `addgene-27705.gbk`
- `addgene-42230.gbk`
- `addgene-48138.gbk`
- `addgene-52961.gbk`
- `addgene-54856.gbk`
- `addgene-69929.gbk`
- `addgene-1864.gbk`

Functional and construction constraints:
- retain an eight-site TCF/LEF response array, its minimal promoter, and its native translation-initiation context.
- replace firefly luciferase with one continuous EGFP-P2A-PuroR open reading frame.
- omit the EGFP stop codon, preserve the P2A reading frame, and place the only coding-region stop after PuroR.
- retain the response vector's SV40 polyadenylation signal and bacterial propagation elements.
- use sequence present in the inventory and no more than three PCR-derived assembly components.

Do not synthesize a complete coding region in primer tails. Choose any supported assembly method, but preserve the selected backbone outside the required local edits. The final circular construct, including its junction sequences, reading frames, and retained architecture, will be assessed.

### Lentiviral mCherry with G418 selection

Build a third-generation lentiviral transfer vector that expresses mCherry and uses independent G418/neomycin selection. Select all starting molecules by inspecting the attached GenBank sequences and annotations; the inventory filenames deliberately provide only accession numbers.

Available inventory:
- `addgene-1864.gbk`
- `addgene-10878.gbk`
- `addgene-12259.gbk`
- `addgene-12260.gbk`
- `addgene-12456.gbk`
- `addgene-13031.gbk`
- `addgene-13770.gbk`
- `addgene-19319.gbk`
- `addgene-21915.gbk`
- `addgene-27705.gbk`
- `addgene-48138.gbk`
- `addgene-52961.gbk`

Functional and construction constraints:
- start from an inventory transfer vector that already contains the required LTR, Psi, RRE, and cPPT/CTS elements.
- replace its green reporter with mCherry while preserving the existing downstream fusion/stop context.
- independently replace its hPGK-driven puromycin-resistance coding region with a complete NeoR/KanR coding region.
- remove all EGFP and PuroR coding sequence while retaining the original promoters, lentiviral cis elements, and bacterial propagation elements.
- make exactly the two local coding-region edits and use no more than four PCR-derived assembly components.

Do not synthesize a complete coding region in primer tails. Choose any supported assembly method, but preserve the selected backbone outside the required local edits. The final circular construct, including its junction sequences, reading frames, and retained architecture, will be assessed.

### Cas9-P2A-mCherry with kanamycin propagation

Build a nonviral mammalian CRISPR plasmid that coexpresses Cas9 and mCherry as separate proteins and propagates under kanamycin selection. Select all starting molecules by inspecting the attached GenBank sequences and annotations; the inventory filenames deliberately provide only accession numbers.

Available inventory:
- `addgene-12456.gbk`
- `addgene-13031.gbk`
- `addgene-13770.gbk`
- `addgene-19319.gbk`
- `addgene-27705.gbk`
- `addgene-37237.gbk`
- `addgene-40315.gbk`
- `addgene-42230.gbk`
- `addgene-48138.gbk`
- `addgene-52961.gbk`
- `addgene-54856.gbk`
- `addgene-69929.gbk`

Functional and construction constraints:
- start from a CAG-Cas9 inventory backbone that initially has no linked fluorescent reporter or mammalian selectable marker.
- retain its U6 guide-RNA cassette, 3xFLAG/SV40-NLS-Cas9-nucleoplasmin-NLS reading frame, and bGH polyadenylation signal.
- append P2A followed by complete mCherry immediately after the terminal Cas9 NLS, with no stop before P2A and one stop after mCherry.
- replace the bacterial AmpR coding region with a complete, correctly oriented KanR coding region while retaining the original bacterial promoter and origin.
- use sequence present in the inventory and no more than five PCR-derived assembly components.

Do not synthesize a complete coding region in primer tails. Choose any supported assembly method, but preserve the selected backbone outside the required local edits. The final circular construct, including its junction sequences, reading frames, and retained architecture, will be assessed.

## Regeneration

```bash
uv run --extra lab_bench_2 python tools/generate_cloning_inventory_hard_questions.py \
  --input-dir /path/to/addgene-genbank-files \
  --igem-dir /path/to/igem-distribution-kit-2026 \
  --output experiments/cloning_inventory_hard_v1
```

## Running

```bash
inspect eval src/lab_bench_2/lab_bench_2.py@lab_bench_2 \
  -T tags=cloning -T mode=file -T solver=agentic \
  -T dataset_path="$PWD/experiments/cloning_inventory_hard_v1/questions.jsonl" \
  --model openai/gpt-5.6-sol --reasoning-effort max
```

To run the three-task primer/enzyme inventory subset, replace `questions.jsonl` above with `questions_reagent_inventory.jsonl`.
