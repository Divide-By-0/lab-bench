from pathlib import Path

import pytest

from lab_bench_2 import file_downloader as file_downloader_module
from lab_bench_2.file_downloader import FileDownloader


class TestListFiles:
    def test_returns_files_sorted_alphabetically(self, tmp_path: Path) -> None:
        # given a directory with files out of alphabetical order
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "c.txt").write_text("c")

        # when
        sut = FileDownloader.list_files(tmp_path)

        # then
        assert [p.name for p in sut] == ["a.txt", "b.txt", "c.txt"]

    def test_skips_subdirectories(self, tmp_path: Path) -> None:
        # given a directory containing both files and a subdirectory
        (tmp_path / "data.txt").write_text("payload")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "ignored.txt").write_text("ignored")

        # when
        sut = FileDownloader.list_files(tmp_path)

        # then
        assert [p.name for p in sut] == ["data.txt"]


class TestFetch:
    def test_raises_when_no_files_downloaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a download that returns an empty directory
        monkeypatch.setattr(
            file_downloader_module, "download_question_files", lambda **_: tmp_path
        )

        # when / then
        with pytest.raises(RuntimeError, match="none were downloaded"):
            FileDownloader().fetch("some/prefix")

    def test_returns_directory_when_populated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a populated download
        (tmp_path / "ok.txt").write_text("ok")
        monkeypatch.setattr(
            file_downloader_module, "download_question_files", lambda **_: tmp_path
        )

        # when
        sut = FileDownloader().fetch("some/prefix")

        # then
        assert sut == tmp_path
