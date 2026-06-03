from lab_bench_2.seqqa2_answer_parser import (
    _is_nucleotide_only_answer_regex,
    _normalized_answer_attempts,
    extract,
)


class TestExtract:
    def test_collapses_ascii_whitespace(self) -> None:
        # given a wrapped answer whose regex expects single spaces
        extracted = extract(
            "<answer>FORWARD,\n   REVERSE</answer>",
            r"(?P<answer>FORWARD, REVERSE)",
        )
        # then whitespace runs collapse to a single space before matching
        assert extracted == {"answer": "FORWARD, REVERSE"}

    def test_strips_internal_whitespace_for_nucleotides(self) -> None:
        # given spaced sequences and a nucleotide-only regex
        extracted = extract(
            "<answer>ATGC TGCA,\n   AATT CCGG</answer>",
            r"(?P<forward>[ATGCatgc]+),(?P<reverse>[ATGCatgc]+)",
        )
        # then internal whitespace is removed so the sequences match
        assert extracted == {"forward": "ATGCTGCA", "reverse": "AATTCCGG"}

    def test_accepts_bare_numeric_answer(self) -> None:
        extracted = extract("25.67", r"(?P<answer>25\.67)")
        assert extracted == {"answer": "25.67"}

    def test_accepts_bare_nucleotide_answer(self) -> None:
        extracted = extract("ATGC TGCA", r"(?P<answer>[ATGCatgc]+)")
        assert extracted == {"answer": "ATGCTGCA"}

    def test_accepts_bare_paired_answer(self) -> None:
        extracted = extract("931,747", r"(?P<left>\d+),(?P<right>\d+)")
        assert extracted == {"left": "931", "right": "747"}

    def test_rejects_invalid_bare_answer(self) -> None:
        assert extract("NA,NA", r"(?P<left>\d+),(?P<right>\d+)") is None

    def test_returns_none_without_regex(self) -> None:
        assert extract("anything", None) is None


class TestIsNucleotideOnlyAnswerRegex:
    def test_true_for_nucleotide_regex(self) -> None:
        assert _is_nucleotide_only_answer_regex(r"(?P<answer>[ATGCatgc]+)") is True

    def test_false_for_word_regex(self) -> None:
        assert (
            _is_nucleotide_only_answer_regex(r"(?P<answer>FORWARD, REVERSE)") is False
        )


class TestNormalizedAnswerAttempts:
    def test_collapses_whitespace_for_non_nucleotide(self) -> None:
        # given a non-nucleotide regex, only the space-collapsed variant is tried
        assert _normalized_answer_attempts("FOR\n  WARD", r"(?P<answer>FORWARD)") == [
            "FOR WARD"
        ]

    def test_adds_stripped_variant_for_nucleotides(self) -> None:
        # given a nucleotide regex, also try removing internal whitespace
        assert _normalized_answer_attempts("AT GC", r"(?P<answer>[ATGC]+)") == [
            "AT GC",
            "ATGC",
        ]
