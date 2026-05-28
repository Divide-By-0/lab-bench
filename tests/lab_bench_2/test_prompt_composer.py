from pathlib import Path

from lab_bench_2 import prompt_composer
from lab_bench_2.prompt_composer import FILE_REFERENCE_INSTRUCTION


class TestCompose:
    def test_returns_question_unchanged_when_no_files_and_no_suffix(self) -> None:
        # given a file-less question with no suffix
        sut = prompt_composer.compose("Q?", mode="inject", files=[])

        # then
        assert sut == "Q?"

    def test_appends_prompt_suffix_with_blank_line(self) -> None:
        # when
        sut = prompt_composer.compose(
            "Q?", mode="inject", files=[], prompt_suffix="Be concise."
        )

        # then
        assert sut == "Q?\n\nBe concise."

    def test_inject_concatenates_text_files_under_headers(self, tmp_path: Path) -> None:
        # given two injectable text files
        a = tmp_path / "a.txt"
        a.write_text("alpha")
        b = tmp_path / "b.txt"
        b.write_text("beta")

        # when
        sut = prompt_composer.compose("Q?", mode="inject", files=[a, b])

        # then
        assert sut == "Q?\n\nFiles:\n\n## a.txt\n\nalpha\n\n## b.txt\n\nbeta"

    def test_inject_skips_non_injectable_formats(self, tmp_path: Path) -> None:
        # given a binary (PDF) file alongside an injectable text file
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        txt = tmp_path / "notes.txt"
        txt.write_text("just text")

        # when
        sut = prompt_composer.compose("Q?", mode="inject", files=[pdf, txt])

        # then — only the .txt content is injected; the .pdf is omitted
        assert sut == "Q?\n\nFiles:\n\n## notes.txt\n\njust text"

    def test_inject_skips_files_section_when_nothing_injectable(
        self, tmp_path: Path
    ) -> None:
        # given only a non-injectable file
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        # when
        sut = prompt_composer.compose("Q?", mode="inject", files=[pdf])

        # then — no "Files:" section added
        assert sut == "Q?"

    def test_file_mode_appends_basename_instruction(self, tmp_path: Path) -> None:
        # given any file
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")

        # when
        sut = prompt_composer.compose("Q?", mode="file", files=[f])

        # then
        assert sut == "Q?" + FILE_REFERENCE_INSTRUCTION

    def test_retrieve_lists_file_stems_in_instruction(self, tmp_path: Path) -> None:
        # given files with distinct stems
        seq1 = tmp_path / "plasmid_A.gb"
        seq1.write_text(">A")
        seq2 = tmp_path / "plasmid_B.fasta"
        seq2.write_text(">B")

        # when
        sut = prompt_composer.compose("Q?", mode="retrieve", files=[seq1, seq2])

        # then
        assert "plasmid_A, plasmid_B" in sut
        assert "Retrieve the necessary sequences" in sut

    def test_prompt_suffix_lands_after_mode_specific_content(
        self, tmp_path: Path
    ) -> None:
        # given an inject-mode question with a suffix
        txt = tmp_path / "data.txt"
        txt.write_text("payload")

        # when
        sut = prompt_composer.compose(
            "Q?", mode="inject", files=[txt], prompt_suffix="Be concise."
        )

        # then — suffix lands at the very end, after the injected content
        assert sut.endswith("\n\nBe concise.")
        assert "payload" in sut
        assert sut.index("payload") < sut.index("Be concise.")
