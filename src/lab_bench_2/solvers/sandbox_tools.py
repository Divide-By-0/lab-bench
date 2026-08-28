"""Tool helpers for LabBench2 agentic evaluations."""

from __future__ import annotations

import logging
import os
from typing import Literal

from inspect_ai.tool import Tool, bash, web_search

from lab_bench_2.solvers.stateful_python import python_session

# External web-search providers used by the standard agentic solver, in priority
# order. The open-source-discovery solver opts into OpenAI's native provider
# explicitly; keeping that choice out of the default path prevents accidental
# web access during ordinary benchmark runs.
_WEB_SEARCH_PROVIDERS_BY_KEY: dict[str, Literal["tavily", "exa", "google"]] = {
    "TAVILY_API_KEY": "tavily",
    "EXA_API_KEY": "exa",
    "GOOGLE_CSE_API_KEY": "google",
}

logger = logging.getLogger(__name__)


def web_search_available() -> bool:
    """True when an external web-search provider key is configured."""
    return any(os.environ.get(key) for key in _WEB_SEARCH_PROVIDERS_BY_KEY)


def _build_web_search() -> Tool | None:
    """Build web_search with the first configured external provider, if any."""
    for key, provider in _WEB_SEARCH_PROVIDERS_BY_KEY.items():
        if os.environ.get(key):
            return web_search(provider)
    return None


def sandbox_tools(
    timeout: int = 180,
    *,
    openai_web_search: bool = False,
) -> list[Tool]:
    """Return the sandboxed client-side tool set (python, bash, optionally web_search).

    web_search is included when an external provider key is configured
    (TAVILY_API_KEY, EXA_API_KEY, or GOOGLE_CSE_API_KEY). For an explicitly
    OpenAI-only exploratory run, ``openai_web_search=True`` instead registers
    OpenAI's server-side search tool. Container network policy is controlled
    separately by the Compose file selected for the solver.
    """
    # REASON: python_session, not the stock python(), because the stock tool loses all
    # state between calls -- 94 of 125 observed tool errors were NameError from exactly
    # that. See stateful_python.py.
    tools: list[Tool] = [python_session(timeout=timeout), bash(timeout=timeout)]
    ws = web_search("openai") if openai_web_search else _build_web_search()
    if ws is not None:
        tools.append(ws)
    else:
        logger.warning(
            "No search provider api key found, so no web search tool is given to the agent"
        )
    return tools
