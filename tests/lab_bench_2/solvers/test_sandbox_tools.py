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
        # python_session, not python: the stock tool loses state between calls
        assert names == {"python_session", "bash"}

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
        assert names == {"python_session", "bash", "web_search"}

    def test_adds_openai_web_search_without_an_external_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for key in _WEB_SEARCH_KEYS:
            monkeypatch.delenv(key, raising=False)

        tools = sandbox_tools(openai_web_search=True)
        names = {ToolDef(tool).name for tool in tools}
        search = next(tool for tool in tools if ToolDef(tool).name == "web_search")

        assert names == {"python_session", "bash", "web_search"}
        assert "openai" in (ToolDef(search).options or {})
        assert not {"tavily", "google", "exa"} & set(ToolDef(search).options or {})
