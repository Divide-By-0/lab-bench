import pytest
from inspect_ai.scorer import Scorer

from lab_bench_2 import SUPPORTED_TAGS, parse_judge_verdict
from lab_bench_2.scorers import (
    SCORERS_BY_TAG,
    exact_match_judge_scorer,
    recall_judge_scorer,
    scorer_for_tag,
    semantic_judge_scorer,
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


class TestScorerForTag:
    @pytest.mark.parametrize("tag", sorted(SCORERS_BY_TAG))
    def test_returns_scorer_for_supported_tag(self, tag: str) -> None:
        assert isinstance(scorer_for_tag(tag), Scorer)

    def test_routing_table_matches_supported_tags(self) -> None:
        # given/when/then — the task gate and the scorer routing list the same tags
        assert set(SCORERS_BY_TAG) == set(SUPPORTED_TAGS)

    def test_unsupported_tag_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            scorer_for_tag("seqqa2")


def test_semantic_judge_scorer_is_scorer() -> None:
    assert isinstance(semantic_judge_scorer(), Scorer)


def test_recall_judge_scorer_is_scorer() -> None:
    assert isinstance(recall_judge_scorer(), Scorer)


def test_exact_match_judge_scorer_is_scorer() -> None:
    assert isinstance(exact_match_judge_scorer(), Scorer)
