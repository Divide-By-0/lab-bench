from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from inspect_ai import Task, eval
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessage, ModelName, ModelOutput, get_model
from inspect_ai.solver import Generate, Solver, TaskState

import lab_bench_2.solvers.agent as agent_module
from lab_bench_2.solvers.agent import (
    FINAL_WARNING_MESSAGE,
    agent_with_final_warning,
    agentic,
    build_sandbox_prompt,
    copy_files_to_sandbox,
)


def test_agentic_returns_solver() -> None:
    assert isinstance(agentic(), Solver)


@pytest.mark.parametrize("web_search", [True, False])
def test_sandbox_prompt_advertises_pdf_libraries(web_search: bool) -> None:
    # given/when the sandbox system prompt
    prompt = build_sandbox_prompt(web_search=web_search)
    # then it tells the agent the PDF readers are available, so it does not have
    # to guess (and stays in sync with the libraries installed in the Dockerfile)
    assert "pymupdf" in prompt
    assert "fitz" in prompt
    assert "pdfplumber" in prompt


def _never_submit_until_warned(
    messages: list[ChatMessage],
    tools: Any,
    tool_choice: Any,
    config: Any,
) -> ModelOutput:
    """Submit only once the final-warning prompt has been injected.

    Before the warning, the model returns plain content (no tool call), so the
    agent loops until it exhausts its message budget without submitting.
    """
    last_text = messages[-1].text if messages else ""
    if "MUST submit your answer NOW" in last_text:
        return ModelOutput.for_tool_call(
            model="mockllm/model",
            tool_name="submit",
            tool_arguments={"answer": "RECOVERED"},
        )
    return ModelOutput.from_content(
        model="mockllm/model", content="still working, no final answer yet"
    )


def test_final_warning_recovers_answer_when_model_never_submits() -> None:
    # given a model that only submits once the final-warning prompt is injected
    model = get_model("mockllm/model", custom_outputs=_never_submit_until_warned)
    task = Task(
        dataset=[Sample(input="What is the answer?", target="RECOVERED")],
        solver=agent_with_final_warning(warning_limit=4),
    )
    # when the agent runs out of turns without submitting
    log = eval(task, model=model)[0]
    # then the final-warning path recovers the submitted answer
    assert log.status == "success"
    assert log.samples is not None
    assert log.samples[0].output.completion == "RECOVERED"
    # and the warning was actually injected into the conversation
    assert any(FINAL_WARNING_MESSAGE in m.text for m in log.samples[0].messages)


def _dangling_submit(
    messages: list[ChatMessage],
    tools: Any,
    tool_choice: Any,
    config: Any,
) -> ModelOutput:
    """Emit a submit call that is cut off by the context window.

    With ``stop_reason="model_length"``, basic_agent breaks its loop without
    executing the tool, so the submit call is left dangling for the wrapper to
    resolve.
    """
    output = ModelOutput.for_tool_call(
        model="mockllm/model",
        tool_name="submit",
        tool_arguments={"answer": "DANGLED"},
    )
    output.choices[0].stop_reason = "model_length"
    return output


def test_recovers_dangling_submit_when_interrupted_mid_tool_call() -> None:
    # given a model whose submit call is cut off by the context window, so
    # basic_agent exits with the submit tool call still unresolved
    model = get_model("mockllm/model", custom_outputs=_dangling_submit)
    task = Task(
        dataset=[Sample(input="What is the answer?", target="DANGLED")],
        solver=agent_with_final_warning(warning_limit=50),
    )
    # when the wrapper resolves the dangling call
    log = eval(task, model=model)[0]
    # then the submit tool runs and its answer is recovered
    assert log.status == "success"
    assert log.samples is not None
    sample = log.samples[0]
    assert sample.output.completion == "DANGLED"
    # and recovery came from resolving the dangling call, not from the
    # final-warning fallback (which is never injected in this path)
    assert all(FINAL_WARNING_MESSAGE not in m.text for m in sample.messages)


class TestCopyFilesToSandbox:
    async def test_writes_each_question_file_into_the_sandbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a question whose files are cached locally (incl. a binary PDF —
        # the file type that drove the sandbox PDF-tooling fix)
        (tmp_path / "seq.fasta").write_text(">a\nACGT\n")
        (tmp_path / "data.csv").write_text("x,y\n1,2\n")
        (tmp_path / "protocol.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        fake_env = MagicMock()
        fake_env.write_file = AsyncMock()
        monkeypatch.setattr(agent_module, "sandbox", lambda *a, **k: fake_env)
        state = TaskState(
            model=ModelName("mockllm/model"),
            sample_id="files",
            epoch=0,
            input="q",
            messages=[],
            metadata={"files_path": str(tmp_path)},
        )
        # when
        await copy_files_to_sandbox()(state, cast(Generate, AsyncMock()))
        # then each file is written into the sandbox cwd by basename
        written = {call.args[0] for call in fake_env.write_file.await_args_list}
        assert written == {"seq.fasta", "data.csv", "protocol.pdf"}

    async def test_is_noop_without_files_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a question with no files (no files_path in metadata)
        fake_env = MagicMock()
        fake_env.write_file = AsyncMock()
        monkeypatch.setattr(agent_module, "sandbox", lambda *a, **k: fake_env)
        state = TaskState(
            model=ModelName("mockllm/model"),
            sample_id="no-files",
            epoch=0,
            input="q",
            messages=[],
            metadata={},
        )
        # when
        await copy_files_to_sandbox()(state, cast(Generate, AsyncMock()))
        # then nothing is written to the sandbox
        fake_env.write_file.assert_not_awaited()
