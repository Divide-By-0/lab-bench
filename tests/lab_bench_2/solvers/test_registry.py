from typing import cast

import pytest
from inspect_ai.solver import Solver

from lab_bench_2.solvers.registry import (
    SOLVERS_BY_TYPE,
    SolverType,
    sandbox_for_solver,
    solver_for_type,
)


class TestSolverForType:
    def test_registered_solver_types(self) -> None:
        # given / when / then the supported types are bare, tools, and agentic
        assert set(SOLVERS_BY_TYPE) == {"bare", "tools", "agentic"}

    def test_returns_a_solver_for_each_registered_type(self) -> None:
        # given each registered solver type
        # when / then a Solver instance is produced
        for solver_type in SOLVERS_BY_TYPE:
            assert isinstance(solver_for_type(cast(SolverType, solver_type)), Solver)

    def test_raises_for_unimplemented_type(self) -> None:
        # given a solver type that is not registered
        # when / then a NotImplementedError is raised
        with pytest.raises(NotImplementedError):
            solver_for_type(cast(SolverType, "nonexistent"))


class TestSandboxForSolver:
    def test_agentic_requires_a_docker_sandbox(self) -> None:
        # given the client-side agentic solver
        # when
        spec = sandbox_for_solver("agentic")
        # then a docker sandbox built from the package compose file is returned
        assert isinstance(spec, tuple)
        sandbox_type, compose = spec
        assert sandbox_type == "docker"
        assert compose.endswith("compose.yaml")

    def test_server_side_solvers_need_no_sandbox(self) -> None:
        # given the server-side solvers
        # when / then no sandbox is attached
        assert sandbox_for_solver("bare") is None
        assert sandbox_for_solver("tools") is None
