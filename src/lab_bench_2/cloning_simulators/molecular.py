"""Adapters between LAB-Bench cloning values and pydna molecules.

The protocol DSL exposes a deliberately small ``BioSequence`` model.  That
model cannot encode which strand forms a sticky end, so v2 keeps a private
``Dseqrecord`` alongside each intermediate.  Public results remain ordinary
``BioSequence`` objects while nested operations retain the double-stranded
molecular state needed by pydna.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Callable, Iterable, Iterator

MAX_CANDIDATES = 256
MAX_REACTION_SUBSETS = 1024


@dataclass(frozen=True)
class AssemblyPart:
    """Coordinates contributed by one direct assembly input."""

    source_index: int
    orientation: int
    start: int
    end: int


@dataclass(frozen=True)
class MolecularCandidate:
    """One library product and the top-level inputs used to make it."""

    record: Any
    source_indices: tuple[int, ...]


def to_pydna(value: Any) -> Any:
    """Return an independent pydna record for a sequence-like value."""
    from pydna.dseqrecord import Dseqrecord  # type: ignore[import-untyped]

    existing = getattr(value, "_pydna_record", None)
    if existing is not None:
        return copy.deepcopy(existing)

    sequence = str(value.sequence if hasattr(value, "sequence") else value).upper()
    record = Dseqrecord(sequence, circular=bool(getattr(value, "is_circular", False)))
    name = str(getattr(value, "name", "") or record.name)
    record.id = name
    record.name = name
    description = getattr(value, "description", None)
    if description:
        record.description = str(description)
    return record


def label_inputs(values: Iterable[Any]) -> list[Any]:
    """Convert inputs and give each one a stable positional library id."""
    records = [to_pydna(value) for value in values]
    for index, record in enumerate(records):
        label = f"labbench-source-{index}"
        record.id = label
        record.name = label
    return records


def from_pydna(
    record: Any,
    *,
    prefix: str,
    description: str,
    assembly_parts: tuple[AssemblyPart, ...] = (),
) -> Any:
    """Convert a pydna product without discarding its molecular state."""
    from labbench2.cloning.sequence_models import BioSequence, make_pretty_id

    circular = bool(record.circular)
    left_overhang = 0 if circular else abs(int(record.seq.left_ovhg or 0))
    right_overhang = 0 if circular else abs(int(record.seq.right_ovhg or 0))
    result = BioSequence(
        sequence=str(record.seq).upper(),
        is_circular=circular,
        name=make_pretty_id(prefix),
        description=description,
        overhang_5prime=left_overhang,
        overhang_3prime=right_overhang,
    )
    object.__setattr__(result, "_pydna_record", copy.deepcopy(record))
    if assembly_parts:
        object.__setattr__(result, "_assembly_parts", assembly_parts)
    return result


def resolve_enzymes(names: Iterable[str]) -> tuple[Any, ...]:
    """Resolve restriction-enzyme names through Biopython's curated registry."""
    from Bio.Restriction import RestrictionBatch  # type: ignore[attr-defined]

    normalized = tuple(name.strip() for name in names if name.strip())
    if not normalized:
        raise ValueError("At least one restriction enzyme is required")
    batch = RestrictionBatch(list(normalized))
    return tuple(batch.get(name) for name in normalized)


def digest_records(value: Any, enzyme_names: Iterable[str]) -> list[Any]:
    """Digest a molecule with all enzymes while retaining true sticky ends."""
    record = to_pydna(value)
    fragments = list(record.cut(*resolve_enzymes(enzyme_names)))
    return fragments or [record]


def cut_sequence_v2(value: Any, enzyme_name: str) -> list[Any]:
    """Public restriction digest used by nested ``enzyme_cut`` operations."""
    record = to_pydna(value)
    fragments = list(record.cut(*resolve_enzymes((enzyme_name,))))
    descriptions: tuple[str, ...]
    if not fragments:
        fragments = [record]
        descriptions = (f"Uncut ({enzyme_name} - no site found)",)
    else:
        descriptions = tuple(
            f"Fragment {index} ({enzyme_name} digest)"
            for index in range(len(fragments))
        )
    return [
        from_pydna(
            fragment,
            prefix="digest-v2",
            description=description,
        )
        for fragment, description in zip(fragments, descriptions, strict=True)
    ]


def input_subsets(
    records: list[Any], *, max_subsets: int = MAX_REACTION_SUBSETS
) -> Iterator[tuple[tuple[int, ...], list[Any]]]:
    """Yield non-empty input subsets under an explicit combinatorial bound."""
    subset_count = (1 << len(records)) - 1
    if subset_count > max_subsets:
        raise ValueError(
            f"Assembly requires {subset_count} input subsets, exceeding the "
            f"{max_subsets}-reaction safety limit"
        )
    for size in range(1, len(records) + 1):
        for indices in combinations(range(len(records)), size):
            yield indices, [copy.deepcopy(records[index]) for index in indices]


def collect_library_products(
    records: list[Any],
    reaction: Callable[[list[Any]], list[Any]],
    *,
    max_candidates: int = MAX_CANDIDATES,
) -> list[MolecularCandidate]:
    """Run a pydna reaction for every input subset and deduplicate its products."""
    candidates: dict[str, MolecularCandidate] = {}
    for indices, subset in input_subsets(records):
        try:
            products = reaction(subset)
        except ValueError as exc:
            if "maximum number of assemblies" in str(exc).lower():
                raise ValueError(f"Assembly search stopped safely: {exc}") from exc
            raise
        for product in products:
            key = str(product.seguid())
            current = candidates.get(key)
            candidate = MolecularCandidate(product, indices)
            if current is None or len(indices) > len(current.source_indices):
                candidates[key] = candidate
            if len(candidates) > max_candidates:
                raise ValueError(
                    f"Assembly exceeded the {max_candidates}-candidate safety limit"
                )
    return list(candidates.values())


def assembly_parts(
    product: Any, source_indices: tuple[int, ...]
) -> tuple[AssemblyPart, ...]:
    """Recover approximate input spans from pydna's assembly provenance."""
    source = getattr(product, "source", None)
    inputs = list(getattr(source, "input", ()) or ())
    if not inputs:
        return ()

    assembled = str(product.seq).upper()
    search_space = assembled + assembled if product.circular else assembled
    parts: list[AssemblyPart] = []
    for position, entry in enumerate(inputs):
        source_record = entry.sequence
        source_id = str(getattr(source_record, "id", ""))
        try:
            local_index = int(source_id.removeprefix("labbench-source-"))
        except ValueError:
            if position >= len(source_indices):
                continue
            local_index = source_indices[position]

        reverse_complemented = bool(entry.reverse_complemented)
        oriented_record = (
            source_record.reverse_complement()
            if reverse_complemented
            else source_record
        )
        oriented = str(oriented_record.seq).upper()
        left = entry.left_location
        right = entry.right_location
        core_start = int(left.end) if left is not None else 0
        core_end = int(right.start) if right is not None else len(oriented)
        if core_end <= core_start:
            core_start, core_end = 0, len(oriented)
        core = oriented[core_start:core_end]
        hit = search_space.find(core) if core else -1
        if not 0 <= hit < len(assembled):
            hit = search_space.find(oriented)
            core_start = 0
        if not 0 <= hit < len(assembled):
            continue
        start = hit - core_start
        parts.append(
            AssemblyPart(
                source_index=local_index,
                orientation=-1 if reverse_complemented else 1,
                start=start,
                end=start + len(oriented),
            )
        )
    return tuple(parts)
