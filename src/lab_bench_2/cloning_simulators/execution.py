"""Version-aware execution for the cloning protocol DSL."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from lab_bench_2.cloning_simulators.gibson_v2 import gibson_v2
from lab_bench_2.cloning_simulators.golden_gate_v2 import goldengate_v2
from lab_bench_2.cloning_simulators.pcr_v2 import simulate_pcr_v2
from lab_bench_2.cloning_simulators.restriction_v2 import restriction_assemble_v2


def _one(results: list[Any], operation: str) -> Any:
    if not results:
        raise ValueError(f"{operation} produced no sequence")
    if len(results) != 1:
        raise ValueError(
            f"Ambiguous intermediate: {operation} produced {len(results)} candidate "
            "sequences. The protocol DSL has no product-selection operation."
        )
    return results[0]


async def execute_operation_v2(operation: Any, base_dir: Path) -> list[Any]:
    """Execute one parsed DSL operation using v2 PCR and Golden Gate semantics."""
    name = type(operation).__name__
    if name == "PCROperation":
        template = _one(
            await execute_operation_v2(operation.sequence, base_dir), "PCR template"
        )
        forward = _one(
            await execute_operation_v2(operation.forward_primer, base_dir),
            "forward primer",
        )
        reverse = _one(
            await execute_operation_v2(operation.reverse_primer, base_dir),
            "reverse primer",
        )
        return [await simulate_pcr_v2(template, forward, reverse)]
    if name == "GoldenGateOperation":
        inputs = [
            _one(await execute_operation_v2(node, base_dir), "Golden Gate input")
            for node in operation.sequences
        ]
        return goldengate_v2(inputs, operation.enzymes)
    if name == "GibsonOperation":
        inputs = [
            _one(await execute_operation_v2(node, base_dir), "Gibson input")
            for node in operation.sequences
        ]
        return gibson_v2(inputs)
    if name == "RestrictionAssembleOperation":
        first = _one(
            await execute_operation_v2(operation.fragment1, base_dir),
            "restriction-assembly input",
        )
        second = _one(
            await execute_operation_v2(operation.fragment2, base_dir),
            "restriction-assembly input",
        )
        return restriction_assemble_v2(first, second)
    if name == "EnzymeCutOperation":
        from labbench2.cloning.enzyme_cut import enzyme_cut

        sequence = _one(
            await execute_operation_v2(operation.sequence, base_dir),
            "restriction digest input",
        )
        fragments = enzyme_cut(sequence, operation.enzyme)
        return [max(fragments, key=lambda value: len(value.sequence))]
    return cast(list[Any], await operation.execute(base_dir))


async def execute_cloning_protocol_v2(expression: str, base_dir: Path) -> list[Any]:
    """Parse and execute a cloning DSL expression with v2 simulators."""
    from labbench2.cloning.cloning_protocol import CloningProtocol

    protocol = CloningProtocol(expression)
    return await execute_operation_v2(protocol.operation, base_dir)
