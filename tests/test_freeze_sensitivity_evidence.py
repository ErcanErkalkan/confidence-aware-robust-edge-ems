import hashlib
import json
from pathlib import Path

from tools.freeze_sensitivity_evidence import (
    INDEX_NAME,
    LOCK_NAME,
    SHA_NAME,
    freeze_sensitivity,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_sensitivity(root: Path) -> None:
    variants = [
        "ETA_LOW_090",
        "ETA_IDEAL_100",
        "SOC_CONSERVATIVE_15_95",
        "RAMP_HALF",
        "RAMP_QUARTER",
        "TEMPORAL_FLOOR",
    ]
    block_payload = "variant_id,method,candidate_id,block_id\n" + "".join(
        f"{variants[i % 6]},CRMT,c1,b{i}\n" for i in range(2340)
    )
    risk_payload = "variant_id,method,candidate_id,value\n" + "".join(
        f"{variants[i % 6]},CRMT,c1,1\n" for i in range(30)
    )
    for seed in range(1001, 1031):
        d = root / f"sensitivity_seed{seed}"
        d.mkdir(parents=True)
        (d / "sensitivity_block_metrics.csv").write_text(block_payload, encoding="utf-8")
        (d / "sensitivity_risk_summary.csv").write_text(risk_payload, encoding="utf-8")
        summary = {
            "stage": "PREDECLARED_SITE_TEMPORAL_SENSITIVITY",
            "seed": seed,
            "variant_ids": variants,
            "selection_lock_sha256": "a" * 64,
            "selected_candidates_sha256": "b" * 64,
            "primary_internal_test_summary_sha256": "c" * 64,
            "primary_internal_test_stage": "ONE_SHOT_INTERNAL_TEST",
            "data_context": {
                "manifest_sha256": "3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1",
                "split": "internal_test",
                "split_block_count": 78,
            },
            "files_sha256": {
                "sensitivity_block_metrics.csv": _sha(d / "sensitivity_block_metrics.csv"),
                "sensitivity_risk_summary.csv": _sha(d / "sensitivity_risk_summary.csv"),
            },
        }
        (d / "sensitivity_run_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )


def test_freeze_sensitivity_is_complete_and_deterministic(tmp_path):
    evidence = tmp_path / "evidence"
    _build_sensitivity(evidence)
    out1 = tmp_path / "freeze1"
    out2 = tmp_path / "freeze2"
    first = freeze_sensitivity(evidence, out1, 35490232146)
    second = freeze_sensitivity(evidence, out2, 35490232146)

    assert first["records"] == 30
    assert first["sensitivity_root_sha256"] == second["sensitivity_root_sha256"]
    assert first["master_lock_sha256"] == second["master_lock_sha256"]
    assert (out1 / INDEX_NAME).read_bytes() == (out2 / INDEX_NAME).read_bytes()
    assert (out1 / LOCK_NAME).read_bytes() == (out2 / LOCK_NAME).read_bytes()
    assert (out1 / SHA_NAME).read_bytes() == (out2 / SHA_NAME).read_bytes()
