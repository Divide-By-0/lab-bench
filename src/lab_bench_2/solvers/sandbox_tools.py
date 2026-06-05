"""Tool helpers for LabBench2 agentic evaluations."""

from __future__ import annotations

import logging
import os
from typing import Literal

from inspect_ai.tool import Tool, bash, python, web_search

# External web-search providers, in priority order. Internal providers (openai,
# anthropic, gemini) use the model's built-in search but cannot coexist with
# other tools like python() and bash() (Gemini raises "does not yet support
# native web search concurrently with other tools"), so we use external-only
# providers, which work alongside code execution for every model.
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


def sandbox_tools(timeout: int = 180) -> list[Tool]:
    """Return the sandboxed client-side tool set (python, bash, optionally web_search).

    web_search is included when an external provider key is configured
    (TAVILY_API_KEY, EXA_API_KEY, or GOOGLE_CSE_API_KEY).
    """
    tools: list[Tool] = [python(timeout=timeout), bash(timeout=timeout)]
    ws = _build_web_search()
    if ws is not None:
        tools.append(ws)
    else:
        logger.warn(
            "No search provider api key found, so no web search tool is given to the agent"
        )
    return tools
