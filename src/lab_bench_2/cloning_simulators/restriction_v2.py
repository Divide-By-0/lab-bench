"""Sticky-end restriction assembly backed by pydna ligation."""

from __future__ import annotations

from typing import Any

from lab_bench_2.cloning_simulators.molecular import (
    MAX_CANDIDATES,
    assembly_parts,
    collect_library_products,
    from_pydna,
    label_inputs,
)


def restriction_assemble_v2(
    first: Any,
    second: Any,
    max_candidates: int = MAX_CANDIDATES,
) -> list[Any]:
    """Enumerate circular products from two genuinely compatible DNA ends.

    Nested v2 digests carry a pydna double-stranded record, including overhang
    sequence, strand, and polarity.  Unlike the prior implementation, failure
    to ligate returns no product rather than returning unassembled inputs.
    """
    from pydna.assembly2 import ligation_assembly  # type: ignore[import-untyped]

    records = label_inputs((first, second))
    candidates = collect_library_products(
        records,
        lambda subset: ligation_assembly(
            subset,
            allow_blunt=False,
            allow_partial_overlap=False,
            circular_only=True,
        ),
        max_candidates=max_candidates,
    )
    candidates.sort(
        key=lambda candidate: (
            -len(candidate.source_indices),
            -len(candidate.record),
            str(candidate.record.seguid()),
        )
    )
    return [
        from_pydna(
            candidate.record,
            prefix="restriction-assemble-v2",
            description=(
                "Restriction-ligation candidate simulated by pydna from "
                f"{len(candidate.source_indices)} input fragments"
            ),
            assembly_parts=assembly_parts(candidate.record, candidate.source_indices),
        )
        for candidate in candidates
    ]
