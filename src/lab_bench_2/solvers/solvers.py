"""Solver factories for the LAB-Bench 2 evaluation.

The reference benchmark runs each model in two configurations: `bare` (no tools,
single-turn) and an agentic configuration with provider-native, server-side tools.
"""

from __future__ import annotations

from inspect_ai.solver import Solver, chain, generate, solver, use_tools
from inspect_ai.tool import Tool, code_execution, web_search


@solver
def bare() -> Solver:
    """The benchmark's "bare" configuration: a plain single-turn ``generate()``."""
    return generate()


def native_tools() -> list[Tool]:
    """Provider-native, server-side tools for the agentic configuration.

    ``web_search()`` and ``code_execution()`` run on the model provider's
    servers; Inspect auto-selects the internal provider that matches the active
    model. ``providers={"python": False}`` disables the sandboxed ``python()``
    fallback so no local sandbox is required.

    TODO Add web_fetch when Inspect adds support for it.
    The paper uses a 3rd tool WebFetch, it is omitted here due to lack of
    support in Inspect.
    """
    return [
        web_search(),
        code_execution(
            providers={"python": False}
        ),  # disable python fallback code_interpreter
    ]


@solver
def tools() -> Solver:
    """The benchmark's agentic ("tools") configuration.

    Gives the model the provider-native tools from :func:`native_tools` and runs
    Inspect's tool-use loop, which drives each provider's server-side tool
    round-trips.
    """
    return chain(
        use_tools(native_tools()),
        generate(tool_calls="loop"),
    )
