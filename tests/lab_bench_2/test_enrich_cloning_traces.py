import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

import enrich_cloning_traces  # noqa: E402
import rescore_cloning_traces_v3  # noqa: E402


def test_question_ids_uses_effective_cache_and_reference_paths(tmp_path) -> None:
    available_id = "available"
    missing_id = "missing"
    cache_root = tmp_path / enrich_cloning_traces.GCS_BUCKET
    (cache_root / "cloning" / available_id).mkdir(parents=True)
    reference_dir = tmp_path / "references"
    reference_dir.mkdir()
    (reference_dir / f"{available_id}_assembled.fa").write_text(">reference\nACGT\n")
    log = SimpleNamespace(
        samples=[
            SimpleNamespace(
                metadata={
                    "tag": "cloning",
                    "id": available_id,
                    "files_path": "/stale/public/path",
                    "reference_path": "/stale/public/reference.fa",
                }
            ),
            SimpleNamespace(
                metadata={
                    "tag": "cloning",
                    "id": missing_id,
                }
            ),
        ]
    )

    assert enrich_cloning_traces._question_ids(
        log,
        tmp_path,
        reference_dir,
    ) == {missing_id}


def test_constraint_details_exposes_module_and_relationship_results() -> None:
    assessment = SimpleNamespace(
        modules=[
            SimpleNamespace(summary="payload: 5 complete copies (expected 5; pass)")
        ],
        relationships=[
            SimpleNamespace(detail="ordered modules promoter -> payload", passes=True)
        ],
    )
    report = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                constraint_assessment=assessment,
                passes=True,
                simulator_index=0,
            )
        ]
    )

    detail = rescore_cloning_traces_v3._constraint_details(report)

    assert "payload: 5 complete copies (expected 5; pass)" in detail
    assert "ordered modules promoter -> payload (pass)" in detail
    assert "pLannotate calls are fallback annotation evidence only" in detail


def test_v3_rescore_records_the_pydna_simulator_pipeline() -> None:
    manifest = rescore_cloning_traces_v3._simulator_manifest()

    assert manifest["molecular_engine"] == "pydna"
    assert manifest["pydna_version"]
    assert manifest["protocol_executor"].endswith("execute_cloning_protocol_v2")
    assert set(manifest["operations"]) == {
        "pcr",
        "gibson",
        "golden_gate",
        "restriction_ligation",
    }
