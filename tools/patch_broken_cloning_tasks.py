#!/usr/bin/env python3
"""Repair three cloning tasks that are unsolvable for environment reasons.

These are DATA fixes applied to the local task cache (~/.cache/labbench2/...). Each
task's science is untouched -- what changes is only the thing that made a correct
answer impossible to express or impossible to match.

  61e4b666  the insert template ships as an 11-record FASTA. BioSequence.from_fasta
            hard-rejects multi-record input, so any protocol referencing it dies before
            execution (upstream issue #16). 0 of 27 published attempts ever reached the
            assembly step. Record 0 (ENST00000612748.1, 2585 bp) is the actual template:
            it sits in the reference assembly at offset 2868 with exactly one mismatch,
            position 295 C->A, which is the C295A mutation the prompt asks for. Rewritten
            as a single-record FASTA containing that record.

  31d22b22  the prompt asks for dCas9-IRES-BlastR, but the reference assembly contains
            dCas9 and the IRES and then no blasticidin cassette at all -- not one base of
            it (upstream issue #32). The 454 bp BSD region of pLV-EF1a-IRES-Blast is
            spliced in immediately after the IRES so the reference matches the prompt.

  a4bf037c  the only backbone file is "addgene-plasmid-105539-sequence-457689 (1).gbk".
            The protocol DSL tokenizer rejects a bare filename containing a space, and
            quoting it produced a DNA literal rather than a file reference, so there was
            no working syntax (upstream PR #34). The browser "(1)" suffix and the opaque
            Addgene accession are both replaced with a name the prompt actually implies.

NOTE: tasks patched here are NO LONGER comparable to published LAB-Bench 2 numbers.
Report them separately.
"""
from __future__ import annotations

import shutil
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
from Bio import SeqIO  # noqa: E402

CACHE = Path.home() / ".cache" / "labbench2" / "labbench2-data-public"
IDS = {
    "peg10": "61e4b666-1ee5-4046-b304-d57e183c8593",
    "dcas9": "31d22b22-0d48-41a4-88ed-b46ff451be52",
    "npas4": "a4bf037c-2477-4cca-9ca3-12c5ee63c44f",
}


def _backup(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".orig")
    if not b.exists() and p.exists():
        shutil.copy2(p, b)


def fix_peg10() -> str:
    d = CACHE / "cloning" / IDS["peg10"]
    f = d / "Homo_sapiens_ENST00000612748_1_sequence.fa"
    recs = list(SeqIO.parse(str(f), "fasta"))
    if len(recs) == 1:
        return "peg10: already single-record, skipped"
    _backup(f)
    SeqIO.write([recs[0]], str(f), "fasta")
    return f"peg10: {len(recs)} records -> 1 ({recs[0].id}, {len(recs[0].seq)} bp)"


def fix_dcas9() -> str:
    ref = CACHE / "validation" / f"{IDS['dcas9']}_assembled.fa"
    src = CACHE / "cloning" / IDS["dcas9"] / "plv-ef1a-ires-blast.gb"
    donor = str(SeqIO.read(str(src), "genbank").seq).upper()
    ires, blast = donor[6768:7318], donor[7318:7772]   # IRES, then the BSD cassette
    rec = SeqIO.read(str(ref), "fasta")
    seq = str(rec.seq).upper()
    if blast in seq:
        return "dcas9: BlastR already present, skipped"
    i = seq.find(ires)
    if i < 0:
        return "dcas9: IRES not found in reference -- NOT patched"
    _backup(ref)
    rec.seq = type(rec.seq)(seq[: i + len(ires)] + blast + seq[i + len(ires) :])
    SeqIO.write([rec], str(ref), "fasta")
    return f"dcas9: inserted {len(blast)} bp BlastR after IRES ({len(seq)} -> {len(rec.seq)} bp)"


def fix_npas4() -> str:
    d = CACHE / "cloning" / IDS["npas4"]
    old = d / "addgene-plasmid-105539-sequence-457689 (1).gbk"
    new = d / "addgene-plasmid-105539-sequence-457689.gbk"
    if new.exists():
        return "npas4: already renamed, skipped"
    if not old.exists():
        return "npas4: source file missing -- NOT patched"
    # REASON: add a DSL-expressible copy rather than renaming. file_downloader.fetch()
    # re-downloads anything missing from the task directory, so an unlinked original
    # simply reappears on the next run and the patch silently undoes itself.
    shutil.copy2(old, new)
    old.unlink(missing_ok=True)
    return f"npas4: added {new.name!r} (original re-downloads; removed if present)"


if __name__ == "__main__":
    for fn in (fix_peg10, fix_dcas9, fix_npas4):
        print("  " + fn())
