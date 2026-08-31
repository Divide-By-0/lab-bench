# Hard mixed-inventory cloning pilot

This package preserves the easier `cloning_inventory_pilot_v1` set and adds six genuinely harder underlying constructs. These are not merely prompt-redacted versions of two-fragment swaps.
A separate matched set, `questions_intent_challenge.jsonl`, keeps those six constructs and inventories fixed while replacing the component-level requests with experimental-intent prompts.

Each JSONL record points to its complete inventory through the `files` field. Base-task inventories are under `cloning/<task-id>/`; fixed-reagent inventories are under `reagent_inventory/<task-id>/`. The runner attaches or copies every file from that directory into the model's working directory.

## Inventory supplied

Each selected iGEM item is represented twice: once as the circular physical carrier plasmid from the 2026 kit snapshot and once as the actual element-level Registry sequence. Thus the inventory includes the promoter, RBS, terminator, CDS, and backbone/device elements themselves, not merely the plasmids carrying them.

| Question set | Tasks | Addgene plasmids/task | iGEM carrier plasmids/task | iGEM element records/task | Primers/task | Enzymes/task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base questions | 6 | 12 | 8 | 8 | 0 | 16 |
| Matched intent challenge | 6 | 12 | 8 | 8 | 0 | 16 |
| TCF/LEF EGFP-P2A-PuroR reporter reagent variant | 1 | 12 | 8 | 8 | 12 | 16 |
| Lentiviral mCherry with G418 selection reagent variant | 1 | 12 | 8 | 8 | 16 | 16 |
| Cas9-P2A-mCherry with kanamycin propagation reagent variant | 1 | 12 | 8 | 8 | 20 | 16 |

The enzyme stock is non-empty for every task and contains: BamHI, BbsI, BsaI, BsmBI, EcoRI, EcoRV, HindIII, KpnI, NdeI, NheI, NotI, PstI, SacI, SpeI, XbaI, XhoI. The three reagent variants additionally contain equal numbers of useful and decoy primers.

## What makes these harder

- No assembly method, backbone, insert source, plasmid name, or exact coordinates are disclosed.
- Each task supplies 12 accession-only Addgene plasmids, eight QC-valid iGEM carrier plasmids, the corresponding eight iGEM elements, and a stocked enzyme panel, including irrelevant alternatives.
- The exact products require three to five PCR-derived components.
- All six tasks require frame-sensitive coding or tag junctions; three require two coding changes, and two require reverse-orienting a bacterial marker.
- The matched intent prompts additionally avoid naming the reporter genes, resistance genes, peptide mechanism, or displaced starting parts.

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

## Matched intent challenge

This is a controlled prompt-hardening experiment, not six new gold constructs. Each record has the same task ID, files, sources, exact reference, and functional constraint specification as its base counterpart. Only the question and difficulty metadata change. This makes a base-versus-intent score comparison interpretable.

The model must infer the backbone class, functional parts, expression architecture, and assembly method. The so-called traps are not secret wishes: they are sequence-level consequences of requirements stated in the prompt, such as preserving a transfer vector's packaging elements, removing an unwanted resistance gene, or avoiding a stop codon inside a linked ORF. Reviewer metadata is also saved in `intent_challenge_design_v1.json`.

