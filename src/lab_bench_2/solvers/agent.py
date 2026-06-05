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


def build_sandbox_prompt(web_search: bool) -> str:
    """System prompt for the agentic sandbox.

    The available-tools sentence reflects whether a ``web_search`` tool is
    actually present (it is only added when an external provider key is set), so
    the model is never told about a tool it does not have.
    """
    tools_clause = (
        "Python, Bash, and Web Search tools" if web_search else "Python and Bash tools"
    )
    return dedent(f"""\
    You are a helpful assistant completing a scientific research task. You have \
access to {tools_clause} in a sandboxed environment. The \
following Python libraries are pre-installed: biopython, pydna, primer3-py, \
pandas, numpy, scipy.

    Any files related to the question are in your working directory. Start by \
running `ls` to see what is available, then use Python or Bash to read and \
analyze them. Use Python when computational analysis would help answer the \
question. Before taking an action, briefly describe your reasoning.

    The environment is non-interactive — imports and variables do not persist \
between calls. Each code execution is independent. If you need to work with long \
sequences, save them to a file and load from that file in subsequent calls.

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
def agent_with_final_warning(
    warning_limit: int = 45,
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
            # the completion is captured even if execute_tools is blocked
            # by the message limit.
            for tc in output.message.tool_calls:
                if tc.function == "submit":
                    answer = (
                        tc.arguments.get("answer", "")
                        if isinstance(tc.arguments, dict)
                        else ""
                    )
                    state.output.completion = answer
                    break

            # Still execute the tools for proper message-state bookkeeping
            tool_results, _ = await execute_tools([output.message], state.tools)
            state.messages.extend(tool_results)

        return state

    return solve
