from pathlib import Path

import pytest

from lab_bench_2 import file_downloader


class TestListFiles:
    def test_returns_files_sorted_alphabetically(self, tmp_path: Path) -> None:
        # given a directory with files out of alphabetical order
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "c.txt").write_text("c")

        # when
        result = file_downloader.list_files(tmp_path)

        # then
        assert [p.name for p in result] == ["a.txt", "b.txt", "c.txt"]

    def test_skips_subdirectories(self, tmp_path: Path) -> None:
        # given a directory containing both files and a subdirectory
        (tmp_path / "data.txt").write_text("payload")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "ignored.txt").write_text("ignored")

        # when
        result = file_downloader.list_files(tmp_path)

        # then
        assert [p.name for p in result] == ["data.txt"]


class TestFetch:
    def test_raises_when_no_files_downloaded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a download that returns an empty directory
        monkeypatch.setattr("evals.utils.download_question_files", lambda **_: tmp_path)

        # when / then
        with pytest.raises(RuntimeError, match="none were downloaded"):
            file_downloader.fetch("some/prefix")

    def test_returns_directory_when_populated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a populated download
        (tmp_path / "ok.txt").write_text("ok")
        monkeypatch.setattr("evals.utils.download_question_files", lambda **_: tmp_path)

        # when
        result = file_downloader.fetch("some/prefix")

        # then
        assert result == tmp_path

    def test_forwards_bucket_name_kwarg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given a stub that records its kwargs
        (tmp_path / "ok.txt").write_text("ok")
        captured: dict[str, str] = {}

        def stub(**kwargs: str) -> Path:
            captured.update(kwargs)
            return tmp_path

        monkeypatch.setattr("evals.utils.download_question_files", stub)

        # when
        file_downloader.fetch("some/prefix", bucket_name="custom-bucket")

        # then
        assert captured == {"bucket_name": "custom-bucket", "gcs_prefix": "some/prefix"}
