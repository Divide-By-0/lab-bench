"""Exact normalized edit similarity for double-stranded cloning products."""

from __future__ import annotations

from typing import Any


def _edit_distance(first: str, second: str) -> int:
    import edlib  # type: ignore[import-not-found]

    return int(edlib.align(first, second, mode="NW", task="distance")["editDistance"])


def _circular_edit_distance(circular: str, other: str) -> int:
    """Find the best edit distance to any origin in a circular molecule."""
    import edlib  # type: ignore[import-not-found]

    result = edlib.align(other, circular + circular, mode="HW", task="distance")
    # HW alignment intentionally leaves the unused copy of the circle free.
    # This length lower bound prevents a short exact substring from being
    # mistaken for a complete circular molecule.
    return max(int(result["editDistance"]), abs(len(circular) - len(other)))


def sequence_similarity_v2(first: Any, second: Any) -> float:
    """Compare physical dsDNA independent of strand and circular origin.

    Edlib supplies the exact unit-cost edit distance.  Its infix alignment mode
    compares a query to every circular origin in one pass, avoiding the prior
    exact-anchor heuristic and exhaustive Python rotation loop.
    """
    from labbench2.cloning.utils import is_rotation, reverse_complement

    first_sequence = str(first.sequence).upper()
    second_sequence = str(second.sequence).upper()
    if not first_sequence and not second_sequence:
        return 1.0
    if not first_sequence or not second_sequence:
        return 0.0

    second_reverse = str(reverse_complement(second_sequence)).upper()
    circular = bool(first.is_circular or second.is_circular)
    if circular and len(first_sequence) == len(second_sequence):
        if is_rotation(first_sequence, second_sequence) or is_rotation(
            first_sequence, second_reverse
        ):
            return 1.0

    if circular:
        circle, other = (
            (first_sequence, second_sequence)
            if first.is_circular
            else (second_sequence, first_sequence)
        )
        distances = (
            _circular_edit_distance(circle, other),
            _circular_edit_distance(circle, str(reverse_complement(other)).upper()),
        )
    else:
        distances = (
            _edit_distance(first_sequence, second_sequence),
            _edit_distance(first_sequence, second_reverse),
        )
    distance = min(distances)
    return max(0.0, 1.0 - distance / max(len(first_sequence), len(second_sequence)))
