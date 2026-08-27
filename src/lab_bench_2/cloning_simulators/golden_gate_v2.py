"""Golden Gate simulator v2 with multi-fragment product enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_CANDIDATES = 256


@dataclass(frozen=True)
class _OrientedFragment:
    index: int
    sequence: str
    left_overhang: int
    right_overhang: int
    orientation: int

    @property
    def left(self) -> str:
        return self.sequence[: self.left_overhang]

    @property
    def right(self) -> str:
        return self.sequence[-self.right_overhang :]


@dataclass(frozen=True)
class _Assembly:
    sequence: str
    fragment_count: int


def _orientations(fragment: Any, index: int) -> tuple[_OrientedFragment, ...]:
    from labbench2.cloning.utils import reverse_complement

    forward = _OrientedFragment(
        index=index,
        sequence=fragment.sequence.upper(),
        left_overhang=fragment.overhang_5prime,
        right_overhang=fragment.overhang_3prime,
        orientation=1,
    )
    reverse = _OrientedFragment(
        index=index,
        sequence=reverse_complement(fragment.sequence.upper()),
        left_overhang=fragment.overhang_3prime,
        right_overhang=fragment.overhang_5prime,
        orientation=-1,
    )
    if reverse.sequence == forward.sequence:
        return (forward,)
    return forward, reverse


def _compatible(left: _OrientedFragment, right: _OrientedFragment) -> int:
    length = left.right_overhang
    if length <= 0 or length != right.left_overhang:
        return 0
    return length if left.right == right.left else 0


def _is_duplicate(sequence: str, assemblies: list[_Assembly]) -> bool:
    from labbench2.cloning.utils import is_rotation, reverse_complement

    reverse = reverse_complement(sequence)
    return any(
        is_rotation(existing.sequence, sequence)
        or is_rotation(existing.sequence, reverse)
        for existing in assemblies
    )


def assemble_restriction_fragments_v2(
    fragments: list[Any], *, max_candidates: int = MAX_CANDIDATES
) -> list[_Assembly]:
    """Enumerate circular products from compatible cohesive-ended fragments."""
    if not fragments:
        return []
    orientations = {
        index: _orientations(fragment, index)
        for index, fragment in enumerate(fragments)
    }
    assemblies: list[_Assembly] = []

    def collect(sequence: str, fragment_count: int) -> None:
        if not sequence or _is_duplicate(sequence, assemblies):
            return
        if len(assemblies) >= max_candidates:
            raise ValueError(
                "Golden Gate assembly exceeded the "
                f"{max_candidates}-candidate safety limit"
            )
        assemblies.append(_Assembly(sequence, fragment_count))

    def extend(
        first: _OrientedFragment,
        current: _OrientedFragment,
        used: frozenset[int],
        assembled: str,
    ) -> None:
        closure = _compatible(current, first)
        if closure:
            collect(assembled[:-closure], len(used))
        for index, choices in orientations.items():
            if index in used:
                continue
            for candidate in choices:
                overlap = _compatible(current, candidate)
                if overlap:
                    extend(
                        first,
                        candidate,
                        used | {index},
                        assembled + candidate.sequence[overlap:],
                    )

    for index, choices in orientations.items():
        for fragment in choices:
            extend(fragment, fragment, frozenset({index}), fragment.sequence)
    return assemblies


def _retained_site_count(sequence: str, enzymes: tuple[str, ...]) -> int:
    from Bio.Restriction import RestrictionBatch  # type: ignore[attr-defined]
    from Bio.Seq import Seq

    batch = RestrictionBatch(list(enzymes))
    return sum(
        len(sites) for sites in batch.search(Seq(sequence), linear=False).values()
    )


def goldengate_v2(
    sequences: list[Any],
    enzymes: str,
    min_fragment_length: int = 30,
    max_candidates: int = MAX_CANDIDATES,
) -> list[Any]:
    """Digest inputs and enumerate all plausible circular Golden Gate products.

    Empty-vector reassembly is retained as a possible product. Products without
    restored Type IIS sites and products using more fragments are ranked first,
    but callers must not assume that the first candidate is uniquely correct.
    """
    from labbench2.cloning.enzyme_cut import enzyme_cut
    from labbench2.cloning.sequence_models import BioSequence, make_pretty_id

    enzyme_names = tuple(value.strip() for value in enzymes.split(",") if value.strip())
    fragments = sequences[:]
    for enzyme in enzyme_names:
        fragments = [
            output for fragment in fragments for output in enzyme_cut(fragment, enzyme)
        ]
    fragments = [
        fragment
        for fragment in fragments
        if len(fragment.sequence) >= min_fragment_length
    ]
    if not fragments:
        return []

    assemblies = assemble_restriction_fragments_v2(
        fragments, max_candidates=max_candidates
    )
    ranked = sorted(
        assemblies,
        key=lambda assembly: (
            _retained_site_count(assembly.sequence, enzyme_names),
            -assembly.fragment_count,
            -len(assembly.sequence),
        ),
    )
    return [
        BioSequence(
            sequence=assembly.sequence,
            is_circular=True,
            name=make_pretty_id("goldengate-v2"),
            description=(
                f"Golden Gate v2 candidate assembled from {assembly.fragment_count} "
                f"digest fragments; retained Type IIS sites: "
                f"{_retained_site_count(assembly.sequence, enzyme_names)}"
            ),
        )
        for assembly in ranked
    ]
