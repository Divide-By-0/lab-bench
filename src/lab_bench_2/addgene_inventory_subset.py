"""Curated Addgene full-sequence subset for cloning inventories.

The catalog is a small, diverse slice of public Addgene plasmids plus
literature-backed gotchas that are easy to miss on a map: conflicting full
maps, FLEX leak, BbsI/BsmBI mixups, nickase vs nuclease, leftover Type IIS
sites, splice-prone tags. Partial Sanger reads are excluded. Each entry also
records a typical Gibson or Golden Gate process that would be run on top of
that backbone, from 2-part inserts up to 24-fragment assembly. Full-sequence
GBKs for this subset live in ``addgene_inventory_subset_gbk/``. Re-download
with the chrome-session builder if those files are missing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ALLOWED_SEQUENCE_SOURCES = frozenset({"preferred", "addgene", "depositor", "all"})
ALLOWED_HOSTS = frozenset(
    {
        "mammalian",
        "bacterial",
        "yeast",
        "plant",
        "worm",
        "insect",
        "viral",
    }
)
ALLOWED_ASSEMBLY_METHODS = frozenset(
    {
        "restriction",
        "gibson",
        "oligo_gg",
        "golden_gate",
        "hierarchical_gg",
    }
)
MAPS_NEEDED_TO_COMPARE = 2
TWO_FRAGMENT_ASSEMBLY = 2
CASSETTE_ASSEMBLY_FRAGMENTS = 8
HIGH_COMPLEXITY_GG_FRAGMENTS = 24
ALLOWED_GOTCHA_KINDS = frozenset(
    {
        "depositor_vs_addgene_mismatch",
        "itr_deletion",
        "backbone_orientation",
        "multiple_full_maps",
        "paper_vs_sequence_typo",
        "splice_motif",
        "redundant_orf_cds",
        "uncatalogued_part_variant",
        "local_duplicate_copy",
        "flex_leak",
        "enzyme_site_mixup",
        "nickase_vs_nuclease",
        "stuffer_vs_empty",
        "leftover_type_iis",
        "inverted_orf",
        "naming_collision",
    }
)

NAR_PLASMID_ERRORS = (
    "Xie et al., Nucleic Acids Research 53:gkaf697 (2025), "
    "https://doi.org/10.1093/nar/gkaf697"
)
NAR_PLASMID_ERRORS_URL = "https://academic.oup.com/nar/article/53/14/gkaf697/8222435"
PLANNOTATE_VARIANTS = (
    "Mante et al., Nucleic Acids Research 51:e55 (2023), "
    "https://doi.org/10.1093/nar/gkad187"
)
PLANNOTATE_VARIANTS_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10120640/"
EMBO_SPLICE = (
    "LaFleur et al., The EMBO Journal (2026), "
    "https://doi.org/10.1038/s44318-026-00733-z"
)
EMBO_SPLICE_URL = "https://www.embopress.org/doi/10.1038/s44318-026-00733-z"
BIOSTARS_ORF = "https://www.biostars.org/p/230001"
ADDGENE_ITR_BLOG = (
    "https://blog.addgene.org/viral-vectors-101-parts-of-the-aav-transfer-plasmid"
)
PKJ1712_NOTES = "https://www.addgene.org/21870/notes/"
ADDGENE_QC = "https://blog.addgene.org/a-look-at-addgenes-qc-process"
FLEX_LEAK_BLOG = "https://blog.addgene.org/a-practical-guide-to-optimizing-aav-dio-and-flex-vector-expression"
FLEX_LEAK_PLASMID = "https://www.addgene.org/28306/"
PX459_DIGEST = "https://pmc.ncbi.nlm.nih.gov/articles/PMC8606105/"
GG_INTERNAL_BSAI = "https://pubs.acs.org/doi/10.1021/acssynbio.2c00355"
YTK_PAPER = (
    "Lee et al., ACS Synth. Biol. 4:975 (2015), https://doi.org/10.1021/sb500366v"
)
YTK_PAPER_URL = "https://doi.org/10.1021/sb500366v"
POTAPOV_OVERHANGS = (
    "Potapov et al., ACS Synth. Biol. 7:2665 (2018), "
    "https://doi.org/10.1021/acssynbio.8b00333"
)
POTAPOV_OVERHANGS_URL = "https://doi.org/10.1021/acssynbio.8b00333"
BMC_LOX2272 = (
    "https://bmcbiotechnol.biomedcentral.com/articles/10.1186/s12896-018-0462-x"
)
LENTICRISPR_PAGE = "https://www.addgene.org/52961/"
PLKO_PAGE = "https://www.addgene.org/10878/"
GREENGATE = (
    "Lampropoulos et al., PLoS One 8:e83043 (2013), "
    "https://doi.org/10.1371/journal.pone.0083043"
)
GREENGATE_URL = "https://doi.org/10.1371/journal.pone.0083043"
CIDAR = (
    "Iverson et al., ACS Synth. Biol. 5:99 (2016), "
    "https://doi.org/10.1021/acssynbio.5b00124"
)
CIDAR_URL = "https://doi.org/10.1021/acssynbio.5b00124"


@dataclass(frozen=True)
class Gotcha:
    """A documented inventory trap on this plasmid or its public maps."""

    kind: str
    summary: str
    citation: str
    citation_url: str


@dataclass(frozen=True)
class SubsetPlasmid:
    """One plasmid in the inventory subset."""

    plasmid_id: int
    name: str
    role: str
    hosts: tuple[str, ...]
    assembly_method: str
    assembly_fragments: int
    assembly_note: str
    sequence_source: str = "preferred"
    gotchas: tuple[Gotcha, ...] = ()


def _gotcha(kind: str, summary: str, citation: str, citation_url: str) -> Gotcha:
    return Gotcha(
        kind=kind, summary=summary, citation=citation, citation_url=citation_url
    )


def _p(
    plasmid_id: int,
    name: str,
    role: str,
    hosts: tuple[str, ...],
    assembly_method: str,
    assembly_fragments: int,
    assembly_note: str,
    *,
    sequence_source: str = "preferred",
    gotchas: tuple[Gotcha, ...] = (),
) -> SubsetPlasmid:
    return SubsetPlasmid(
        plasmid_id=plasmid_id,
        name=name,
        role=role,
        hosts=hosts,
        assembly_method=assembly_method,
        assembly_fragments=assembly_fragments,
        assembly_note=assembly_note,
        sequence_source=sequence_source,
        gotchas=gotchas,
    )


# Full-sequence plasmids only. Names match the Addgene sequences-page heading.
# sequence_source "all" pulls every public full map so conflicting copies stay
# in the inventory. assembly_* describes a typical Gibson/Golden Gate job on
# that backbone, not how the deposited plasmid was originally built.
SUBSET: tuple[SubsetPlasmid, ...] = (
    _p(
        50005,
        "pUC19",
        "minimal cloning backbone",
        ("bacterial",),
        "gibson",
        2,
        "2-fragment Gibson of a PCR insert into linearized pUC19.",
    ),
    _p(
        29663,
        "pET His6 GFP TEV LIC cloning vector (1GFP)",
        "bacterial GFP expression; 2-fragment Gibson/LIC",
        ("bacterial",),
        "gibson",
        2,
        "Swap the GFP ORF for a new CDS with 2-fragment Gibson or LIC.",
    ),
    _p(
        29656,
        "pET His6 MBP TEV LIC cloning vector (1M)",
        "bacterial LIC expression backbone",
        ("bacterial",),
        "gibson",
        2,
        "2-fragment Gibson/LIC of a CDS into the TEV-cleavable MBP fusion.",
    ),
    _p(
        17398,
        "pENTR1A no ccDB (w48-1)",
        "Gateway entry backbone",
        ("bacterial",),
        "gibson",
        2,
        "2-fragment Gibson of att-flanked CDS into pENTR; ccdB is already gone.",
    ),
    _p(
        10878,
        "pLKO.1 - TRC cloning vector",
        "lentiviral empty backbone",
        ("mammalian", "viral"),
        "restriction",
        2,
        "AgeI/EcoRI replacement of the 1.9 kb stuffer with an shRNA oligo duplex.",
        gotchas=(
            _gotcha(
                "stuffer_vs_empty",
                "The TRC backbone is not empty: a 1.9 kb stuffer sits between "
                "AgeI and EcoRI. A digest that 'looks linearized' can still be "
                "uncut stuffer plasmid.",
                "Addgene pLKO.1 cloning instructions",
                PLKO_PAGE,
            ),
            _gotcha(
                "redundant_orf_cds",
                "SnapGene maps often stack an ORF annotation on top of the "
                "true CDS for the same stretch of DNA.",
                "BioStars plasmid annotation thread",
                BIOSTARS_ORF,
            ),
            _gotcha(
                "uncatalogued_part_variant",
                "pLannotate found 171,828 non-canonical part instances across "
                "51,384 fully sequenced Addgene plasmids, including AmpR and "
                "origin variants still given the canonical name.",
                PLANNOTATE_VARIANTS,
                PLANNOTATE_VARIANTS_URL,
            ),
        ),
    ),
    _p(
        48138,
        "pSpCas9(BB)-2A-GFP (PX458)",
        "mammalian CRISPR all-in-one",
        ("mammalian",),
        "oligo_gg",
        2,
        "BbsI Golden Gate of an annealed sgRNA oligo duplex into PX458.",
        gotchas=(
            _gotcha(
                "enzyme_site_mixup",
                "Zhang mammalian PX plasmids use BbsI. Lentiviral CRISPR "
                "plasmids from the same lab use BsmBI. Protocols copied across "
                "backbones silently fail.",
                LENTICRISPR_PAGE,
                LENTICRISPR_PAGE,
            ),
        ),
    ),
    _p(
        42230,
        "pX330-U6-Chimeric_BB-CBh-hSpCas9",
        "mammalian CRISPR empty backbone",
        ("mammalian",),
        "oligo_gg",
        2,
        "BbsI Golden Gate of a sgRNA oligo duplex into pX330.",
        gotchas=(
            _gotcha(
                "nickase_vs_nuclease",
                "pX330 is nuclease Cas9. pX335 (42335) is the D10A nickase "
                "with an almost identical map. A one-letter page mixup yields "
                "nicks instead of DSBs.",
                "Addgene pX335 42335 vs pX330 42230",
                "https://www.addgene.org/42335/",
            ),
        ),
    ),
    _p(
        42335,
        "pX335-U6-Chimeric_BB-CBh-hSpCas9n(D10A)",
        "mammalian Cas9 D10A nickase",
        ("mammalian",),
        "oligo_gg",
        2,
        "BbsI Golden Gate of a sgRNA oligo duplex into the nickase backbone.",
        gotchas=(
            _gotcha(
                "nickase_vs_nuclease",
                "SnapGene still labels the CDS Cas9. The D10A nickase is a "
                "single residue; inventory role rules that key on 'cas9' will "
                "call this a nuclease.",
                "Addgene pX335 42335",
                "https://www.addgene.org/42335/",
            ),
        ),
    ),
    _p(
        62988,
        "pSpCas9(BB)-2A-Puro (PX459) V2.0",
        "mammalian CRISPR all-in-one",
        ("mammalian",),
        "oligo_gg",
        2,
        "BbsI Golden Gate of a sgRNA oligo duplex; RE mapping alone mis-calls inserts.",
        sequence_source="all",
        gotchas=(
            _gotcha(
                "multiple_full_maps",
                "Addgene lists two Addgene-verified full sequences (9171 vs "
                "9172 bp). Preferred download keeps only the first.",
                ADDGENE_QC,
                ADDGENE_QC,
            ),
            _gotcha(
                "enzyme_site_mixup",
                "BbsI-EcoRI screening of PX459 sgRNA clones can match the "
                "expected two-band pattern even when the oligo failed to "
                "insert or a BbsI site survived (PMC8606105).",
                "Pitfalls of restriction mapping CRISPR constructs",
                PX459_DIGEST,
            ),
        ),
    ),
    _p(
        52961,
        "lentiCRISPR v2",
        "lentiviral CRISPR all-in-one",
        ("mammalian", "viral"),
        "oligo_gg",
        2,
        "BsmBI Golden Gate of a sgRNA oligo duplex into the filler slot.",
        gotchas=(
            _gotcha(
                "enzyme_site_mixup",
                "gRNA cloning is BsmBI (Esp3I), not the BbsI used on PX330/"
                "PX458/PX459. The unused slot is a filler, not an empty MCS.",
                "Addgene lentiCRISPR v2 cloning note",
                LENTICRISPR_PAGE,
            ),
            _gotcha(
                "naming_collision",
                "lentiCRISPR (49535) is the older lower-titer v1 with a "
                "different map. Papers still cite 'lentiCRISPR' for v2.",
                LENTICRISPR_PAGE,
                LENTICRISPR_PAGE,
            ),
        ),
    ),
    _p(
        49535,
        "lentiCRISPR",
        "lentiviral CRISPR v1; lower titer than v2",
        ("mammalian", "viral"),
        "oligo_gg",
        2,
        "BsmBI oligo Golden Gate; often confused with v2 (52961).",
        gotchas=(
            _gotcha(
                "naming_collision",
                "Same lab, same gRNA protocol, ~10-fold lower titer than v2. "
                "Inventories that merge 'lentiCRISPR' labels hide which backbone "
                "the user actually has.",
                LENTICRISPR_PAGE,
                LENTICRISPR_PAGE,
            ),
        ),
    ),
    _p(
        52962,
        "lentiCas9-Blast",
        "lentiviral Cas9 only",
        ("mammalian", "viral"),
        "gibson",
        2,
        "2-fragment Gibson to swap the EF1a-Cas9 cassette; no gRNA slot.",
    ),
    _p(
        52963,
        "lentiGuide-Puro",
        "lentiviral sgRNA only",
        ("mammalian", "viral"),
        "oligo_gg",
        2,
        "BsmBI Golden Gate of a sgRNA oligo duplex (same enzyme trap as v2).",
        gotchas=(
            _gotcha(
                "enzyme_site_mixup",
                "BsmBI oligo cloning, not BbsI. Pairing this backbone with a "
                "PX458 oligo design leaves the wrong overhangs.",
                LENTICRISPR_PAGE,
                LENTICRISPR_PAGE,
            ),
        ),
    ),
    _p(
        46569,
        "pdCas9",
        "catalytically dead Cas9",
        ("bacterial",),
        "gibson",
        2,
        "2-fragment Gibson of a new dCas9 fusion; map still reads as Cas9.",
        gotchas=(
            _gotcha(
                "nickase_vs_nuclease",
                "Dead Cas9 (D10A and H840A). Feature labels usually still say "
                "Cas9; role rules keyed on 'cas9' will not mark it catalytically dead.",
                "Addgene pdCas9 46569",
                "https://www.addgene.org/46569/",
            ),
        ),
    ),
    _p(
        12260,
        "psPAX2",
        "2nd-generation lentiviral packaging",
        ("mammalian", "viral"),
        "restriction",
        1,
        "Used as-is; not a cloning destination. Often swapped with pMD2.G (12259).",
        gotchas=(
            _gotcha(
                "naming_collision",
                "12259 is pMD2.G (VSV-G). 12260 is psPAX2 (gag/pol). The ids "
                "are consecutive and both are 'packaging' in lab slang.",
                "Addgene 12259 vs 12260",
                "https://www.addgene.org/12259/",
            ),
        ),
    ),
    _p(
        12259,
        "pMD2.G",
        "VSV-G envelope",
        ("mammalian", "viral"),
        "restriction",
        1,
        "Used as-is. Consecutive id with psPAX2.",
    ),
    _p(
        8454,
        "pCMV-VSV-G",
        "VSV-G envelope (3rd-gen helper)",
        ("mammalian", "viral"),
        "gibson",
        2,
        "2-fragment Gibson of an alternate envelope glycoprotein.",
    ),
    _p(
        8455,
        "pCMV-dR8.2 dvpr",
        "3rd-generation lentiviral packaging",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson if swapping helper cassettes around the LTRs.",
    ),
    _p(
        1764,
        "pBABE-puro",
        "retroviral empty backbone",
        ("mammalian", "viral"),
        "gibson",
        2,
        "2-fragment Gibson of a CDS into the retroviral MCS.",
    ),
    _p(
        13775,
        "pCAG-Cre",
        "Cre recombinase expression",
        ("mammalian",),
        "gibson",
        3,
        "3-fragment Gibson to replace Cre with Cre-ERT2 or FlpO.",
    ),
    _p(
        14148,
        "pAG416GPD-ccdB",
        "yeast Gateway destination",
        ("yeast",),
        "gibson",
        2,
        "LR/Gibson of an entry clone; ccdB dropout is the counterselection.",
    ),
    _p(
        1384,
        "pYES2/25Q",
        "yeast expression",
        ("yeast",),
        "gibson",
        2,
        "2-fragment Gibson of a new polyQ or CDS into pYES2.",
    ),
    _p(
        1654,
        "L4440",
        "C. elegans RNAi feeding backbone",
        ("worm", "bacterial"),
        "gibson",
        2,
        "2-fragment Gibson of a gene fragment between T7 promoters.",
    ),
    _p(
        41819,
        "gRNA_GFP-T1",
        "Drosophila gRNA",
        ("insect",),
        "oligo_gg",
        2,
        "BbsI Golden Gate of a new gRNA oligo duplex.",
    ),
    _p(
        65108,
        "pYTK001",
        "YTK part-plasmid entry (BsmBI)",
        ("yeast", "bacterial"),
        "golden_gate",
        2,
        "BsmBI Golden Gate of a PCR part into pYTK001; BsaI sites must remain.",
        gotchas=(
            _gotcha(
                "leftover_type_iis",
                "Entry cloning uses BsmBI. The part is supposed to keep inward "
                "BsaI sites for the next (8-part cassette) level. Digesting the "
                "entry clone with BsaI looks like a failed insert.",
                YTK_PAPER,
                YTK_PAPER_URL,
            ),
            _gotcha(
                "leftover_type_iis",
                "Parts with internal BsaI or BsmBI must be domesticated before "
                "MoClo; leftover sites re-cut the cassette (ACS Synth Biol 2022).",
                "A User's Guide to Golden Gate Cloning Methods and Standards",
                GG_INTERNAL_BSAI,
            ),
        ),
    ),
    _p(
        65202,
        "pYTK095",
        "YTK 8-part cassette acceptor",
        ("yeast", "bacterial"),
        "hierarchical_gg",
        8,
        "BsaI one-pot of up to 8 YTK parts (connectors, promoter, CDS, "
        "terminator, origin, marker) into pYTK095.",
        gotchas=(
            _gotcha(
                "leftover_type_iis",
                "Cassette assembly is BsaI. Using BsmBI (the entry enzyme) on "
                "this acceptor does not drop the GFP dropout.",
                YTK_PAPER,
                YTK_PAPER_URL,
            ),
        ),
    ),
    _p(
        48856,
        "pGGA000",
        "GreenGate promoter-module entry",
        ("plant",),
        "hierarchical_gg",
        6,
        "BsaI GreenGate of six modules (promoter, N-tag, CDS, C-tag, "
        "terminator, resistance) into a plant binary.",
        gotchas=(
            _gotcha(
                "leftover_type_iis",
                "GreenGate modules keep BsaI sites with module-specific "
                "overhangs. An internal BsaI in a plant CDS silently drops "
                "that module (Lampropoulos 2013).",
                GREENGATE,
                GREENGATE_URL,
            ),
        ),
    ),
    _p(
        47676,
        "pGoldenGate-SE7",
        "2-part scarless plant Golden Gate dest",
        ("plant",),
        "golden_gate",
        3,
        "BsaI or SapI 2-part (promoter + reporter) scarless assembly into SE7.",
    ),
    _p(
        48076,
        "pICH86988",
        "MoClo plant binary Level 1/2 dest",
        ("plant",),
        "hierarchical_gg",
        8,
        "Hierarchical MoClo (BsaI then BpiI) of a transcription unit into a "
        "plant binary.",
    ),
    _p(
        51776,
        "pMDC32B-AtMIR390a-B/c",
        "plant miRNA backbone",
        ("plant",),
        "gibson",
        3,
        "3-fragment Gibson of a new miRNA precursor into the plant binary.",
    ),
    _p(
        59176,
        "p201H Cas9",
        "plant Cas9",
        ("plant",),
        "gibson",
        3,
        "3-fragment Gibson of gRNA cassettes onto plant Cas9.",
    ),
    _p(
        66070,
        "DVK_FG",
        "CIDAR MoClo destination (FG overhangs)",
        ("bacterial",),
        "hierarchical_gg",
        4,
        "BsaI 4-part transcriptional unit (promoter, RBS, CDS, terminator) "
        "into DVK_FG; BbsI for multi-gene Level 2.",
        gotchas=(
            _gotcha(
                "naming_collision",
                "CIDAR destinations are named by overhang pair (AE, EF, FG, "
                "GH). DVK_FG will not accept an AE-flanked part; the map looks "
                "like a generic dest.",
                CIDAR,
                CIDAR_URL,
            ),
        ),
    ),
    _p(
        195714,
        "pGGAselect",
        "24-fragment Golden Gate destination",
        ("bacterial",),
        "golden_gate",
        24,
        "BsaI, BsmBI, or BbsI assembly of the 24-fragment lac cassette "
        "(NEB high-complexity kit) into pGGAselect.",
        gotchas=(
            _gotcha(
                "leftover_type_iis",
                "The dest is cut by BsaI, BsmBI, and BbsI. Picking the enzyme "
                "that still has sites in a fragment re-opens the product. "
                "Overhang fidelity collapses as fragment count hits 24 "
                "(Potapov 2018).",
                POTAPOV_OVERHANGS,
                POTAPOV_OVERHANGS_URL,
            ),
        ),
    ),
    _p(
        37825,
        "pAAV-CAG-GFP",
        "AAV reporter",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a new promoter/ORF between the ITRs.",
    ),
    _p(
        105539,
        "pAAV.hSyn.eGFP.WPRE.bGH",
        "AAV reporter; LAB-Bench cloning attachment",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a cargo swap between the ITRs.",
        gotchas=(
            _gotcha(
                "local_duplicate_copy",
                "The LAB-Bench cloning cache has also contained a '(1)' copy of "
                "this GBK next to the official attachment.",
                "src/lab_bench_2/CLONING_SEQUENCE_DATA.md",
                "src/lab_bench_2/CLONING_SEQUENCE_DATA.md",
            ),
        ),
    ),
    _p(
        181752,
        "pCMV-MMLVgag-3xNES-Cas9",
        "mammalian Cas9 expression",
        ("mammalian",),
        "gibson",
        4,
        "4-fragment Gibson to rearrange NES, Cas9, and gag helpers.",
    ),
    _p(
        128652,
        "pLVX-EGFP-IRES-puro",
        "lentiviral reporter",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of an IRES cargo swap.",
        gotchas=(
            _gotcha(
                "splice_motif",
                "IRES and nearby MCS sequences can carry cryptic splice sites "
                "that the map never labels (EMBO J 2026).",
                EMBO_SPLICE,
                EMBO_SPLICE_URL,
            ),
        ),
    ),
    _p(
        61591,
        "pX601-AAV-CMV::NLS-SaCas9-NLS-3xHA-bGHpA;U6::BsaI-sgRNA",
        "AAV SaCas9; ITR match control in NAR 2025 Table S4",
        ("mammalian", "viral"),
        "oligo_gg",
        2,
        "BsaI Golden Gate of a SaCas9 sgRNA oligo; also an AAV ITR plasmid.",
        gotchas=(
            _gotcha(
                "enzyme_site_mixup",
                "sgRNA cloning is BsaI, not the BbsI/BsmBI used on SpCas9 PX "
                "and lentiCRISPR plasmids. HA-tagged SaCas9 plus ITRs on one "
                "map is easy to inventory as 'just Cas9'.",
                "Addgene 61591",
                "https://www.addgene.org/61591/",
            ),
        ),
    ),
    _p(
        28306,
        "pAAV-FLEX-tdTomato",
        "AAV FLEX reporter; Cre-OFF until recombination",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a new inverted ORF between loxP/lox2272 pairs.",
        gotchas=(
            _gotcha(
                "inverted_orf",
                "The tdTomato CDS is antisense to the CAG promoter. A feature "
                "inventory that ignores strand looks like a working reporter.",
                "Addgene FLEX/DIO guide",
                FLEX_LEAK_BLOG,
            ),
            _gotcha(
                "flex_leak",
                "Addgene warns this FLEX plasmid recombines during amp and "
                "packaging more than their other FLEX vectors, so a minority "
                "of particles express without Cre. The map cannot show that.",
                "Addgene 28306 comments",
                FLEX_LEAK_PLASMID,
            ),
            _gotcha(
                "naming_collision",
                "FLEX and DIO are used interchangeably in papers. This plasmid "
                "is named FLEX; 20297 is named 'double floxed'. Both invert.",
                FLEX_LEAK_BLOG,
                FLEX_LEAK_BLOG,
            ),
        ),
    ),
    _p(
        20297,
        "pAAV-EF1a-double floxed-hChR2(H134R)-mCherry-WPRE-HGHpA",
        "AAV DIO ChR2-mCherry",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of an opsin swap inside the double-floxed cassette.",
        gotchas=(
            _gotcha(
                "inverted_orf",
                "ChR2-mCherry starts inverted. Inventory 'mCherry' hits are "
                "on the wrong strand until Cre.",
                BMC_LOX2272,
                BMC_LOX2272,
            ),
            _gotcha(
                "flex_leak",
                "lox2272×lox2272 recombination is ~10× weaker than loxP×loxP "
                "in FLEX plasmids (BMC Biotechnol 2018), so flip-excision is "
                "not symmetric on the map.",
                BMC_LOX2272,
                BMC_LOX2272,
            ),
        ),
    ),
    _p(
        20298,
        "pAAV-EF1a-double floxed-hChR2(H134R)-EYFP-WPRE-HGHpA",
        "AAV DIO ChR2-EYFP; dual full maps",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of an opsin/fluorophore swap in the DIO cassette.",
        sequence_source="all",
        gotchas=(
            _gotcha(
                "multiple_full_maps",
                "Addgene-verified and depositor full maps both exist.",
                ADDGENE_QC,
                ADDGENE_QC,
            ),
            _gotcha(
                "inverted_orf",
                "EYFP is inverted relative to EF1a until Cre. 20297 is the "
                "mCherry twin; papers cite either id for 'DIO-ChR2'.",
                BMC_LOX2272,
                BMC_LOX2272,
            ),
        ),
    ),
    _p(
        44361,
        "pAAV-hSyn-DIO-hM3D(Gq)-mCherry",
        "AAV DIO hM3Dq DREADD",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a DREADD/fluorophore swap in the DIO cassette.",
        gotchas=(
            _gotcha(
                "naming_collision",
                "50474 is constitutive pAAV-hSyn-hM3D(Gq)-mCherry (no DIO). "
                "44361 is the Cre-dependent DIO version. The names differ by "
                "one token.",
                "Addgene 44361 vs 50474",
                "https://www.addgene.org/44361/",
            ),
            _gotcha(
                "inverted_orf",
                "hM3D-mCherry is inverted. An inventory 'mCherry' hit is not "
                "evidence the construct is on.",
                FLEX_LEAK_BLOG,
                FLEX_LEAK_BLOG,
            ),
        ),
    ),
    _p(
        26973,
        "pAAV-hSyn-hChR2(H134R)-EYFP",
        "AAV optogenetic",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a cargo swap between ITRs.",
        sequence_source="all",
        gotchas=(
            _gotcha(
                "itr_deletion",
                "Addgene NGS vs depositor full maps: 5' ITR lost the 11 nt "
                "C-C' segment; 3' ITR unchanged (NAR 2025 Table S4).",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
            _gotcha(
                "depositor_vs_addgene_mismatch",
                "Both a depositor full sequence and an Addgene-verified full "
                "sequence are public; they are not the same molecule.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
            _gotcha(
                "multiple_full_maps",
                "Inventory must keep both full GBKs or the ITR conflict is invisible.",
                ADDGENE_ITR_BLOG,
                ADDGENE_ITR_BLOG,
            ),
        ),
    ),
    _p(
        112168,
        "pAAV.CAG-FLEX.iGABASnFR.F102Y.Y137L",
        "AAV FLEX sensor; NAR 2025 ITR match control",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a sensor swap in the FLEX cassette.",
        sequence_source="all",
        gotchas=(
            _gotcha(
                "depositor_vs_addgene_mismatch",
                "Same study as 112159. NAR 2025 reports the ITR sequences "
                "match, unlike siblings 112159/112173, but the two full maps "
                "still differ by 3 bp.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
            _gotcha(
                "inverted_orf",
                "FLEX cassette: the sensor ORF starts inverted.",
                FLEX_LEAK_BLOG,
                FLEX_LEAK_BLOG,
            ),
            _gotcha(
                "multiple_full_maps",
                "Public depositor-full and addgene-full maps both exist.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
        ),
    ),
    _p(
        112159,
        "pAAV.hSynap.iGABASnFR",
        "AAV sensor",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a sensor/promoter swap between ITRs.",
        gotchas=(
            _gotcha(
                "itr_deletion",
                "NAR 2025: Addgene sequencing is grossly different in the ITR "
                "relative to the depositor reference.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
            _gotcha(
                "backbone_orientation",
                "NAR 2025: backbone of 112159 and 112173 also appear flipped "
                "versus the depositor maps. The live sequences page now shows "
                "only an Addgene-verified full map.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
        ),
    ),
    _p(
        60229,
        "AAV:ITR-U6-sgRNA(backbone)-pCBh-Cre-WPRE-hGHpA-ITR",
        "AAV CRISPR Cre",
        ("mammalian", "viral"),
        "oligo_gg",
        2,
        "sgRNA oligo Golden Gate plus an AAV ITR backbone.",
        gotchas=(
            _gotcha(
                "itr_deletion",
                "Four plasmids from one deposit (60226, 60227, 60229, 60231) "
                "share the same 11-bp 5' ITR C-C' deletion versus depositor maps.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
        ),
    ),
    _p(
        104588,
        "pAAV-EFS-SpCas9",
        "AAV SpCas9",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a promoter/Cas9 swap between ITRs.",
        gotchas=(
            _gotcha(
                "itr_deletion",
                "Blue-flame AAV transfer plasmid; NAR 2025 Table S4 marks a "
                "5' ITR 11-nt C-C' loss versus the depositor map.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
        ),
    ),
    _p(
        83900,
        "pAAV-mDlx-GFP-Fishell-1",
        "AAV reporter",
        ("mammalian", "viral"),
        "gibson",
        3,
        "3-fragment Gibson of a promoter/reporter swap between ITRs.",
        gotchas=(
            _gotcha(
                "itr_deletion",
                "NAR 2025 Table S4: 5' ITR lost the 11 nt highlighted in Fig. 3A.",
                NAR_PLASMID_ERRORS,
                NAR_PLASMID_ERRORS_URL,
            ),
        ),
    ),
    _p(
        21870,
        "pKJ1712",
        "custom oligo vector",
        ("bacterial",),
        "restriction",
        2,
        "Oligo clone into the BamHI region that the paper figure mistyped.",
        gotchas=(
            _gotcha(
                "paper_vs_sequence_typo",
                "Depositor notes: Fig. S5 of the paper has GAATTCTGT-C-G near "
                "BamHI; the Addgene sequence and Fig. S1 have G. Not a "
                "functional mutation — a figure typo.",
                "Addgene pKJ1712 notes",
                PKJ1712_NOTES,
            ),
        ),
    ),
    _p(
        128034,
        "pcDNA3.1-HA",
        "mammalian HA-tag empty backbone",
        ("mammalian",),
        "gibson",
        2,
        "2-fragment Gibson of a CDS after the HA tag.",
        gotchas=(
            _gotcha(
                "splice_motif",
                "A common HA codon choice encodes a 3' splice site and is "
                "present in this Addgene empty backbone (cited 23 times in "
                "the EMBO J 2026 analysis).",
                EMBO_SPLICE,
                EMBO_SPLICE_URL,
            ),
        ),
    ),
    _p(
        23007,
        "pCMV-M1",
        "mammalian CMV expression",
        ("mammalian",),
        "gibson",
        2,
        "2-fragment Gibson of a CDS into the CMV cassette.",
        gotchas=(
            _gotcha(
                "splice_motif",
                "EMBO J 2026 scored splice motifs in a pCMV MCS taken from "
                "Addgene 23007. The live record is pCMV-M1, not an empty "
                "pCMV backbone.",
                EMBO_SPLICE,
                EMBO_SPLICE_URL,
            ),
        ),
    ),
)


def subset_gbk_dir() -> Path:
    """Directory of tracked full-sequence GBKs for this subset."""
    return Path(__file__).resolve().parent / "addgene_inventory_subset_gbk"


def subset_plasmids() -> tuple[SubsetPlasmid, ...]:
    """Return the curated catalog after validating invariants."""
    validate_subset(SUBSET)
    return SUBSET


def plasmid_ids(entries: Sequence[SubsetPlasmid] | None = None) -> list[int]:
    """Addgene ids in catalog order."""
    return [entry.plasmid_id for entry in (entries or subset_plasmids())]


def validate_subset(entries: Sequence[SubsetPlasmid]) -> None:
    """Raise ValueError if the catalog is internally inconsistent."""
    seen: set[int] = set()
    if not entries:
        raise ValueError("subset catalog is empty")
    fragment_counts: set[int] = set()
    methods: set[str] = set()
    for entry in entries:
        if entry.plasmid_id in seen:
            raise ValueError(f"duplicate plasmid id {entry.plasmid_id}")
        seen.add(entry.plasmid_id)
        if entry.plasmid_id <= 0:
            raise ValueError(f"invalid plasmid id {entry.plasmid_id}")
        if not entry.name.strip():
            raise ValueError(f"{entry.plasmid_id} is missing a name")
        if not entry.role.strip():
            raise ValueError(f"{entry.plasmid_id} is missing a role")
        if entry.sequence_source not in ALLOWED_SEQUENCE_SOURCES:
            raise ValueError(
                f"{entry.plasmid_id} has unknown sequence_source "
                f"{entry.sequence_source!r}"
            )
        if entry.assembly_method not in ALLOWED_ASSEMBLY_METHODS:
            raise ValueError(
                f"{entry.plasmid_id} has unknown assembly_method "
                f"{entry.assembly_method!r}"
            )
        if entry.assembly_fragments < 1:
            raise ValueError(f"{entry.plasmid_id} has no assembly fragments")
        if not entry.assembly_note.strip():
            raise ValueError(f"{entry.plasmid_id} is missing an assembly note")
        fragment_counts.add(entry.assembly_fragments)
        methods.add(entry.assembly_method)
        unknown_hosts = set(entry.hosts) - ALLOWED_HOSTS
        if unknown_hosts:
            raise ValueError(
                f"{entry.plasmid_id} has unknown hosts {sorted(unknown_hosts)}"
            )
        if not entry.hosts:
            raise ValueError(f"{entry.plasmid_id} has no hosts")
        for gotcha in entry.gotchas:
            if gotcha.kind not in ALLOWED_GOTCHA_KINDS:
                raise ValueError(
                    f"{entry.plasmid_id} has unknown gotcha kind {gotcha.kind!r}"
                )
            if not gotcha.summary.strip():
                raise ValueError(f"{entry.plasmid_id} gotcha is missing a summary")
            if not gotcha.citation.strip() or not gotcha.citation_url.strip():
                raise ValueError(f"{entry.plasmid_id} gotcha is missing a citation")
    if TWO_FRAGMENT_ASSEMBLY not in fragment_counts:
        raise ValueError("catalog needs a 2-fragment assembly")
    if max(fragment_counts) < CASSETTE_ASSEMBLY_FRAGMENTS:
        raise ValueError("catalog needs an 8-or-more-fragment Golden Gate assembly")
    if HIGH_COMPLEXITY_GG_FRAGMENTS not in fragment_counts:
        raise ValueError("catalog needs the 24-fragment Golden Gate destination")
    missing_methods = ALLOWED_ASSEMBLY_METHODS - methods
    if missing_methods:
        raise ValueError(f"catalog missing assembly methods {sorted(missing_methods)}")


def catalog_records(
    entries: Sequence[SubsetPlasmid] | None = None,
) -> list[dict[str, Any]]:
    """JSON-ready catalog rows."""
    return [asdict(entry) for entry in (entries or subset_plasmids())]


def annotate_inventory_with_subset(
    inventory: Mapping[str, Any],
    download_records: Iterable[Mapping[str, Any]],
    entries: Sequence[SubsetPlasmid] | None = None,
) -> dict[str, Any]:
    """Attach catalog metadata and same-plasmid map conflicts to an inventory."""
    catalog = {entry.plasmid_id: entry for entry in (entries or subset_plasmids())}
    by_plasmid: dict[int, list[dict[str, Any]]] = {}
    for record in download_records:
        plasmid_id = int(record["plasmid_id"])
        by_plasmid.setdefault(plasmid_id, []).append(dict(record))

    conflicting_full_maps = []
    identical_full_maps = []
    for plasmid_id, records in sorted(by_plasmid.items()):
        hashes = {str(item.get("sha256") or "") for item in records}
        hashes.discard("")
        if len(records) < MAPS_NEEDED_TO_COMPARE:
            continue
        payload = {
            "plasmid_id": plasmid_id,
            "filenames": [str(item.get("filename") or "") for item in records],
            "sequence_ids": [str(item.get("sequence_id") or "") for item in records],
            "source_buckets": [
                str(item.get("source_bucket") or "") for item in records
            ],
        }
        if len(hashes) > 1:
            conflicting_full_maps.append(payload)
        elif len(hashes) == 1:
            identical_full_maps.append(payload)

    return {
        "schema_version": 1,
        "catalog": catalog_records(list(catalog.values())),
        "download_records": list(download_records),
        "inventory": dict(inventory),
        "gotcha_index": {
            "conflicting_full_maps": conflicting_full_maps,
            "identical_full_maps": identical_full_maps,
            "files_with_no_part_features": list(
                inventory.get("summary", {}).get("files_with_no_part_features") or []
            ),
            "files_with_no_primers": list(
                inventory.get("summary", {}).get("files_with_no_primers") or []
            ),
            "duplicate_sequences": dict(
                inventory.get("indexes", {}).get("duplicate_sequences") or {}
            ),
        },
    }
