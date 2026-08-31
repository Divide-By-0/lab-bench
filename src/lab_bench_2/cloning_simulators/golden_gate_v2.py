"""Golden Gate simulation backed by pydna restriction/ligation assembly."""

from __future__ import annotations

from typing import Any

from lab_bench_2.cloning_simulators.molecular import (
    MAX_CANDIDATES,
    assembly_parts,
    collect_library_products,
    from_pydna,
    label_inputs,
    resolve_enzymes,
)


def goldengate_v2(
    sequences: list[Any],
    enzymes: str,
    min_fragment_length: int = 30,
    max_candidates: int = MAX_CANDIDATES,
) -> list[Any]:
    """Digest and assemble all circular Golden Gate candidates with pydna.

    pydna models the enzyme's actual Watson/Crick cut positions and sticky-end
    polarity.  Input subsets are evaluated so empty-vector and other competing
    products remain visible to the verifier.

    ``min_fragment_length`` is retained for API compatibility.  The library
    assembly model determines which restriction fragments participate instead
    of silently discarding short, potentially functional fragments.
    """
    from pydna.assembly2 import golden_gate_assembly  # type: ignore[import-untyped]

    if not sequences:
        return []
    if min_fragment_length < 0:
        raise ValueError("Minimum Golden Gate fragment length cannot be negative")

    enzyme_names = tuple(value.strip() for value in enzymes.split(",") if value.strip())
    enzyme_objects = list(resolve_enzymes(enzyme_names))
    records = label_inputs(sequences)
    candidates = collect_library_products(
        records,
        lambda subset: golden_gate_assembly(
            subset,
            enzyme_objects,
            allow_blunt=False,
            circular_only=True,
        ),
        max_candidates=max_candidates,
    )
    candidates.sort(
        key=lambda candidate: (
            len(candidate.record.seq.get_cutsites(*enzyme_objects)),
            -len(candidate.source_indices),
            -len(candidate.record),
            str(candidate.record.seguid()),
        )
    )
    return [
        from_pydna(
            candidate.record,
            prefix="goldengate-v2",
            description=(
                "Golden Gate candidate simulated by pydna from "
                f"{len(candidate.source_indices)} input molecules; retained "
                "restriction sites: "
                f"{len(candidate.record.seq.get_cutsites(*enzyme_objects))}"
            ),
            assembly_parts=assembly_parts(candidate.record, candidate.source_indices),
        )
        for candidate in candidates
    ]
