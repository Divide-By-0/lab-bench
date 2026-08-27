"""Candidate-aware sticky-end restriction assembly."""

from __future__ import annotations

from typing import Any

from lab_bench_2.cloning_simulators.golden_gate_v2 import (
    MAX_CANDIDATES,
    assemble_restriction_fragments_v2,
)


def restriction_assemble_v2(
    first: Any,
    second: Any,
    max_candidates: int = MAX_CANDIDATES,
) -> list[Any]:
    """Enumerate self-ligation and two-fragment circular products.

    The archived implementation returns immediately when the first fragment can
    self-ligate, which suppresses an otherwise valid first-plus-second product.
    """
    from labbench2.cloning.sequence_models import BioSequence, make_pretty_id

    assemblies = assemble_restriction_fragments_v2(
        [first, second], max_candidates=max_candidates
    )
    assemblies.sort(
        key=lambda assembly: (-assembly.fragment_count, -len(assembly.sequence))
    )
    if not assemblies:
        return [first, second]
    products: list[Any] = []
    for assembly in assemblies:
        product = BioSequence(
            sequence=assembly.sequence,
            is_circular=True,
            name=make_pretty_id("restriction-assemble-v2"),
            description=(
                "Restriction assembly v2 candidate assembled from "
                f"{assembly.fragment_count} fragments"
            ),
        )
        object.__setattr__(product, "_assembly_parts", assembly.parts)
        products.append(product)
    return products
