"""Candidate-aware Gibson assembly backed by pydna."""

from __future__ import annotations

from typing import Any

from lab_bench_2.cloning_simulators.molecular import (
    MAX_CANDIDATES,
    assembly_parts,
    collect_library_products,
    from_pydna,
    label_inputs,
)


def gibson_v2(
    sequences: list[Any],
    min_overlap: int = 10,
    max_overlap: int = 60,
    max_candidates: int = MAX_CANDIDATES,
) -> list[Any]:
    """Enumerate pydna Gibson products across all non-empty input subsets.

    ``max_overlap`` remains in the public signature for protocol compatibility.
    pydna deliberately uses complete maximal homologies rather than truncating
    biologically valid overlaps at an arbitrary upper length.
    """
    from pydna.assembly2 import gibson_assembly  # type: ignore[import-untyped]

    if not sequences:
        return []
    if min_overlap <= 0 or max_overlap < min_overlap:
        raise ValueError("Gibson overlap bounds are invalid")

    records = label_inputs(sequences)
    candidates = collect_library_products(
        records,
        lambda subset: gibson_assembly(
            subset,
            limit=min_overlap,
            circular_only=False,
        ),
        max_candidates=max_candidates,
    )
    circular = [candidate for candidate in candidates if candidate.record.circular]
    selected = circular or candidates
    selected.sort(
        key=lambda candidate: (
            -len(candidate.source_indices),
            -len(candidate.record),
            str(candidate.record.seguid()),
        )
    )
    return [
        from_pydna(
            candidate.record,
            prefix="gibson-v2",
            description=(
                "Gibson candidate simulated by pydna from "
                f"{len(candidate.source_indices)} input fragments"
            ),
            assembly_parts=assembly_parts(candidate.record, candidate.source_indices),
        )
        for candidate in selected
    ]
