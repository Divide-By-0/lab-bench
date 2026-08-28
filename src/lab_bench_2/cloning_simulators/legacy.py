"""Archived access to the pinned LAB-Bench 2 cloning simulator behavior.

These wrappers intentionally preserve the behavior from the upstream
``labbench2`` dependency pinned in ``pyproject.toml``. New evaluation runs use
the v2 implementations, but the wrappers remain available for reproducing old
scores and traces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast


async def simulate_pcr_legacy(
    sequence: Any,
    forward_primer: Any,
    reverse_primer: Any,
) -> Any:
    """Run the archived Go-backed PCR simulator."""
    from labbench2.cloning.simulate_pcr import simulate_pcr

    return await simulate_pcr(sequence, forward_primer, reverse_primer)


def goldengate_legacy(
    sequences: list[Any], enzymes: str, min_fragment_length: int = 30
) -> list[Any]:
    """Run the archived pairwise-only Golden Gate simulator."""
    from labbench2.cloning.goldengate import goldengate

    return cast(list[Any], goldengate(sequences, enzymes, min_fragment_length))


def gibson_legacy(
    sequences: list[Any], min_overlap: int = 10, max_overlap: int = 60
) -> list[Any]:
    """Run the archived name-keyed, terminal-only Gibson simulator."""
    from labbench2.cloning.gibson import gibson

    return cast(list[Any], gibson(sequences, min_overlap, max_overlap))


def restriction_assemble_legacy(first: Any, second: Any) -> list[Any]:
    """Run the archived early-return restriction assembly simulator."""
    from labbench2.cloning.restriction_enzyme import restriction_assemble

    return cast(list[Any], restriction_assemble(first, second))


async def execute_protocol_legacy(expression: str, base_dir: Path) -> list[Any]:
    """Execute a protocol with the archived upstream operation implementations."""
    from labbench2.cloning.cloning_protocol import CloningProtocol

    return cast(list[Any], await CloningProtocol(expression).run(base_dir))
