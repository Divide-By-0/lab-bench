import pytest
from inspect_ai import eval

from lab_bench_2.lab_bench_2 import lab_bench_2
from lab_bench_2.prompt_composer import Mode
from lab_bench_2.solvers import tools


def test_unsupported_tag_raises() -> None:
    with pytest.raises(NotImplementedError):
        lab_bench_2(tag="bogusqa")


@pytest.mark.huggingface
@pytest.mark.dataset_download
def test_litqa3_tools_e2e() -> None:
    # given the litqa3 task with the agentic (tools) solver overriding the
    # default via Inspect's solver override, and a mock grader
    # when
    [log] = eval(
        tasks=lab_bench_2(tag="litqa3"),
        solver=tools(),
        model="mockllm/model",
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
        tasks=lab_bench_2(tag="litqa3"),
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
        tasks=lab_bench_2(tag=tag, mode=mode),
        model="mockllm/model",
        model_roles={"grader": "mockllm/model"},
        limit=1,
    )
    # then
    assert log.status == "success"
