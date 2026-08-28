# Hard mixed-inventory cloning pilot

This package preserves the easier `cloning_inventory_pilot_v1` set and adds six genuinely harder underlying constructs. These are not merely prompt-redacted versions of two-fragment swaps.

Each JSONL record points to its complete inventory through the `files` field. Base-task inventories are under `cloning/<task-id>/`; fixed-reagent inventories are under `reagent_inventory/<task-id>/`. The runner attaches or copies every file from that directory into the model's working directory.

## Inventory supplied

Each selected iGEM item is represented twice: once as the circular physical carrier plasmid from the 2026 kit snapshot and once as the actual element-level Registry sequence. Thus the inventory includes the promoter, RBS, terminator, CDS, and backbone/device elements themselves, not merely the plasmids carrying them.

| Question set | Tasks | Addgene plasmids/task | iGEM carrier plasmids/task | iGEM element records/task | Primers/task | Enzymes/task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base questions | 6 | 12 | 8 | 8 | 0 | 16 |
| TCF/LEF EGFP-P2A-PuroR reporter reagent variant | 1 | 12 | 8 | 8 | 12 | 16 |
| Lentiviral mCherry with G418 selection reagent variant | 1 | 12 | 8 | 8 | 16 | 16 |
| Cas9-P2A-mCherry with kanamycin propagation reagent variant | 1 | 12 | 8 | 8 | 20 | 16 |

The enzyme stock is non-empty for every task and contains: BamHI, BbsI, BsaI, BsmBI, EcoRI, EcoRV, HindIII, KpnI, NdeI, NheI, NotI, PstI, SacI, SpeI, XbaI, XhoI. The three reagent variants additionally contain equal numbers of useful and decoy primers.

## What makes these harder

- No assembly method, backbone, insert source, plasmid name, or exact coordinates are disclosed.
- Each task supplies 12 accession-only Addgene plasmids, eight QC-valid iGEM carrier plasmids, the corresponding eight iGEM elements, and a stocked enzyme panel, including irrelevant alternatives.
- The exact products require three to five PCR-derived components.
- All six tasks require frame-sensitive coding or tag junctions; three require two coding changes, and two require reverse-orienting a bacterial marker.
- The prompt describes the biological outcome without naming the source plasmids, assembly method, coordinates, junctions, or component count.

The verifier still compares the assembled circular product with one exact reference. Because the prompts are now less prescriptive, that score should be interpreted alongside the sequence visualization: another biologically reasonable architecture may not be sequence-identical to the reference. `validation/` contains exact FASTA references and annotated GenBank review references with complete component provenance.

## Which requirements are realistic?

The expressed protein, regulatory context, linked-versus-independent expression, selectable marker, and removal of an unwanted gene are ordinary real-world design requirements. Requiring genes to come from the available inventory is also realistic when a lab wants to reuse material on hand.

The fixed primer-only variant is benchmark scaffolding that represents a stockroom exercise, not a universal laboratory requirement. The previous component-count limits, explicit stop-codon and reading-frame instructions, long lists of elements to retain, and directions about exact local edits were removed. Those details made the intended reference easier to infer and were more useful for constraining the verifier than for stating a normal request.

## Primer inventory subset

`questions_reagent_inventory.jsonl` contains three representative tasks: the 3-component TCF/LEF reporter, 4-component two-locus lentiviral edit, and 5-component Cas9/marker edit. Each has an equal number of canonical and decoy primer stocks. Primer and enzyme filenames are opaque; the model must select them by inspecting `reagent_inventory.tsv` or the individual stock files. Novel primers are not permitted in these variants. Both canonical and decoy primer stocks are drawn deterministically from primer designs against the attached Addgene sequence inventory rather than random DNA strings.

Every base task and reagent task includes eight QC-valid plasmids sampled from the 2026 iGEM distribution kit: a promoter, RBS, terminator, three unrelated CDS parts, a fluorescent-protein decoy, and a Type IIS destination backbone/device. Each carrier is paired with its separate element-level GenBank record. `igem_inventory.tsv` maps the pair and preserves plate, role, assembly, flanking-overhang, resistance, QC, and length metadata.

The reagent-inventory prompt adds only this rule:

> This version also has a fixed primer stock. Use only the stocked primers; some of them will not be relevant to this build.

## Shared inventory suffix used on all questions

> All available Addgene plasmids, iGEM carrier plasmids and element records, and stocked enzymes are in the attached task inventory. Do not synthesize genes de novo; obtain the gene sequences you need from that inventory.

The suffix is present in each JSONL question but is shown only once here.

## All six questions and intended work

The intended-work column is reviewer-only and is not shown to the model.

| Name | Question shown before the shared suffix | Intended solution/work |
| --- | --- | --- |
| TCF/LEF EGFP-P2A-PuroR reporter | Could you turn one of our TCF/LEF-responsive mammalian reporters into an EGFP reporter with puromycin selection? I want EGFP and PuroR made as separate proteins from the same reporter transcript, using P2A. | Identify the TOPFlash reporter backbone, replace luciferase with EGFP-P2A-PuroR, and assemble three PCR products while keeping the coding junction in frame. |
| Lentiviral mCherry with G418 selection | Could you modify one of our third-generation lentiviral transfer vectors so it expresses mCherry instead of its current fluorescent reporter and uses G418 rather than puromycin for mammalian selection? Keep reporter expression and drug selection independent. | Identify the pLJM1 transfer vector, replace EGFP with mCherry and replace the independently expressed PuroR CDS with NeoR; the canonical build uses four PCR products. |
| Cre-dependent tdTomato-P2A-PuroR reporter | Could you modify one of our Cre-dependent mammalian reporters so that, after Cre activation, it produces tdTomato and puromycin resistance as separate proteins from one transcript? Please use P2A between them. | Identify the lox-stop-lox conditional reporter, preserve its Cre-control architecture, and replace GFP with tdTomato-P2A-PuroR using three PCR products. |
| Cas9-P2A-mCherry with kanamycin propagation | Could you modify one of our CAG-Cas9/sgRNA plasmids so it also makes mCherry as a separate protein using P2A? I also need the finished plasmid to use kanamycin, rather than ampicillin, for bacterial selection. | Identify the pX330 CAG-Cas9/sgRNA backbone, append P2A-mCherry to the Cas9 reading frame, and replace AmpR with the correctly oriented KanR CDS; the canonical build uses five PCR products. |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | Could you repurpose one of our T7 MBP expression plasmids to express tdTomato instead of MBP? The protein should carry the available N-terminal 6xHis/T7-tag/TEV leader, and the finished plasmid should use kanamycin rather than ampicillin for bacterial selection. | Identify the T7 MBP destination, replace MBP with the donor's 6xHis/T7-tag/TEV-tdTomato segment, and replace AmpR with correctly oriented KanR using four PCR products. |
| Guide-vector mCherry-P2A-NeoR replacement | Could you convert one of our lentiviral Cas9/guide vectors into a guide-only vector that expresses mCherry and NeoR as separate proteins using P2A? The finished vector should use G418 for mammalian selection and should no longer contain Cas9. | Identify lentiCRISPR v2 and replace its Cas9-P2A-PuroR coding region with mCherry-P2A-NeoR while retaining the guide and lentiviral architecture; the canonical build uses four PCR products. |

## Regeneration

```bash
uv run --extra lab_bench_2 python tools/generate_cloning_inventory_hard_questions.py \
  --input-dir /path/to/addgene-genbank-files \
  --igem-dir /path/to/igem-distribution-kit-2026 \
  --igem-elements-dir experiments/cloning_inventory_hard_v1/igem_element_sources \
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
