"""PCR simulation backed by pydna's primer-annealing model."""

from __future__ import annotations

from typing import Any

from lab_bench_2.cloning_simulators.molecular import from_pydna, to_pydna

MIN_ANNEAL_LENGTH = 15


def _sequence(value: Any) -> str:
    return str(value.sequence if hasattr(value, "sequence") else value).upper()


def circular_origin_amplicon(
    sequence: Any,
    forward_primer: Any,
    reverse_primer: Any,
) -> Any:
    """Simulate a unique PCR product, including inverse/circular-origin PCR.

    pydna searches exact 3' primer footprints, preserves non-annealing 5' tails,
    handles circular templates, and rejects zero or non-specific products.
    """
    from pydna.amplify import pcr  # type: ignore[import-untyped]
    from pydna.primer import Primer  # type: ignore[import-untyped]

    try:
        product = pcr(
            Primer(_sequence(forward_primer)),
            Primer(_sequence(reverse_primer)),
            to_pydna(sequence),
            limit=MIN_ANNEAL_LENGTH,
        )
    except ValueError as exc:
        raise ValueError(f"PCR simulation failed: {exc}") from exc
    return from_pydna(
        product,
        prefix="pcr-v2",
        description="PCR product simulated by pydna",
    )


async def simulate_pcr_v2(
    sequence: Any,
    forward_primer: Any,
    reverse_primer: Any,
) -> Any:
    """Run pydna PCR while retaining double-stranded product metadata."""
    return circular_origin_amplicon(sequence, forward_primer, reverse_primer)
