import pytest
from inspect_ai.scorer import Scorer

from lab_bench_2 import parse_judge_verdict
from lab_bench_2.scorers import scorer_for_tag, semantic_judge_scorer


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


class TestScorerForTag:
    def test_litqa3_returns_scorer(self) -> None:
        assert isinstance(scorer_for_tag("litqa3"), Scorer)

    def test_unsupported_tag_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            scorer_for_tag("seqqa2")


def test_semantic_judge_scorer_is_scorer() -> None:
    assert isinstance(semantic_judge_scorer(), Scorer)
