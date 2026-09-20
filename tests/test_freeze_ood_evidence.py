import hashlib
import json
from pathlib import Path

from tools.freeze_ood_evidence import (
    INDEX_NAME,
    LOCK_NAME,
    SHA_NAME,
    freeze_ood,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_ood(root: Path) -> None:
    payloads = {
        "ood_block_metrics.csv": "x\n" + "1\n" * 16560,
        "ood_stratum_risk_summary.csv": "x\n" + "1\n" * 30,
        "ood_macro_risk_summary.csv": "x\n" + "1\n" * 5,
        "ood_pooled_risk_summary.csv": "x\n" + "1\n" * 5,
    }
    for seed in range(1001, 1031):
        d = root / f"opsd_ood_seed{seed}"
        d.mkdir(parents=True)
        for name, payload in payloads.items():
            (d / name).write_text(payload, encoding="utf-8")
        summary = {
            "stage": "EXTERNAL_OOD_OPSD_FROZEN_SELECTION",
            "protocol_version": "opencem-confirmatory-prelock-v1",
            "seed": seed,
            "selection_lock_sha256": "a" * 64,
            "selected_candidates_sha256": "b" * 64,
            "primary_internal_test_summary_sha256": "c" * 64,
            "source_context": {
                "package_sha256": "17c41c778bf8ce9a6e483c179664afc66af2e5eddda869e359c719fc037013b3",
                "full_replay_manifest_sha256": "7e6137adf98a4b5c604fd047891297458b0a2dc606e32f2e8b9e3dba562bea1d",
                "full_replay_manifest_rows": 1656,
                "target_site_ids": [1, 2],
                "ood_block_count": 3312,
            },
            "files_sha256": {
                name: _sha(d / name) for name in payloads
            },
        }
        (d / "ood_run_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )


def test_freeze_ood_is_complete_and_deterministic(tmp_path):
    evidence = tmp_path / "evidence"
    _build_ood(evidence)
    out1 = tmp_path / "freeze1"
    out2 = tmp_path / "freeze2"
    first = freeze_ood(evidence, out1, 1)
    second = freeze_ood(evidence, out2, 1)

    assert first["records"] == 30
    assert first["ood_root_sha256"] == second["ood_root_sha256"]
    assert first["master_lock_sha256"] == second["master_lock_sha256"]
    assert (out1 / INDEX_NAME).read_bytes() == (out2 / INDEX_NAME).read_bytes()
    assert (out1 / LOCK_NAME).read_bytes() == (out2 / LOCK_NAME).read_bytes()
    assert (out1 / SHA_NAME).read_bytes() == (out2 / SHA_NAME).read_bytes()
