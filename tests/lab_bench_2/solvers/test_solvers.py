from inspect_ai.solver import Solver
from inspect_ai.tool import Tool, ToolDef

from lab_bench_2.solvers.solvers import bare, native_tools, tools


def test_bare_returns_solver() -> None:
    assert isinstance(bare(), Solver)


def test_tools_returns_solver() -> None:
    assert isinstance(tools(), Solver)


class TestNativeTools:
    def test_returns_provider_native_search_and_code_execution(self) -> None:
        # given / when
        result = native_tools()
        # then the two provider-native, server-side tools are present
        names = {ToolDef(t).name for t in result}
        assert all(isinstance(t, Tool) for t in result)
        assert names == {"web_search", "code_execution"}

    def test_omits_web_fetch(self) -> None:
        # given Inspect has no native web_fetch wrapper (documented omission)
        # when / then no fetch tool leaks into the agentic tool set
        names = {ToolDef(t).name for t in native_tools()}
        assert not any("fetch" in name for name in names)
