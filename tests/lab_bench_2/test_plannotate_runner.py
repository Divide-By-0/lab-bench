from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lab_bench_2.plannotate_runner import (
    annotate_with_plannotate,
    build_annotation_command,
    prepare_plannotate,
)


class FakePlannotate:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.environments: list[dict[str, str]] = []

    def __call__(
        self, command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        environment = kwargs.get("env")
        assert isinstance(environment, dict)
        self.environments.append(environment)
        self.commands.append(command)
        if command[-1] == "databases":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "schema_version": 1,
                        "bundle": "plannotate-databases-v2",
                        "files": {"BLAST_dbs/snapgene.db": {"sha256": "db"}},
                    }
                ),
                stderr="",
            )
        if command[-1] == "--version":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="pLannotate 2.0.0\ndatabase: plannotate-databases-v2\n",
                stderr="",
            )
        if "batch" in command:
            output_dir = Path(command[command.index("--output") + 1])
            stem = command[command.index("--file-name") + 1]
            (output_dir / f"{stem}.gbk").write_text("annotated genbank")
            (output_dir / f"{stem}.csv").write_text(
                "Feature,Type,Description,database,fragment,percent identity,percent match length\n"
                "Cas9,CDS,editor,snapgene,False,100.0,100.0\n"
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(command)


def test_prepare_reads_version_and_database_provenance(tmp_path: Path) -> None:
    fake = FakePlannotate()

    environment = prepare_plannotate(
        tmp_path,
        run=fake,
        which=lambda name: "/usr/local/bin/plannotate"
        if name == "plannotate"
        else None,
    )

    assert environment.command == ["/usr/local/bin/plannotate"]
    assert environment.database_manifest["bundle"] == "plannotate-databases-v2"
    assert environment.managed_environment is False
    assert fake.environments[0]["PATH"].split(":", 1)[0] == "/usr/local/bin"


def test_fasta_annotation_command_is_linear_and_fast(tmp_path: Path) -> None:
    fasta = tmp_path / "sequence.fa"
    fasta.write_text(">sequence\nACGT\n")

    command = build_annotation_command(
        ["plannotate"], fasta, tmp_path / "out", "sequence-hash", fast=True, cores=3
    )

    assert command[-2:] == ["--linear", "--fast"]
    assert command[command.index("--cores") + 1] == "3"


def test_annotations_are_separate_provenance_linked_and_cached(tmp_path: Path) -> None:
    fasta = tmp_path / "sequence.fa"
    fasta.write_text(">sequence\nACGTACGT\n")
    output = tmp_path / "annotations"
    fake = FakePlannotate()

    def which(name: str) -> str | None:
        return "/usr/local/bin/plannotate" if name == "plannotate" else None

    first = annotate_with_plannotate(
        [fasta], output, cache_dir=tmp_path / "cache", run=fake, which=which
    )
    second = annotate_with_plannotate(
        [fasta], output, cache_dir=tmp_path / "cache", run=fake, which=which
    )
    refreshed = annotate_with_plannotate(
        [fasta],
        output,
        cache_dir=tmp_path / "cache",
        refresh=True,
        run=fake,
        which=which,
    )

    assert fasta.read_text() == ">sequence\nACGTACGT\n"
    assert first["policy"]["source_files_modified"] is False
    assert first["policy"]["outputs_are_enrichment_candidates"] is True
    assert first["results"][0]["status"] == "annotated"
    assert first["results"][0]["annotation_summary"]["exact_full_length_count"] == 1
    assert second["results"][0]["status"] == "cache-hit"
    assert refreshed["results"][0]["status"] == "annotated"
    assert sum("batch" in command for command in fake.commands) == 2
