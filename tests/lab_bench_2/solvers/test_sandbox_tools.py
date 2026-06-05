import pytest
from inspect_ai.tool import Tool, ToolDef

from lab_bench_2.solvers.sandbox_tools import sandbox_tools

_WEB_SEARCH_KEYS = ("TAVILY_API_KEY", "EXA_API_KEY", "GOOGLE_CSE_API_KEY")


class TestSandboxTools:
    def test_code_tools_only_without_web_search_keys(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given no external web-search provider keys
        for key in _WEB_SEARCH_KEYS:
            monkeypatch.delenv(key, raising=False)
        # when
        result = sandbox_tools()
        # then only the sandboxed code-execution tools are present
        names = {ToolDef(t).name for t in result}
        assert all(isinstance(t, Tool) for t in result)
        assert names == {"python", "bash"}

    def test_adds_web_search_when_external_key_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a single external web-search provider key
        for key in _WEB_SEARCH_KEYS:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        # when
        names = {ToolDef(t).name for t in sandbox_tools()}
        # then web_search joins the code-execution tools
        assert names == {"python", "bash", "web_search"}
