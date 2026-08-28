# Hard mixed-inventory cloning pilot

This package preserves the easier `cloning_inventory_pilot_v1` set and adds six genuinely harder underlying constructs. These are not merely prompt-redacted versions of two-fragment swaps.

Each JSONL record points to its complete inventory through the `files` field. Base-task inventories are under `cloning/<task-id>/`; fixed-reagent inventories are under `reagent_inventory/<task-id>/`. The runner attaches or copies every file from that directory into the model's working directory.

| Construct | Canonical components | Addgene plasmids | iGEM plasmids |
| --- | ---: | ---: | ---: |
| TCF/LEF EGFP-P2A-PuroR reporter | 3 | 12 | 8 |
| Lentiviral mCherry with G418 selection | 4 | 12 | 8 |
| Cre-dependent tdTomato-P2A-PuroR reporter | 3 | 12 | 8 |
| Cas9-P2A-mCherry with kanamycin propagation | 5 | 12 | 8 |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | 4 | 12 | 8 |
| Guide-vector mCherry-P2A-NeoR replacement | 4 | 12 | 8 |

## What makes these harder

- No assembly method, backbone, insert source, plasmid name, or exact coordinates are disclosed.
- Each task supplies 12 accession-only Addgene GenBank files and eight QC-valid iGEM GenBank files, including irrelevant alternatives.
- The exact products require three to five PCR-derived components.
- All six tasks require frame-sensitive coding or tag junctions; three require two coding changes, and two require reverse-orienting a bacterial marker.
- The prompt describes the biological outcome without naming the source plasmids, assembly method, coordinates, junctions, or component count.

The verifier still compares the assembled circular product with one exact reference. Because the prompts are now less prescriptive, that score should be interpreted alongside the sequence visualization: another biologically reasonable architecture may not be sequence-identical to the reference. `validation/` contains exact FASTA references and annotated GenBank review references with complete component provenance.

## Which requirements are realistic?

The expressed protein, regulatory context, linked-versus-independent expression, selectable marker, and removal of an unwanted gene are ordinary real-world design requirements. Requiring genes to come from the available inventory is also realistic when a lab wants to reuse material on hand.

The fixed primer-only variant is benchmark scaffolding that represents a stockroom exercise, not a universal laboratory requirement. The previous component-count limits, explicit stop-codon and reading-frame instructions, long lists of elements to retain, and directions about exact local edits were removed. Those details made the intended reference easier to infer and were more useful for constraining the verifier than for stating a normal request.

## Primer and enzyme inventory subset

`questions_reagent_inventory.jsonl` contains three representative tasks: the 3-component TCF/LEF reporter, 4-component two-locus lentiviral edit, and 5-component Cas9/marker edit. Each has an equal number of canonical and decoy primer stocks plus eight enzyme stocks. Primer filenames and enzyme filenames are opaque; the model must select them by inspecting `reagent_inventory.tsv` or the individual stock files. Novel primers are not permitted in these variants. Both canonical and decoy primer stocks are drawn deterministically from primer designs against the attached Addgene sequence inventory rather than random DNA strings.

Every base task and reagent task includes eight QC-valid plasmids sampled from the 2026 iGEM distribution kit: a promoter, RBS, terminator, three unrelated CDS parts, a fluorescent-protein decoy, and a Type IIS destination backbone. Only the circular GenBank files and a filtered `igem_inventory.tsv` are attached. The FASTA copies are sequence-identical and therefore redundant; the full 573-record manifests and raw JSON are useful for dataset curation but unnecessarily large for an individual model task. The filtered TSV preserves the useful plate, role, assembly, flanking-overhang, resistance, and QC metadata. The source kit does not provide nucleotide coordinates for the named parts, so the model still has to inspect the whole-plasmid sequence.

The reagent-inventory prompt adds only this rule:

> This version also has a fixed primer and enzyme stock in the same task inventory. Use only the stocked primers and enzymes; some of them will not be relevant to this build.

## Reagent-inventory questions for review (3 of 6)

These show the shortened question wording. The reagent variant adds one sentence requiring use of the stocked primers and enzymes. The shared protocol-syntax suffix is not repeated here.

### TCF/LEF EGFP-P2A-PuroR reporter

Could you turn one of our TCF/LEF-responsive mammalian reporters into an EGFP reporter with puromycin selection? I want EGFP and PuroR made as separate proteins from the same reporter transcript, using P2A.

All available Addgene and iGEM plasmids are in the attached task inventory. Do not synthesize genes de novo; obtain the gene sequences you need from that inventory.

### Lentiviral mCherry with G418 selection

Could you modify one of our third-generation lentiviral transfer vectors so it expresses mCherry instead of its current fluorescent reporter and uses G418 rather than puromycin for mammalian selection? Keep reporter expression and drug selection independent.

All available Addgene and iGEM plasmids are in the attached task inventory. Do not synthesize genes de novo; obtain the gene sequences you need from that inventory.

### Cas9-P2A-mCherry with kanamycin propagation

Could you modify one of our CAG-Cas9/sgRNA plasmids so it also makes mCherry as a separate protein using P2A? I also need the finished plasmid to use kanamycin, rather than ampicillin, for bacterial selection.

All available Addgene and iGEM plasmids are in the attached task inventory. Do not synthesize genes de novo; obtain the gene sequences you need from that inventory.

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
