"""Shared agentic solver with final-warning mechanism for LabBench2 tasks.

Wraps basic_agent with a message-limit-aware final-warning prompt that
forces the agent to submit before running out of time.
"""

import logging
from pathlib import Path
from textwrap import dedent
from typing import Any

from inspect_ai.model import ChatMessageTool, ChatMessageUser, execute_tools, get_model
from inspect_ai.solver import (
    Generate,
    Solver,
    TaskState,
    basic_agent,
    chain,
    solver,
    system_message,
)
from inspect_ai.util import LimitExceededError, sandbox

from lab_bench_2.file_downloader import list_files
from lab_bench_2.solvers.sandbox_tools import sandbox_tools, web_search_available

# Each agent turn is roughly one model generation plus one tool execution
# (~2 messages); the +2 covers the system and initial user messages.
DEFAULT_AGENTIC_MAX_TURNS = 80


def build_sandbox_prompt(web_search: bool, *, open_web_research: bool = False) -> str:
    """System prompt for the agentic sandbox.

    The available-tools sentence reflects whether a ``web_search`` tool is
    actually present (it is only added when an external provider key is set), so
    the model is never told about a tool it does not have.
    """
    tools_clause = (
        "Python, Bash, and Web Search tools" if web_search else "Python and Bash tools"
    )
    # REASON: an agent that starts open-ended web searching does not come back. One
    # observed run spent 18 of its last 22 tool calls on DuckDuckGo queries that
    # returned nothing, and hit the token limit without answering -- while the same
    # task succeeded in 31 calls when it just computed. Scope the tool to single
    # factual lookups so it cannot become a research strategy.
    if open_web_research:
        search_clause = (
            "\n\n    This is an open-source-discovery task. Use Web Search to locate "
            "public sequence records, quantitative component data, and primary or "
            "repository sources needed for the design. Record stable accessions or "
            "URLs and distinguish directly supported facts from assumptions. The "
            "sandbox has outbound access in this mode, so use Bash or Python to "
            "download and inspect exact public sequence files after finding them. "
            "Do not search for a worked answer to this benchmark question."
        )
    elif web_search:
        search_clause = (
            "\n\n    Use Web Search only to answer a single specific factual question "
            "(for example, the catalogue sequence of a named plasmid). Do not use it to "
            "research the task, look for worked solutions, or browse. Everything you need "
            "to compute the answer is in your working directory and /opt/docs."
        )
    else:
        search_clause = ""
    return dedent(f"""\
    You are a helpful assistant completing a scientific research task. You have \
access to {tools_clause} in a sandboxed environment. The \
following Python libraries are pre-installed: biopython, pydna, primer3-py, \
pandas, numpy, scipy, pymupdf (fitz), pdfplumber. Use pymupdf or pdfplumber to \
read any PDF files.

    Any files related to the question are in your working directory. Start by \
running `ls` to see what is available, then use Python or Bash to read and \
analyze them. Use Python when computational analysis would help answer the \
question. Before taking an action, briefly describe your reasoning.

    Your Python session is persistent: variables, imports and functions defined \
in one call are still available in later calls. Do not re-import modules or \
re-parse a file you have already read — just reuse the variable.

    API reference for the installed libraries is on disk at /opt/docs (one .txt \
per module, e.g. /opt/docs/pydna.design.txt, /opt/docs/pydna.assembly2.txt, \
/opt/docs/Bio.Restriction.txt). Read those instead of guessing at an API or \
searching for documentation.

{search_clause}

    When you have your final answer, call the submit() tool. Be specific and \
precise — provide exact numerical values, sequences, or lists as requested. For \
numeric answers, provide the number without units unless specifically asked.

    PLEASE BE CONCISE WITH YOUR OUTPUT AND CODE.""")


CONTINUE_MESSAGE = dedent("""\
    You did not call a tool. Think step-by-step (<=2 lines), then either call a \
tool to make progress on the question, or call submit() with your final answer.""")

FINAL_WARNING_MESSAGE = dedent("""\
    You are running out of time and MUST submit your answer NOW.
    Based on everything you have learned so far, use the submit()
    tool to submit your single best answer. Do NOT run any more
    code — just submit your best guess immediately.""")

logger = logging.getLogger(__name__)


