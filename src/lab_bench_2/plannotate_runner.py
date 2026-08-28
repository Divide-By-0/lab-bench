"""Run pLannotate as a separate, provenance-preserving enrichment pass."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from lab_bench_2.cloning_inventory import SEQUENCE_FORMATS, discover_sequence_files

PLANNOTATE_VERSION = "2.0.0"
DEFAULT_CACHE_DIR = Path.home() / ".cache/labbench2/plannotate-v2"
EXACT_IDENTITY_PERCENT = 100.0
FULL_LENGTH_COVERAGE_PERCENT = 99.9


class PlannotateError(RuntimeError):
    """Raised when the managed pLannotate enrichment cannot run safely."""


@dataclass(frozen=True)
class PlannotateEnvironment:
    """Resolved executable and database provenance for one annotation run."""

    command: list[str]
    version_report: str
    database_manifest: dict[str, Any]
    managed_environment: bool


RunCommand = Callable[..., subprocess.CompletedProcess[str]]
WhichCommand = Callable[[str], str | None]


def prepare_plannotate(
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    auto_setup: bool = True,
    run: RunCommand = subprocess.run,
    which: WhichCommand = shutil.which,
) -> PlannotateEnvironment:
    """Find pLannotate or create a cached conda environment, then install its DBs."""
    cache_dir = cache_dir.expanduser().resolve()
    executable = which("plannotate")
    managed = False
    if executable:
        command = [executable]
    else:
        managed = True
        command = [_managed_executable(cache_dir)]
        if not Path(command[0]).is_file():
            if not auto_setup:
                raise PlannotateError(
                    "pLannotate is not installed and automatic setup is disabled"
                )
            _create_managed_environment(cache_dir, run=run, which=which)
        if not Path(command[0]).is_file():
            raise PlannotateError("Managed pLannotate setup did not create its CLI")

    database_result = _run([*command, "databases"], run=run, timeout=60, check=False)
    if database_result.returncode != 0:
        if not auto_setup:
            raise PlannotateError(
                "pLannotate databases are absent and automatic setup is disabled"
            )
        _run([*command, "setupdb"], run=run, timeout=900)
        database_result = _run([*command, "databases"], run=run, timeout=60)
    try:
        database_manifest = json.loads(database_result.stdout)
    except json.JSONDecodeError as exc:
        raise PlannotateError(
            "pLannotate returned an invalid database manifest"
        ) from exc
    if not isinstance(database_manifest, dict):
        raise PlannotateError("pLannotate database manifest is not an object")
    version_result = _run([*command, "--version"], run=run, timeout=60)
    version_report = version_result.stdout.strip()
    if f"pLannotate {PLANNOTATE_VERSION}" not in version_report:
        raise PlannotateError(
            f"Expected pLannotate {PLANNOTATE_VERSION}, got: {version_report}"
        )
    return PlannotateEnvironment(
        command=command,
        version_report=version_report,
        database_manifest=database_manifest,
        managed_environment=managed,
    )


def annotate_with_plannotate(
    inputs: Sequence[Path],
    output_dir: Path,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    fast: bool = True,
    cores: int = 4,
    refresh: bool = False,
    auto_setup: bool = True,
    run: RunCommand = subprocess.run,
    which: WhichCommand = shutil.which,
) -> dict[str, Any]:
    """Annotate files into a separate directory and return a source-linked manifest."""
    if cores < 1:
        raise ValueError("cores must be positive")
    files = discover_sequence_files(inputs)
    if not files:
        raise ValueError("No supported sequence files found")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    environment = prepare_plannotate(
        cache_dir, auto_setup=auto_setup, run=run, which=which
    )
    prior = _read_prior_manifest(output_dir / "plannotate-manifest.json")
    prior_by_hash = {
        str(item.get("source_sha256")): item
        for item in prior.get("results", [])
        if isinstance(item, dict)
    }

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source_file in files:
        source_hash = _sha256_file(source_file)
        cached = prior_by_hash.get(source_hash)
        if not refresh and cached and _outputs_exist(output_dir, cached):
            results.append({**cached, "status": "cache-hit"})
            continue
        output_stem = _output_stem(source_file, source_hash)
        command = build_annotation_command(
            environment.command,
            source_file,
            output_dir,
            output_stem,
            fast=fast,
            cores=cores,
        )
        try:
            _run(command, run=run, timeout=1800)
        except PlannotateError as exc:
            errors.append({"source_path": str(source_file), "error": str(exc)})
            continue
        outputs = sorted(
            path.name for path in output_dir.glob(f"{output_stem}*") if path.is_file()
        )
        if not outputs:
            errors.append(
                {
                    "source_path": str(source_file),
                    "error": "pLannotate created no output files",
                }
            )
            continue
        results.append(
            {
                "source_path": str(source_file),
                "source_sha256": source_hash,
                "source_format": SEQUENCE_FORMATS[source_file.suffix.casefold()],
                "status": "annotated",
                "mode": "fast" if fast else "full",
                "linear": _is_linear(source_file),
                "outputs": outputs,
                "output_sha256": {
                    name: _sha256_file(output_dir / name) for name in outputs
                },
                "annotation_summary": _summarize_plannotate_outputs(
                    output_dir, outputs
                ),
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "tool": {
            "name": "pLannotate",
            "version": PLANNOTATE_VERSION,
            "version_report": environment.version_report,
            "managed_environment": environment.managed_environment,
            "database_manifest": environment.database_manifest,
        },
        "policy": {
            "source_files_modified": False,
            "outputs_are_enrichment_candidates": True,
            "mode": "fast" if fast else "full",
        },
        "summary": {
            "discovered_file_count": len(files),
            "annotated_or_cached_count": len(results),
            "error_count": len(errors),
        },
        "results": results,
        "errors": errors,
    }
    _write_json_atomic(output_dir / "plannotate-manifest.json", manifest)
    return manifest


def build_annotation_command(
    plannotate_command: Sequence[str],
    source_file: Path,
    output_dir: Path,
    output_stem: str,
    *,
    fast: bool,
    cores: int,
) -> list[str]:
    """Build the pLannotate CLI invocation for one source file."""
    command = [
        *plannotate_command,
        "batch",
        "--input",
        str(source_file),
        "--output",
        str(output_dir),
        "--file-name",
        output_stem,
        "--suffix",
        "",
        "--csv",
        "--cores",
        str(cores),
    ]
    if _is_linear(source_file):
        command.append("--linear")
    if fast:
        command.append("--fast")
    return command


def _create_managed_environment(
    cache_dir: Path, *, run: RunCommand, which: WhichCommand
) -> None:
    manager = next(
        (
            resolved
            for name in ("micromamba", "mamba", "conda")
            if (resolved := which(name))
        ),
        None,
    )
    if manager is None:
        raise PlannotateError(
            "Automatic pLannotate setup requires micromamba, mamba, or conda"
        )
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            manager,
            "create",
            "--yes",
            "--prefix",
            str(cache_dir),
            "--channel",
            "conda-forge",
            "--channel",
            "bioconda",
            f"plannotate={PLANNOTATE_VERSION}",
        ],
        run=run,
        timeout=1800,
    )


def _managed_executable(cache_dir: Path) -> str:
    unix = cache_dir / "bin/plannotate"
    windows = cache_dir / "Scripts/plannotate.exe"
    return str(windows if windows.is_file() else unix)


def _is_linear(source_file: Path) -> bool:
    if SEQUENCE_FORMATS[source_file.suffix.casefold()] == "fasta":
        return True
    try:
        from Bio import SeqIO

        with source_file.open(encoding="utf-8") as handle:
            records = list(SeqIO.parse(handle, "genbank"))  # type: ignore[no-untyped-call]
    except (ModuleNotFoundError, OSError, ValueError):
        return False
    return bool(records) and all(
        str(record.annotations.get("topology") or "").casefold() == "linear"
        for record in records
    )


def _output_stem(source_file: Path, source_hash: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_file.stem).strip("_")
    return f"{safe_name or 'sequence'}-{source_hash[:12]}"


def _read_prior_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _outputs_exist(output_dir: Path, item: dict[str, Any]) -> bool:
    outputs = item.get("outputs")
    hashes = item.get("output_sha256")
    if not isinstance(outputs, list) or not isinstance(hashes, dict) or not outputs:
        return False
    return all(
        isinstance(name, str)
        and (output_dir / name).is_file()
        and _sha256_file(output_dir / name) == hashes.get(name)
        for name in outputs
    )


def _summarize_plannotate_outputs(
    output_dir: Path, outputs: Sequence[str]
) -> dict[str, Any]:
    annotations: list[dict[str, Any]] = []
    database_counts: dict[str, int] = {}
    for name in outputs:
        if Path(name).suffix.casefold() != ".csv":
            continue
        with (output_dir / name).open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                database = str(row.get("database") or "")
                fragment = str(row.get("fragment") or "").casefold() == "true"
                identity = _optional_float(row.get("percent identity"))
                match_coverage = _optional_float(row.get("percent match length"))
                annotations.append(
                    {
                        "feature": str(row.get("Feature") or ""),
                        "feature_type": str(row.get("Type") or ""),
                        "description": str(row.get("Description") or ""),
                        "database": database,
                        "fragment": fragment,
                        "percent_identity": identity,
                        "percent_match_length": match_coverage,
                    }
                )
                database_counts[database] = database_counts.get(database, 0) + 1
    return {
        "annotation_count": len(annotations),
        "fragment_count": sum(item["fragment"] for item in annotations),
        "non_fragment_count": sum(not item["fragment"] for item in annotations),
        "exact_full_length_count": sum(
            item["percent_identity"] == EXACT_IDENTITY_PERCENT
            and item["percent_match_length"] is not None
            and item["percent_match_length"] >= FULL_LENGTH_COVERAGE_PERCENT
            for item in annotations
        ),
        "database_counts": dict(sorted(database_counts.items())),
        "annotations": annotations,
    }


def _optional_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _run(
    command: Sequence[str],
    *,
    run: RunCommand,
    timeout: float,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    executable_directory = str(Path(command[0]).expanduser().resolve().parent)
    environment = {
        **os.environ,
        "PATH": executable_directory + os.pathsep + os.environ.get("PATH", ""),
    }
    try:
        result = run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlannotateError(f"Command failed to start: {command[0]}: {exc}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        raise PlannotateError(f"pLannotate failed: {detail}")
    return result
