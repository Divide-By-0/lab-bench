"""PCR simulator v2 with reliable circular-origin amplification."""

from __future__ import annotations

from typing import Any

from lab_bench_2.cloning_simulators.legacy import simulate_pcr_legacy

MIN_ANNEAL_LENGTH = 15


def _sequence(value: Any) -> str:
    return str(value.sequence if hasattr(value, "sequence") else value).upper()


def _reverse_complement(sequence: str) -> str:
    from labbench2.cloning.utils import reverse_complement

    return str(reverse_complement(sequence))


def _circular_occurrences(sequence: str, motif: str) -> tuple[int, ...]:
    doubled = sequence + sequence[: max(0, len(motif) - 1)]
    return tuple(
        index for index in range(len(sequence)) if doubled.startswith(motif, index)
    )


def _longest_bindings(
    template: str,
    primer: str,
    *,
    reverse: bool,
) -> tuple[int, tuple[int, ...]]:
    for length in range(len(primer), MIN_ANNEAL_LENGTH - 1, -1):
        annealing = primer[-length:]
        motif = _reverse_complement(annealing) if reverse else annealing
        starts = _circular_occurrences(template, motif)
        if starts:
            return length, starts
    return 0, ()


def _circular_interval(sequence: str, start: int, end: int) -> str:
    if start <= end:
        return sequence[start:end]
    return sequence[start:] + sequence[:end]


def circular_origin_amplicon(
    sequence: Any,
    forward_primer: Any,
    reverse_primer: Any,
) -> Any:
    """Construct a unique exact-match PCR product across a circular origin.

    Primer 5' tails are retained. The longest exact 3' annealing segment of each
    primer is used, and ambiguous binding sites fail closed.
    """
    from labbench2.cloning.sequence_models import BioSequence

    template = _sequence(sequence)
    forward = _sequence(forward_primer)
    reverse = _sequence(reverse_primer)
    forward_length, forward_starts = _longest_bindings(template, forward, reverse=False)
    reverse_length, reverse_starts = _longest_bindings(template, reverse, reverse=True)
    if not forward_starts or not reverse_starts:
        raise ValueError(
            "PCR simulation found no unique exact primer pair on the circular template."
        )
    if len(forward_starts) != 1 or len(reverse_starts) != 1:
        raise ValueError(
            "PCR simulation found ambiguous primer binding sites on the circular template."
        )

    forward_start = forward_starts[0]
    reverse_start = reverse_starts[0]
    middle = _circular_interval(
        template,
        (forward_start + forward_length) % len(template),
        reverse_start,
    )
    amplicon = forward + middle + _reverse_complement(reverse)
    return BioSequence(
        sequence=amplicon,
        is_circular=False,
        description="PCR product (v2 circular-origin fallback)",
    )


async def simulate_pcr_v2(
    sequence: Any,
    forward_primer: Any,
    reverse_primer: Any,
) -> Any:
    """Run legacy PCR first, then repair false circular-origin no-amplicon calls."""
    try:
        return await simulate_pcr_legacy(sequence, forward_primer, reverse_primer)
    except ValueError as exc:
        if (
            not getattr(sequence, "is_circular", False)
            or "no amplicon" not in str(exc).lower()
        ):
            raise
        return circular_origin_amplicon(sequence, forward_primer, reverse_primer)