@solver
def copy_files_to_sandbox() -> Solver:
    """Copy a question's downloaded files into the sandbox working directory.

    Reads the files cached at ``metadata["files_path"]`` (set by the dataset
    loader for file-bearing tags) and writes each into the sandbox cwd so the
    agent can inspect them with ``python``/``bash``. A no-op for file-less tags
    (e.g. litqa3), where no ``files_path`` is set.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        files_path = state.metadata.get("files_path")
        if not files_path:
            return state
        env = sandbox()
        for file in list_files(Path(files_path)):
            logger.debug(f"Copying file into the sandbox: {file.name}")
            await env.write_file(file.name, file.read_bytes())
        return state

    return solve


@solver
def agentic() -> Solver:
    """The benchmark's client-side agentic configuration.

    Copies any question files into the sandbox, then runs an agent with
    sandboxed ``python``/``bash`` (and, when an external provider key is set,
    ``web_search``) tools, wrapped in the final-warning mechanism that forces a
    ``submit`` before the turn budget is exhausted. Requires a Docker sandbox,
    which the task attaches for ``solver="agentic"``.
    """
    # Each agent turn produces ~2 messages (assistant + tool result), plus
    # system and initial user message. Translate turns to message count.
    message_limit = DEFAULT_AGENTIC_MAX_TURNS * 2 + 2

    return chain(
        copy_files_to_sandbox(),
        agent_with_final_warning(
            warning_limit=message_limit,
            init=system_message(
                build_sandbox_prompt(web_search=web_search_available())
            ),
            tools=sandbox_tools(),
            continue_message=CONTINUE_MESSAGE,
        ),
    )


@solver
def agentic_web(final_warning_cost_limit: float | None = None) -> Solver:
    """OrbStack agent with Python/Bash plus OpenAI's server-side web search.

    This solver uses a separate network-enabled compose file so the model can
    download exact sequence records after discovering them with the explicitly
    registered OpenAI search tool. It is for open-source-discovery pilots and
    must not be used on public-answer-key tasks.
    """
    message_limit = DEFAULT_AGENTIC_MAX_TURNS * 2 + 2
    return chain(
        copy_files_to_sandbox(),
        agent_with_final_warning(
            warning_limit=message_limit,
            final_warning_cost_limit=final_warning_cost_limit,
            init=system_message(
                build_sandbox_prompt(web_search=True, open_web_research=True)
            ),
            tools=sandbox_tools(openai_web_search=True),
            continue_message=CONTINUE_MESSAGE,
        ),
    )


@solver
def agent_with_final_warning(
    warning_limit: int = 45,
    final_warning_cost_limit: float | None = None,
    **agent_kwargs: Any,
) -> Solver:
    """Wrap basic_agent with a final-warning mechanism.

    Runs basic_agent with a message_limit of `warning_limit`. If the agent
    hits that limit without submitting, injects a "submit NOW" prompt and
    gives the model one more generation with tools to submit its best guess.
    """
    agent_solver = basic_agent(message_limit=warning_limit, **agent_kwargs)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        try:
            state = await agent_solver(state, generate)
        except LimitExceededError:
            pass  # Agent hit message limit without submitting — expected

        # basic_agent set the sample message_limit to warning_limit, and the
        # agent just ran up against it — so the limit must be raised here or the
        # final-warning generate below would immediately re-trip it. Allow room
        # for dangling-tool resolution (2), the final-warning user message (1),
        # the model response (1), and its tool execution results (2).
        state.message_limit = len(state.messages) + 6
        # A caller can reserve part of its total cost budget for the final
        # answer by running the research loop with a lower CLI cost limit and
        # relaxing it here. Without this, Inspect records the final model event
        # but raises the already-active limit before returning ModelOutput, so
        # the submit answer cannot become the sample completion.
        if state.cost_limit is not None and final_warning_cost_limit is not None:
            state.cost_limit = max(state.cost_limit, final_warning_cost_limit)

        # Resolve any dangling tool calls from the interrupted agent.
        if state.output and state.output.message.tool_calls:
            resolved_ids = {
                msg.tool_call_id
                for msg in state.messages
                if isinstance(msg, ChatMessageTool) and msg.tool_call_id
            }
            has_pending = any(
                tc.id not in resolved_ids for tc in state.output.message.tool_calls
            )
            if has_pending:
                tool_results, _ = await execute_tools(
                    [state.output.message], state.tools
                )
                state.messages.extend(tool_results)

        # Check if submit was already called (either normally or via dangling resolution)
        submitted = any(
            isinstance(msg, ChatMessageTool) and msg.function == "submit"
            for msg in state.messages
        )
        if submitted:
            for msg in reversed(state.messages):
                if isinstance(msg, ChatMessageTool) and msg.function == "submit":
                    state.output.completion = msg.text
                    break
            return state

        # Inject warning, one final generate
        state.messages.append(ChatMessageUser(content=FINAL_WARNING_MESSAGE))

        output = await get_model().generate(input=state.messages, tools=state.tools)
        state.messages.append(output.message)
        state.output = output

        if output.message.tool_calls:
            # Extract submit answer directly from tool call arguments so
            # the completion is captured even when this warning was triggered
            # by a sample cost/token limit. Do not execute a recovered submit:
            # Inspect can re-raise the active sample limit during tool
            # execution and discard the state mutation we just recovered.
            for tc in output.message.tool_calls:
                if tc.function == "submit":
                    answer = (
                        tc.arguments.get("answer", "")
                        if isinstance(tc.arguments, dict)
                        else ""
                    )
                    state.output.completion = answer
                    return state

            # A warning response that ignored the instruction and called a
            # non-submit tool is still executed for proper bookkeeping.
            tool_results, _ = await execute_tools([output.message], state.tools)
            state.messages.extend(tool_results)

        return state

    return solve
