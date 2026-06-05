"""Registry mapping a ``SolverType`` to its solver factory."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from inspect_ai.solver import Solver
from inspect_ai.util import SandboxEnvironmentType

from lab_bench_2.solvers.agent import agentic
from lab_bench_2.solvers.solvers import bare, tools

SolverType = Literal["bare", "tools", "agentic"]

SOLVERS_BY_TYPE = {
    "bare": bare,
    "tools": tools,
    "agentic": agentic,
}

# Docker sandbox shared by the client-side `agentic` solver.
COMPOSE = str(Path(__file__).parent / "compose.yaml")


def solver_for_type(solver_type: SolverType) -> Solver:
    """Return the solver for a type, or raise if the type is not yet implemented."""
    factory = SOLVERS_BY_TYPE.get(solver_type)
    if factory is None:
        raise NotImplementedError(
            f"No solver implemented for type={solver_type!r}; "
            f"supported types: {sorted(SOLVERS_BY_TYPE)}."
        )
    return factory()


def sandbox_for_solver(solver_type: SolverType) -> SandboxEnvironmentType | None:
    """Return the sandbox a solver needs, or ``None`` if it runs without one.

    Only the client-side ``agentic`` solver executes tools in a sandbox; ``bare``
    and ``tools`` run server-side and must not spin up a container.
    """
    if solver_type == "agentic":
        return ("docker", COMPOSE)
    return None
