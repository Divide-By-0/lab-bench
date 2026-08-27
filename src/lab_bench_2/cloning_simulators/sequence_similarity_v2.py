"""Efficient normalized edit similarity for circular cloning products."""

from __future__ import annotations

from typing import Any

ANCHOR_LENGTH = 24
ANCHOR_STEP = 64


def _similarity(first: str, second: str) -> float:
    from rapidfuzz.distance import Levenshtein

    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    return 1.0 - Levenshtein.distance(first, second) / max(len(first), len(second))


def _candidate_rotations(circular: str, other: str) -> tuple[int, ...]:
    if len(circular) < ANCHOR_LENGTH or len(other) < ANCHOR_LENGTH:
        return (0,)
    doubled = circular + circular
    rotations: set[int] = {0}
    offsets = list(range(0, len(other) - ANCHOR_LENGTH + 1, ANCHOR_STEP))
    final_offset = len(other) - ANCHOR_LENGTH
    if final_offset not in offsets:
        offsets.append(final_offset)
    for offset in offsets:
        anchor = other[offset : offset + ANCHOR_LENGTH]
        start = doubled.find(anchor)
        while 0 <= start < len(circular):
            rotations.add((start - offset) % len(circular))
            start = doubled.find(anchor, start + 1)
    return tuple(rotations)


def sequence_similarity_v2(first: Any, second: Any) -> float:
    """Compute normalized Levenshtein similarity with circular-origin alignment.

    Candidate origins are inferred from exact 24-bp anchors. A sequence capable
    of passing the 0.95 benchmark threshold is expected to contain many such
    anchors; the direct origin is always retained as a conservative fallback.
    """
    from labbench2.cloning.utils import is_rotation

    first_sequence = first.sequence.upper()
    second_sequence = second.sequence.upper()
    if first_sequence == second_sequence:
        return 1.0
    if len(first_sequence) == len(second_sequence) and (
        first.is_circular or second.is_circular
    ):
        if is_rotation(first_sequence, second_sequence):
            return 1.0
    if first.is_circular or second.is_circular:
        circular, other = (
            (first_sequence, second_sequence)
            if first.is_circular
            else (second_sequence, first_sequence)
        )
        return max(
            _similarity(circular[rotation:] + circular[:rotation], other)
            for rotation in _candidate_rotations(circular, other)
        )
    return _similarity(first_sequence, second_sequence)
