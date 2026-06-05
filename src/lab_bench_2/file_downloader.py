"""GCS-backed file downloads for LAB-Bench 2 questions.

Caching, atomic writes, and concurrency-safe locking are delegated to
``evals.utils.download_question_files`` (the reference implementation's
filelock-guarded cache at ``~/.cache/labbench2/``).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast


def fetch(gcs_prefix: str, bucket_name: str | None = None) -> Path:
    """Download files under ``gcs_prefix`` and return the local directory.

    ``bucket_name`` defaults to the reference implementation's ``GCS_BUCKET``
    when omitted. Raises ``RuntimeError`` if the prefix yields no files.
    """
    from evals.utils import GCS_BUCKET, download_question_files

    if bucket_name is None:
        bucket_name = GCS_BUCKET
    files_path = cast(
        Path,
        download_question_files(bucket_name=bucket_name, gcs_prefix=gcs_prefix),
    )
    if not files_path.exists() or not any(files_path.iterdir()):
        raise RuntimeError(
            f"Question expects files at '{gcs_prefix}' but none were downloaded."
        )
    return files_path


def list_files(directory: Path) -> list[Path]:
    """Return files in ``directory``, deterministically sorted."""
    return sorted(path for path in directory.iterdir() if path.is_file())
