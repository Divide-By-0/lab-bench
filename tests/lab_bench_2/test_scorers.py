from pathlib import Path
from typing import Any

import pytest
from inspect_ai.model import ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target
from inspect_ai.solver import TaskState

from lab_bench_2 import SUPPORTED_TAGS, parse_judge_verdict
from lab_bench_2.scorers import (
    SCORERS_BY_TAG,
    cloning_scorer,
    exact_match_judge_scorer,
    recall_judge_scorer,
    scorer_for_tag,
    semantic_judge_scorer,
)


def _task_state(completion: str, metadata: dict[str, Any]) -> TaskState:
    return TaskState(
        model="mockllm/model",
        sample_id="sample-1",
        epoch=1,
        input="Question?",
        messages=[],
        output=ModelOutput.from_content("mockllm/model", completion),
        metadata=metadata,
    )


class TestParseJudgeVerdict:
    @pytest.mark.parametrize(
        "verdict",
        ["correct", "incorrect", "unsure"],
    )
    def test_parses_each_verdict(self, verdict: str) -> None:
        # given / when
        sut = parse_judge_verdict(f"Rationale: ...\nresult: {verdict}")
        # then
        assert sut == verdict

    @pytest.mark.parametrize(
        "decorated",
        [
            "result: correct",
            "**Result**\ncorrect",
            "## Result\ncorrect",
            "**Result:** *correct*",
            "- Result -> correct",
        ],
    )
    def test_tolerates_markdown_decoration(self, decorated: str) -> None:
        assert parse_judge_verdict(f"Rationale: ...\n{decorated}") == "correct"

    def test_is_case_insensitive(self) -> None:
        assert parse_judge_verdict("RESULT: CORRECT") == "correct"

    def test_returns_none_when_absent(self) -> None:
        assert parse_judge_verdict("No verdict in this text.") is None

    def test_returns_none_for_empty(self) -> None:
        assert parse_judge_verdict("") is None

    def test_last_verdict_wins(self) -> None:
        # given the rubric words echoed before the final verdict
        text = "Options are result: incorrect or result: unsure.\nresult: correct"
        # when / then
        assert parse_judge_verdict(text) == "correct"

    def test_parses_recall_style_output_with_format_suffix(self) -> None:
        # given a recall-style judgement that echoes the rubric, then closes
        # with the verdict line that VERDICT_FORMAT_SUFFIX instructs
        text = (
            "Matched 5/6 expected variables. Recall = 0.83 < 0.95.\nresult: incorrect"
        )
        # when / then
        assert parse_judge_verdict(text) == "incorrect"

    def test_ignores_code_assignment(self) -> None:
        # given grader output that is code rather than a verdict — `result =
        # "correct"` is an assignment, not a graded result
        text = '    result = "unknown"\n        result = "correct"\n    return result'
        # when / then
        assert parse_judge_verdict(text) is None


class TestScorerForTag:
    @pytest.mark.parametrize("tag", sorted(SCORERS_BY_TAG))
    def test_returns_scorer_for_supported_tag(self, tag: str) -> None:
        assert isinstance(scorer_for_tag(tag), Scorer)

    def test_routing_table_matches_supported_tags(self) -> None:
        # given/when/then — the task gate and the scorer routing list the same tags
        assert set(SCORERS_BY_TAG) == set(SUPPORTED_TAGS)

    def test_unsupported_tag_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            scorer_for_tag("bogusqa")


def test_semantic_judge_scorer_is_scorer() -> None:
    assert isinstance(semantic_judge_scorer(), Scorer)


def test_recall_judge_scorer_is_scorer() -> None:
    assert isinstance(recall_judge_scorer(), Scorer)


def test_exact_match_judge_scorer_is_scorer() -> None:
    assert isinstance(exact_match_judge_scorer(), Scorer)


class TestCloningScorer:
    async def test_scores_correct_when_reward_passes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # given a resolvable reference assembly and a passing cloning reward
        reference = tmp_path / "clone_1_assembled.fa"
        reference.write_text(">ref\nACGT\n")

        async def fake_cloning_reward(**kwargs: Any) -> tuple[float, str]:
            # then the scorer forwards files_path and the resolved reference
            assert kwargs["base_dir"] == tmp_path
            assert kwargs["reference_path"] == reference
            return 1.0, "Cloning validation passed"

        monkeypatch.setattr(
            "labbench2.cloning.rewards.cloning_reward", fake_cloning_reward
        )
        monkeypatch.setattr(
            "evals.utils.resolve_file_path",
            lambda filename, _: (
                reference if filename == "clone_1_assembled.fa" else None
            ),
        )

        # when
        sut = cloning_scorer()
        state = _task_state(
            "<protocol>assemble</protocol>",
            {"tag": "cloning", "id": "clone_1", "files_path": str(tmp_path)},
        )
        result = await sut(state, Target(""))

        # then
        assert result == Score(
            value=CORRECT,
            explanation="Cloning validation passed",
            metadata={"cloning_score": 1.0},
        )

    async def test_scores_incorrect_when_reward_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # given a cloning reward below the pass threshold
        async def fake_cloning_reward(**kwargs: Any) -> tuple[float, str]:
            return 0.0, "Accuracy failed: output does not match reference"

        monkeypatch.setattr(
            "labbench2.cloning.rewards.cloning_reward", fake_cloning_reward
        )
        monkeypatch.setattr(
            "evals.utils.resolve_file_path", lambda filename, _: tmp_path / filename
        )

        # when
        sut = cloning_scorer()
        state = _task_state(
            "<protocol>assemble</protocol>",
            {"tag": "cloning", "id": "clone_1", "files_path": str(tmp_path)},
        )
        result = await sut(state, Target(""))

        # then
        assert result.value == INCORRECT
        assert result.metadata == {"cloning_score": 0.0}

    async def test_incorrect_without_files_path_or_id(self) -> None:
        # given metadata missing files_path and id
        sut = cloning_scorer()
        state = _task_state("<protocol>assemble</protocol>", {"tag": "cloning"})

        # when
        result = await sut(state, Target(""))

        # then it fails closed before resolving or scoring
        assert result.value == INCORRECT
        assert "files_path and id" in (result.explanation or "")

    async def test_incorrect_when_ground_truth_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # given the reference assembly cannot be resolved
        monkeypatch.setattr("evals.utils.resolve_file_path", lambda filename, _: None)

        # when
        sut = cloning_scorer()
        state = _task_state(
            "<protocol>assemble</protocol>",
            {"tag": "cloning", "id": "clone_1", "files_path": str(tmp_path)},
        )
        result = await sut(state, Target(""))

        # then
        assert result.value == INCORRECT
        assert "Ground truth file not found" in (result.explanation or "")
