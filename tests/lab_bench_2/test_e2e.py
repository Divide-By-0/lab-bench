import pytest
from inspect_ai import eval
from inspect_ai.model import ModelOutput, get_model

from lab_bench_2.lab_bench_2 import lab_bench_2
from lab_bench_2.prompt_composer import Mode


def test_unsupported_tag_raises() -> None:
    with pytest.raises(NotImplementedError):
        lab_bench_2(tags="bogusqa")


@pytest.mark.huggingface
@pytest.mark.dataset_download
def test_litqa3_tools_e2e() -> None:
    # given the litqa3 task under the agentic (tools) solver, with a mock grader
    # when
    [log] = eval(
        tasks=lab_bench_2(tags="litqa3", solver="tools"),
        model="mockllm/model",
        model_roles={"grader": "mockllm/model"},
        limit=1,
    )
    # then the agentic configuration runs end to end
    assert log.status == "success"


@pytest.mark.huggingface
@pytest.mark.dataset_download
@pytest.mark.docker
@pytest.mark.slow
def test_litqa3_agentic_e2e() -> None:
    # given the litqa3 task under the client-side agentic solver (Docker sandbox),
    # with a model that submits immediately and a mock grader
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.for_tool_call(
                model="mockllm/model",
                tool_name="submit",
                tool_arguments={"answer": "A"},
            ),
        ],
    )
    # when
    [log] = eval(
        tasks=lab_bench_2(tags="litqa3", solver="agentic"),
        model=model,
        model_roles={"grader": "mockllm/model"},
        limit=1,
    )
    # then the agentic configuration runs end to end
    assert log.status == "success"


@pytest.mark.huggingface
@pytest.mark.dataset_download
def test_litqa3_bare_e2e() -> None:
    # given the litqa3 task under the default (bare) solver, with a mock grader
    # when
    [log] = eval(
        tasks=lab_bench_2(tags="litqa3"),
        model="mockllm/model",
        model_roles={"grader": "mockllm/model"},
        limit=1,
    )
    # then
    assert log.status == "success"


@pytest.mark.huggingface
@pytest.mark.dataset_download
@pytest.mark.parametrize(
    "tag,mode",
    [
        ("patentqa", "inject"),
        ("trialqa", "inject"),
        ("protocolqa2", "file"),
        ("sourcequality", "file"),
    ],
)
def test_supported_tag_loads_one_sample_e2e(tag: str, mode: Mode) -> None:
    # given a newly enabled tag in its primary mode, with a mock grader
    # when
    [log] = eval(
        tasks=lab_bench_2(tags=tag, mode=mode),
        model="mockllm/model",
        model_roles={"grader": "mockllm/model"},
        limit=1,
    )
    # then
    assert log.status == "success"
