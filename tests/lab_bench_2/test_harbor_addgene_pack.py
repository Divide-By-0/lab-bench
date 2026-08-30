"""Harbor packaging for the Addgene CloningQA subset."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lab_bench_2.cloning_simulators.rewards_v2 import cloning_reward_v2

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from package_addgene_harbor_tasks import (  # noqa: E402
    PACK,
    _task_dir_name,
    build_all,
    load_pack,
)


@pytest.fixture(scope="module")
def sample_task_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("harbor-addgene")
    built = build_all(dest, limit=1)
    assert len(built) == 1
    return built[0]


def test_harbor_task_has_required_layout(sample_task_dir: Path) -> None:
    questions, _reviews = load_pack()
    question_id = str(questions[0]["id"])
    assert sample_task_dir.name == _task_dir_name(question_id)
    assert (sample_task_dir / "instruction.md").is_file()
    assert (sample_task_dir / "task.toml").is_file()
    assert (sample_task_dir / "environment" / "Dockerfile").is_file()
    assert (sample_task_dir / "solution" / "solve.sh").is_file()
    assert (sample_task_dir / "solution" / "protocol.txt").is_file()
    assert (sample_task_dir / "tests" / "test.sh").is_file()
    assert (sample_task_dir / "tests" / "test_outputs.py").is_file()
    assert (sample_task_dir / "tests" / "reference.fa").is_file()
    gbks = list((sample_task_dir / "environment").glob("addgene-plasmid-*.gbk"))
    assert len(gbks) == 55
    toml = (sample_task_dir / "task.toml").read_text(encoding="utf-8")
    assert 'name = "ivy-research/' in toml
    assert "cloning_reward_v2" in toml
    assert 'network_mode = "no-network"' in toml
    instruction = (sample_task_dir / "instruction.md").read_text(encoding="utf-8")
    assert "/app/protocol.txt" in instruction
    assert "<protocol>" in instruction
    assert "assembled.fa" not in instruction


@pytest.mark.asyncio
async def test_harbor_oracle_protocol_scores_one(sample_task_dir: Path) -> None:
    protocol = (sample_task_dir / "solution" / "protocol.txt").read_text(
        encoding="utf-8"
    )
    score, reason = await cloning_reward_v2(
        answer=protocol,
        base_dir=PACK / "cloning" / "shared",
        reference_path=sample_task_dir / "tests" / "reference.fa",
        threshold=0.95,
    )
    assert score >= 1.0, reason


@pytest.mark.asyncio
async def test_harbor_wrong_protocol_scores_zero(sample_task_dir: Path) -> None:
    score, reason = await cloning_reward_v2(
        answer="<protocol>gibson(missing.gbk, also-missing.gbk)</protocol>",
        base_dir=PACK / "cloning" / "shared",
        reference_path=sample_task_dir / "tests" / "reference.fa",
        threshold=0.95,
    )
    assert score == 0.0
    assert "Execution failed" in reason or "Format invalid" in reason


@pytest.mark.asyncio
async def test_all_addgene_oracle_protocols_score_one() -> None:
    questions, _reviews = load_pack()
    inventory = PACK / "cloning" / "shared"
    failures: list[str] = []
    for question in questions:
        question_id = str(question["id"])
        protocol = (PACK / "canonical_protocols" / f"{question_id}.txt").read_text(
            encoding="utf-8"
        )
        score, reason = await cloning_reward_v2(
            answer=protocol,
            base_dir=inventory,
            reference_path=PACK / "validation" / f"{question_id}_assembled.fa",
            threshold=0.95,
        )
        if score < 1.0:
            failures.append(f"{question_id}: {reason}")
    assert failures == []
