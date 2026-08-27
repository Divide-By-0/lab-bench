"""Candidate-aware Gibson assembly simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_CANDIDATES = 256


@dataclass(frozen=True)
class _GibsonAssembly:
    sequence: str
    fragment_count: int


def _overlap(left: str, right: str, minimum: int, maximum: int) -> int:
    upper = min(len(left), len(right), maximum)
    for length in range(upper, minimum - 1, -1):
        if left[-length:] == right[:length]:
            return length
    return 0


def _self_overlap(sequence: str, minimum: int, maximum: int) -> int:
    upper = min(len(sequence) // 2, maximum)
    for length in range(upper, minimum - 1, -1):
        if sequence[-length:] == sequence[:length]:
            return length
    return 0


def _equivalent_circle(first: str, second: str) -> bool:
    from labbench2.cloning.utils import is_rotation, reverse_complement

    return bool(
        is_rotation(first, second) or is_rotation(first, reverse_complement(second))
    )


def gibson_v2(
    sequences: list[Any],
    min_overlap: int = 10,
    max_overlap: int = 60,
    max_candidates: int = MAX_CANDIDATES,
) -> list[Any]:
    """Enumerate Gibson products without treating the first as authoritative.

    Unlike the archived simulator, fragment identity is tracked by input position,
    circularization is considered even when another extension is also possible,
    and reverse-complement-equivalent circular products are deduplicated.
    """
    from labbench2.cloning.sequence_models import BioSequence, make_pretty_id
    from labbench2.cloning.utils import reverse_complement

    if not sequences:
        return []
    oriented = tuple(
        (sequence.sequence.upper(), reverse_complement(sequence.sequence.upper()))
        for sequence in sequences
    )
    circulars: list[_GibsonAssembly] = []
    linears: dict[str, _GibsonAssembly] = {}

    def collect_circle(sequence: str, fragment_count: int) -> None:
        if any(
            _equivalent_circle(existing.sequence, sequence) for existing in circulars
        ):
            return
        if len(circulars) >= max_candidates:
            raise ValueError(
                f"Gibson assembly exceeded the {max_candidates}-candidate safety limit"
            )
        circulars.append(_GibsonAssembly(sequence, fragment_count))

    def extend(assembled: str, used: frozenset[int]) -> None:
        closure = _self_overlap(assembled, min_overlap, max_overlap)
        if closure:
            collect_circle(assembled[:-closure], len(used))

        extended = False
        for index, choices in enumerate(oriented):
            if index in used:
                continue
            for candidate in choices:
                overlap = _overlap(assembled, candidate, min_overlap, max_overlap)
                if overlap:
                    extended = True
                    extend(assembled + candidate[overlap:], used | {index})
        if not closure and not extended:
            linears.setdefault(assembled, _GibsonAssembly(assembled, len(used)))

    for index, choices in enumerate(oriented):
        for seed in dict.fromkeys(choices):
            extend(seed, frozenset({index}))

    products = circulars or list(linears.values())
    products.sort(key=lambda product: (-product.fragment_count, -len(product.sequence)))
    return [
        BioSequence(
            sequence=product.sequence,
            is_circular=bool(circulars),
            name=make_pretty_id("gibson-v2"),
            description=(
                f"Gibson v2 candidate assembled from {product.fragment_count} fragments"
            ),
        )
        for product in products
    ]