| Reviewer name | Tier | Question shown before the shared suffix | Inference required | Sequence-level traps |
| --- | ---: | --- | --- | --- |
| TCF/LEF EGFP-P2A-PuroR reporter | 2 | We need a live-cell construct for enriching and tracking mammalian cells only while canonical Wnt/beta-catenin transcription is active. Use a fluorescence-only readout rather than a luminescent one. The pathway-responsive transcript should provide green fluorescence and puromycin resistance from one compact open reading frame, but those activities must come from separate proteins. | select a pathway-responsive rather than constitutive backbone; infer a green reporter and puromycin-resistance coding sequence; choose an inventory-supported way to make two proteins from one transcript | retain the TCF/LEF response array and its minimal promoter; remove the original luciferase coding sequence; omit the reporter stop at the linked coding junction and keep one frame |
| Lentiviral mCherry with G418 selection | 2 | We need a third-generation lentiviral transfer construct for stable labeling of mammalian cells with a monomeric red fluorescent protein and enrichment with G418. Reporter intensity must remain interpretable independently of selection-marker expression, so each should have its own transcription unit. The vector should add no other fluorescent or mammalian drug-selection phenotype. | identify a lentiviral transfer rather than packaging plasmid; map monomeric red fluorescence and G418 resistance to inventory parts; preserve independent reporter and selector expression cassettes | retain the packaging signal, RRE, and self-inactivating LTR architecture; distinguish a mammalian G418 cassette from bacterial kanamycin selection; remove the displaced reporter and mammalian selector coding sequences |
| Cre-dependent tdTomato-P2A-PuroR reporter | 3 | Build a ubiquitous mammalian lineage-tracing construct that remains off until Cre removes a transcriptional stop. Once activated, it should produce only a bright red signal and puromycin resistance from one compact open reading frame while leaving the two products physically separate. | identify a Cre-dependent lox-stop-lox reporter backbone; choose the brighter available red reporter and a puromycin marker; infer an inventory-supported polycistronic architecture | retain both loxP sites and the intervening stop cassette in the right order; remove the original post-recombination reporter; preserve an uninterrupted reporter-to-cleavage-peptide-to-selector frame |
| Cas9-P2A-mCherry with kanamycin propagation | 3 | We need a single transient mammalian plasmid that accepts an sgRNA and expresses its nuclease, with monomeric red fluorescence reporting nuclease expression from the same transcript without making a fluorescent fusion protein. It must propagate under kanamycin, and our facility does not permit beta-lactam-resistance plasmids. | infer the nuclease and guide-expression architecture from the sgRNA use case; choose a monomeric red reporter and a cotranslational separation strategy; select bacterial kanamycin resistance and eliminate beta-lactam resistance | retain both the U6 guide cassette and the mammalian nuclease cassette; remove the nuclease stop before the linked peptide while preserving its frame; install the bacterial marker in expression orientation without retaining AmpR |
| T7 6xHis-TEV-tdTomato with kanamycin propagation | 3 | We need an IPTG-inducible E. coli construct for high-level production of a bright red fluorescent protein. The product should support immobilized-metal affinity purification and clean protease removal of its N-terminal affinity/expression leader, without a bulky solubility-fusion partner. Maintain the plasmid under kanamycin; beta-lactam-resistance DNA cannot be used in this project. | select a T7 bacterial expression backbone rather than a mammalian vector; infer the fluorescent protein, affinity handle, and protease-cleavage site; choose bacterial kanamycin resistance and remove beta-lactam resistance | retain the T7 promoter, gene-10 translation context, and T7 terminator; transfer only the useful donor coding interval rather than its arabinose system; keep the complete leader and reporter in frame while excluding MBP |
| Guide-vector mCherry-P2A-NeoR replacement | 3 | Our mammalian cells already express the genome-editing nuclease. Build a third-generation lentiviral construct that delivers only an sgRNA, marks transduced cells with a monomeric red signal, and permits G418 selection. The two phenotypes should come from one compact open reading frame but separate proteins. No nuclease or second mammalian drug-selection phenotype may remain in the payload. | identify a guide-capable lentiviral transfer backbone; map monomeric red fluorescence and G418 selection to inventory parts; infer a linked-but-separated expression architecture while deleting nuclease | retain the U6 guide cassette plus lentiviral packaging and SIN-LTR elements; remove both the nuclease and the displaced mammalian selector; preserve one coding frame across reporter, cleavage peptide, and G418 marker |

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
To run the matched intent set, use `questions_intent_challenge.jsonl` instead. Use a distinct Inspect log name when comparing the two sets because their deliberately matched sample IDs are the same.
