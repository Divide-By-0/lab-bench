#!/usr/bin/env python3
"""Build Harbor-format CloningQA tasks from the Addgene subset pack.

Each output directory is a Harbor task (instruction.md, task.toml,
environment/, solution/, tests/). DataVendor accepts a zip of these
directories as a Harbor taskset.

The verifier is cloning simulator v2 (pydna + edlib, circular
similarity ≥ 0.95), matching Inspect ``cloning_scorer``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
from pathlib import Path

from lab_bench_2.prompt_composer import (
    CLONING_PROTOCOL_SUFFIX,
    FILE_REFERENCE_INSTRUCTION,
)

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "experiments" / "cloning_addgene_subset_v1"
SIMULATORS = ROOT / "src" / "lab_bench_2" / "cloning_simulators"


def _labbench2_cloning() -> Path:
    import labbench2

    cloning = Path(labbench2.__file__).resolve().parent / "cloning"
    if not cloning.is_dir():
        raise FileNotFoundError(
            f"labbench2 cloning package not found at {cloning}. "
            "Run `uv sync --extra lab_bench_2` first."
        )
    return cloning

SIMULATOR_FILES = (
    "execution.py",
    "gibson_v2.py",
    "golden_gate_v2.py",
    "molecular.py",
    "pcr_v2.py",
    "restriction_v2.py",
    "rewards_v2.py",
    "sequence_similarity_v2.py",
)
LABBENCH2_FILES = (
    "cloning_protocol.py",
    "enzyme_cut.py",
    "gibson.py",
    "goldengate.py",
    "restriction_enzyme.py",
    "sequence_models.py",
    "simulate_pcr.py",
    "utils.py",
    "sequence_alignment.py",
    "rewards.py",
)

DOCKERFILE = """FROM python:3.12-slim-bookworm

