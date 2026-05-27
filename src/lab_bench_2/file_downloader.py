"""GCS-backed file downloads for LAB-Bench 2 questions."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from evals.utils import GCS_BUCKET, download_question_files


class FileDownloader:
    """Downloads a question's files from GCS into the shared local cache.

    Caching, atomic writes, and concurrency-safe locking are delegated to
    ``evals.utils.download_question_files`` (the reference implementation's
    filelock-guarded cache at ``~/.cache/labbench2/``).
    """

    def __init__(self, bucket_name: str = GCS_BUCKET) -> None:
        self._bucket_name = bucket_name

    def fetch(self, gcs_prefix: str) -> Path:
        """Download files under ``gcs_prefix`` and return the local directory.

        Raises ``RuntimeError`` if the prefix yields no files.
        """
        files_path = cast(
            Path,
            download_question_files(
                bucket_name=self._bucket_name, gcs_prefix=gcs_prefix
            ),
        )
        if not files_path.exists() or not any(files_path.iterdir()):
            raise RuntimeError(
                f"Question expects files at '{gcs_prefix}' but none were downloaded."
            )
        return files_path

    @staticmethod
    def list_files(directory: Path) -> list[Path]:
        """Return files in ``directory``, deterministically sorted."""
        return sorted(path for path in directory.iterdir() if path.is_file())
