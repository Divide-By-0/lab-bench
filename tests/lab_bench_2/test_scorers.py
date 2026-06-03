from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from inspect_ai.model import ModelName, ModelOutput
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target
from inspect_ai.solver import TaskState

from lab_bench_2 import SUPPORTED_TAGS, parse_judge_verdict, scorers
from lab_bench_2.scorers import (
    SCORERS_BY_TAG,
    cloning_scorer,
    exact_match_judge_scorer,
    recall_judge_scorer,
    scorer_for_tag,
    semantic_judge_scorer,
    seqqa2_scorer,
)


def _task_state(completion: str, metadata: dict[str, Any]) -> TaskState:
    return TaskState(
        model=ModelName("mockllm/model"),
        sample_id="sample-1",
        epoch=1,
        input="Question?",
        messages=[],
        output=ModelOutput.from_content("mockllm/model", completion),
        metadata=metadata,
    )


async def _score(sut: Scorer, state: TaskState, target: Target) -> Score:
    """Run a scorer and assert it produced a Score (narrows ``Score | None``)."""
    result = await sut(state, target)
    assert result is not None
    return result


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


def _patch_grader(monkeypatch: pytest.MonkeyPatch, completion: str) -> None:
    class _Grader:
        async def generate(self, prompt: str, **kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(completion=completion)

    monkeypatch.setattr(scorers, "get_model", lambda *args, **kwargs: _Grader())


class TestJudgeScorer:
    async def test_structured_correct_verdict_scores_correct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a grader returning a structured (typed) correct verdict
        _patch_grader(
            monkeypatch,
            '{"rationale": "matches the reference", "result": "correct"}',
        )
        # when
        sut = semantic_judge_scorer()
        result = await _score(
            sut, _task_state("answer", {"tag": "litqa3"}), Target("ref")
        )
        # then the typed rationale and verdict are used
        assert result.value == CORRECT
        assert result.explanation == "matches the reference"
        assert result.metadata == {
            "verdict": "correct",
            "verdict_source": "structured",
        }

    @pytest.mark.parametrize("verdict", ["incorrect", "unsure"])
    async def test_structured_non_correct_verdict_scores_incorrect(
        self, monkeypatch: pytest.MonkeyPatch, verdict: str
    ) -> None:
        _patch_grader(monkeypatch, f'{{"rationale": "x", "result": "{verdict}"}}')
        sut = semantic_judge_scorer()
        result = await _score(
            sut, _task_state("answer", {"tag": "litqa3"}), Target("ref")
        )
        assert result.value == INCORRECT
        assert result.metadata == {"verdict": verdict, "verdict_source": "structured"}

    async def test_falls_back_to_regex_for_non_structured_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a grader that ignores the schema and returns free text
        _patch_grader(monkeypatch, "Reasoning here.\nresult: correct")
        # when
        sut = semantic_judge_scorer()
        result = await _score(
            sut, _task_state("answer", {"tag": "litqa3"}), Target("ref")
        )
        # then the regex fallback recovers the verdict
        assert result.value == CORRECT
        assert result.metadata == {"verdict": "correct", "verdict_source": "fallback"}

    @pytest.mark.parametrize(
        "completion, expected_verdict",
        [
            ("Reasoning here.\nresult: incorrect", "incorrect"),
            ("no parseable verdict in this text", None),
        ],
    )
    async def test_falls_back_to_regex_scores_incorrect(
        self,
        monkeypatch: pytest.MonkeyPatch,
        completion: str,
        expected_verdict: str | None,
    ) -> None:
        # given non-structured grader output that is not a correct verdict
        # (a parsed "incorrect", or nothing parseable at all)
        _patch_grader(monkeypatch, completion)
        # when
        sut = semantic_judge_scorer()
        result = await _score(
            sut, _task_state("answer", {"tag": "litqa3"}), Target("ref")
        )
        # then it scores incorrect
        assert result.value == INCORRECT
        assert result.metadata == {
            "verdict": expected_verdict,
            "verdict_source": "fallback",
        }

    async def test_empty_answer_scores_incorrect(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given an empty answer but correct grade
        answer = "   "
        _patch_grader(monkeypatch, '{"rationale": "x", "result": "correct"}')

        # when
        sut = semantic_judge_scorer()
        result = await _score(
            sut, _task_state(answer, {"tag": "litqa3"}), Target("ref")
        )

        # then
        assert result.value == INCORRECT
        assert "No answer" in (result.explanation or "")


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
        result = await _score(sut, state, Target(""))

        # then
        assert result == Score(
            value=CORRECT,
            answer="<protocol>assemble</protocol>",
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
        result = await _score(sut, state, Target(""))

        # then
        assert result.value == INCORRECT
        assert result.metadata == {"cloning_score": 0.0}

    async def test_incorrect_without_files_path_or_id(self) -> None:
        # given metadata missing files_path and id
        sut = cloning_scorer()
        state = _task_state("<protocol>assemble</protocol>", {"tag": "cloning"})

        # when
        result = await _score(sut, state, Target(""))

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
        result = await _score(sut, state, Target(""))

        # then
        assert result.value == INCORRECT
        assert "Ground truth file not found" in (result.explanation or "")


class TestSeqqa2Scorer:
    async def test_dispatches_to_validator_and_scores_correct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from labbench2.seqqa2.registry import VALIDATORS

        # given a dummy validator registered for a question type
        validator = SimpleNamespace(answer_param="answer", func=lambda answer: 1.0)
        monkeypatch.setitem(VALIDATORS, "dummy_validator", validator)

        # when
        sut = seqqa2_scorer()
        state = _task_state(
            "<answer>pass</answer>",
            {
                "tag": "seqqa2",
                "type": "dummy_validator",
                "answer_regex": "(?P<answer>pass)",
                "validator_params": {},
            },
        )
        result = await _score(sut, state, Target(""))

        # then
        assert result == Score(
            value=CORRECT,
            answer="<answer>pass</answer>",
            explanation="Validator 'dummy_validator' passed",
            metadata={"validator": "dummy_validator", "validator_score": 1.0},
        )

    async def test_renames_answer_param_for_validator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from labbench2.seqqa2.registry import VALIDATORS

        captured: dict[str, Any] = {}

        def validator_func(sequence: str) -> float:
            captured["sequence"] = sequence
            return 1.0

        # given a validator whose answer param is named "sequence"
        validator = SimpleNamespace(answer_param="sequence", func=validator_func)
        monkeypatch.setitem(VALIDATORS, "rename_validator", validator)

        # when
        sut = seqqa2_scorer()
        state = _task_state(
            "<answer>ACTG</answer>",
            {
                "tag": "seqqa2",
                "type": "rename_validator",
                "answer_regex": "(?P<answer>ACTG)",
                "validator_params": {},
            },
        )
        result = await _score(sut, state, Target(""))

        # then the extracted answer is passed under the validator's param name
        assert result.value == CORRECT
        assert captured == {"sequence": "ACTG"}

    async def test_incorrect_for_unknown_validator_type(self) -> None:
        sut = seqqa2_scorer()
        state = _task_state(
            "<answer>x</answer>",
            {
                "tag": "seqqa2",
                "type": "does_not_exist",
                "answer_regex": "(?P<answer>x)",
            },
        )
        result = await _score(sut, state, Target(""))
        assert result.value == INCORRECT
        assert "No validator found" in (result.explanation or "")

    async def test_incorrect_when_type_missing(self) -> None:
        sut = seqqa2_scorer()
        state = _task_state("<answer>x</answer>", {"tag": "seqqa2"})
        result = await _score(sut, state, Target(""))
        assert result.value == INCORRECT
        assert "question type" in (result.explanation or "")

    async def test_fail_closed_when_path_param_unresolved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from labbench2.seqqa2.registry import VALIDATORS

        # given a validator with a _path param that cannot be resolved
        validator = SimpleNamespace(answer_param="answer", func=lambda **kw: 1.0)
        monkeypatch.setitem(VALIDATORS, "path_validator", validator)
        monkeypatch.setattr("evals.utils.resolve_file_path", lambda value, _: None)

        # when
        sut = seqqa2_scorer()
        state = _task_state(
            "<answer>x</answer>",
            {
                "tag": "seqqa2",
                "type": "path_validator",
                "answer_regex": "(?P<answer>x)",
                "validator_params": {"reference_path": "missing.fa"},
            },
        )
        result = await _score(sut, state, Target(""))

        # then it fails closed rather than calling the validator
        assert result.value == INCORRECT
        assert "File not found: missing.fa" in (result.explanation or "")