# REASON: edlib and primer3-py ship as source on some platforms; gcc/make
# and Python headers are required at image build. primer3-py 2.3.0 fails on
# aarch64 without `make` (missing amplicon3_core). Purging the toolchain
# afterwards keeps the agent image smaller. Removing edlib reintroduces the
# host scoring hole that recorded finished iGABASnFR protocols as errors.
RUN apt-get update && apt-get install -y --no-install-recommends \\
        gcc g++ make python3-dev \\
    && pip install --no-cache-dir \\
        biopython==1.87 \\
        pydna==5.5.12 \\
        primer3-py==2.3.0 \\
        numpy==2.4.6 \\
        pandas==3.0.3 \\
        scipy==1.17.1 \\
        edlib==1.3.9.post1 \\
        pytest==8.4.1 \\
    && apt-get purge -y gcc g++ make python3-dev \\
    && apt-get autoremove -y \\
    && rm -rf /var/lib/apt/lists/*

COPY . /app
WORKDIR /app
"""

SOLVE_SH = """#!/bin/bash
set -euo pipefail
cp /solution/protocol.txt /app/protocol.txt
"""

TEST_SH = """#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
set +e
python -m pytest /tests/test_outputs.py -rA
status=$?
set -e
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$status"
"""

TEST_OUTPUTS = '''"""Harbor verifier: execute /app/protocol.txt against the hidden circle."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))

from lab_bench_2.cloning_simulators.rewards_v2 import cloning_reward_v2

PROTOCOL_PATH = Path("/app/protocol.txt")
INVENTORY_DIR = Path("/app")
REFERENCE_PATH = Path("/tests/reference.fa")


def test_protocol_matches_hidden_circle() -> None:
    assert PROTOCOL_PATH.is_file(), "Agent must write /app/protocol.txt"
    score, reason = asyncio.run(
        cloning_reward_v2(
            answer=PROTOCOL_PATH.read_text(encoding="utf-8"),
            base_dir=INVENTORY_DIR,
            reference_path=REFERENCE_PATH,
            threshold=0.95,
        )
    )
    assert score >= 1.0, reason
'''

HARBOR_INSTRUCTION_FOOTER = """
Working directory is `/app`. The Addgene GenBank inventory and `enzyme_inventory.tsv` are already in that directory. Refer to sequence files by basename only (for example `addgene-plasmid-104588-sequence-200932.gbk`).

Write your final protocol to `/app/protocol.txt` as a single `<protocol>...</protocol>` expression. Do not write the hidden assembled FASTA; the verifier executes the protocol.
"""


def _task_dir_name(question_id: str) -> str:
    return f"addgene-{question_id[:8]}"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _copy_vendor(dest: Path) -> None:
    lab_root = dest / "lab_bench_2"
    sim_root = lab_root / "cloning_simulators"
    bench_root = dest / "labbench2"
    cloning_root = bench_root / "cloning"
    sim_root.mkdir(parents=True, exist_ok=True)
    cloning_root.mkdir(parents=True, exist_ok=True)
    (lab_root / "__init__.py").write_text("", encoding="utf-8")
    (sim_root / "__init__.py").write_text("", encoding="utf-8")
    (bench_root / "__init__.py").write_text(
        '__version__ = "0.1.0"\n', encoding="utf-8"
    )
    (cloning_root / "__init__.py").write_text("", encoding="utf-8")
    for name in SIMULATOR_FILES:
        shutil.copy2(SIMULATORS / name, sim_root / name)
    cloning_src = _labbench2_cloning()
    for name in LABBENCH2_FILES:
        src = cloning_src / name
        if src.is_file():
            shutil.copy2(src, cloning_root / name)


def _task_toml(
    *,
    name: str,
    description: str,
    catalog_method: str,
    addgene_id: int,
    question_id: str,
) -> str:
    return f"""schema_version = "1.3"
artifacts = []

[task]
name = "{name}"
description = {description!r}
keywords = ["cloning", "synthetic-biology", "addgene", "gibson", "{catalog_method}"]
[[task.authors]]
name = "Aayush Gupta"
email = "aayushgupta05@gmail.com"

[metadata]
org = "ivy-research"
pack = "addgene-subset-v1"
question_id = "{question_id}"
addgene_id = "{addgene_id}"
catalog_method = "{catalog_method}"
scorer = "cloning_reward_v2"
similarity_threshold = "0.95"

[verifier]
timeout_sec = 600.0
collect = []

[verifier.env]

[agent]
timeout_sec = 7200.0

[environment]
network_mode = "no-network"
build_timeout_sec = 1200.0
os = "linux"
mcp_servers = []

[environment.env]

[solution.env]
"""


def _instruction(question: dict[str, object]) -> str:
    text = str(question["question"])
    suffix = str(question.get("prompt_suffix") or CLONING_PROTOCOL_SUFFIX)
    return (
        text
        + FILE_REFERENCE_INSTRUCTION
        + "\n\n"
        + suffix
        + "\n"
        + HARBOR_INSTRUCTION_FOOTER
    )


def build_task(
    question: dict[str, object],
    review: dict[str, object],
    dest: Path,
) -> Path:
    question_id = str(question["id"])
    task_name = f"ivy-research/{_task_dir_name(question_id)}"
    task_dir = dest / _task_dir_name(question_id)
    if task_dir.exists():
        shutil.rmtree(task_dir)
    env = task_dir / "environment"
    tests = task_dir / "tests"
    solution = task_dir / "solution"
    env.mkdir(parents=True)
    tests.mkdir(parents=True)
    solution.mkdir(parents=True)

    inventory = PACK / "cloning" / "shared"
    for gbk in inventory.glob("addgene-plasmid-*.gbk"):
        shutil.copy2(gbk, env / gbk.name)
    shutil.copy2(inventory / "enzyme_inventory.tsv", env / "enzyme_inventory.tsv")
    (env / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")

    description = (
        f"Replace {review['replace_cds']} on {review['backbone_name']} "
        f"(Addgene {review['backbone_addgene_id']}) with {review['donor_cds']} "
        "from the shared inventory."
    )
    (task_dir / "task.toml").write_text(
        _task_toml(
            name=task_name,
            description=description,
            catalog_method=str(review["catalog_method"]),
            addgene_id=int(review["backbone_addgene_id"]),
            question_id=question_id,
        ),
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text(
        _instruction(question), encoding="utf-8"
    )
    (task_dir / "README.md").write_text(
        f"# {task_name}\n\n{description}\n", encoding="utf-8"
    )

    protocol = (PACK / "canonical_protocols" / f"{question_id}.txt").read_text(
        encoding="utf-8"
    )
    (solution / "protocol.txt").write_text(protocol, encoding="utf-8")
    _write_executable(solution / "solve.sh", SOLVE_SH)

    shutil.copy2(
        PACK / "validation" / f"{question_id}_assembled.fa",
        tests / "reference.fa",
    )
    (tests / "test_outputs.py").write_text(TEST_OUTPUTS, encoding="utf-8")
    _write_executable(tests / "test.sh", TEST_SH)
    _copy_vendor(tests / "vendor")
    return task_dir


def load_pack() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    questions = [
        json.loads(line)
        for line in (PACK / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reviews = json.loads((PACK / "reviews.json").read_text(encoding="utf-8"))
    return questions, reviews


def build_all(dest: Path, limit: int | None = None) -> list[Path]:
    questions, reviews = load_pack()
    reviews_by_id = {str(item["id"]): item for item in reviews}
    dest.mkdir(parents=True, exist_ok=True)
    built: list[Path] = []
    for question in questions[: limit or None]:
        review = reviews_by_id[str(question["id"])]
        built.append(build_task(question, review, dest))
    return built


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "experiments" / "harbor_addgene_subset_v1" / "tasks",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    built = build_all(args.output_dir, limit=args.limit)
    print(f"built {len(built)} Harbor tasks under {args.output_dir}")


if __name__ == "__main__":
    main()
