import hashlib
import json
from pathlib import Path

import pytest

from tools.evidence_roots import compute_evidence_root


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_validation(root: Path):
    for seed in range(1001, 1031):
        d = root / f"validation_selection_seed{seed}"
        d.mkdir(parents=True)
        selected = d / "selected_candidates.csv"
        selected.write_text("method,candidate_id\nCRMT,c1\n", encoding="utf-8")
        lock = {
            "stage": "VALIDATION_SELECTION_LOCK",
            "seed": seed,
            "selected_candidates_sha256": _sha(selected),
            "files_sha256": {"selected_candidates.csv": _sha(selected)},
        }
        (d / "selection_lock.json").write_text(json.dumps(lock), encoding="utf-8")


def test_validation_root_is_deterministic(tmp_path):
    _build_validation(tmp_path)
    first = compute_evidence_root("validation", tmp_path)
    second = compute_evidence_root("validation", tmp_path)
    assert first == second
    assert first["records"] == 30
    assert len(first["root_sha256"]) == 64


def test_validation_root_fails_closed_on_tamper(tmp_path):
    _build_validation(tmp_path)
    target = tmp_path / "validation_selection_seed1010" / "selected_candidates.csv"
    target.write_text("method,candidate_id\nCRMT,TAMPERED\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="selected-candidate hash mismatch|hash mismatch"):
        compute_evidence_root("validation", tmp_path)


def test_validation_root_rejects_duplicate_evidence(tmp_path):
    _build_validation(tmp_path)
    original = tmp_path / "validation_selection_seed1001"
    nested = tmp_path / "extra" / "validation_selection_seed1001"
    nested.mkdir(parents=True)
    for name in ("selection_lock.json", "selected_candidates.csv"):
        (nested / name).write_bytes((original / name).read_bytes())
    for name in ("selection_lock.json", "selected_candidates.csv"):
        (original / name).unlink()
    duplicate2 = tmp_path / "extra2" / "validation_selection_seed1001"
    duplicate2.mkdir(parents=True)
    for name in ("selection_lock.json", "selected_candidates.csv"):
        (duplicate2 / name).write_bytes((nested / name).read_bytes())
    with pytest.raises(RuntimeError, match="expected exactly one evidence directory"):
        compute_evidence_root("validation", tmp_path)


def _build_ablation_train(root: Path):
    for ablation in ("NO_CVAR", "NO_CONFIDENCE", "NO_ADAPTIVE"):
        for seed in range(1001, 1031):
            d = root / f"{ablation}_seed{seed}"
            d.mkdir(parents=True)
            for name, content in (
                ("candidate_metrics.csv", "candidate_id,value\nc1,1\n"),
                ("optimizer_front.csv", "candidate_id,obj\nc1,1\n"),
                ("ledger.csv", "candidate_id,block_id\nc1,b1\n"),
            ):
                (d / name).write_text(content, encoding="utf-8")
            files_sha256 = {
                name: _sha(d / name)
                for name in ("candidate_metrics.csv", "optimizer_front.csv", "ledger.csv")
            }
            summary = {
                "stage": "CRMT_ABLATION_TRAIN_ONLY",
                "ablation_id": ablation,
                "seed": seed,
                "controller_block_budget": 12600,
                "ledger_used": 12600,
                "git_sha": "128c6d3be06d9efd7921f903065bc727ac1d7440",
                "data_context": {
                    "manifest_sha256": "3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1",
                    "split": "train",
                    "split_block_count": 210,
                },
                "files_sha256": files_sha256,
            }
            (d / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_ablation_train_root_verifies_exact_90_records(tmp_path):
    _build_ablation_train(tmp_path)
    result = compute_evidence_root("ablation_train", tmp_path)
    assert result["records"] == 90
    assert len(result["root_sha256"]) == 64


def test_ablation_train_root_fails_on_wrong_budget(tmp_path):
    _build_ablation_train(tmp_path)
    path = tmp_path / "NO_CVAR_seed1001" / "run_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["controller_block_budget"] = 12599
    summary["ledger_used"] = 12599
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(RuntimeError, match="budget mismatch"):
        compute_evidence_root("ablation_train", tmp_path)


def test_ablation_train_root_fails_on_missing_required_hash(tmp_path):
    _build_ablation_train(tmp_path)
    path = tmp_path / "NO_CVAR_seed1001" / "run_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["files_sha256"].pop("optimizer_front.csv")
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing required file hashes"):
        compute_evidence_root("ablation_train", tmp_path)


def _build_sensitivity(root: Path):
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


def test_sensitivity_root_verifies_exact_30_seed_design(tmp_path):
    _build_sensitivity(tmp_path)
    result = compute_evidence_root("sensitivity", tmp_path)
    assert result["records"] == 30
    assert len(result["root_sha256"]) == 64


def test_sensitivity_root_fails_on_variant_drift(tmp_path):
    _build_sensitivity(tmp_path)
    path = tmp_path / "sensitivity_seed1001" / "sensitivity_run_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["variant_ids"][0] = "UNDECLARED_VARIANT"
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(RuntimeError, match="variant set/order mismatch"):
        compute_evidence_root("sensitivity", tmp_path)


def test_sensitivity_root_fails_on_row_count_drift(tmp_path):
    _build_sensitivity(tmp_path)
    path = tmp_path / "sensitivity_seed1001" / "sensitivity_risk_summary.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    summary_path = tmp_path / "sensitivity_seed1001" / "sensitivity_run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["files_sha256"]["sensitivity_risk_summary.csv"] = _sha(path)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(RuntimeError, match="row-count mismatch"):
        compute_evidence_root("sensitivity", tmp_path)


def _build_ood(root: Path):
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


def test_ood_root_verifies_exact_30_seed_design(tmp_path):
    _build_ood(tmp_path)
    result = compute_evidence_root("ood", tmp_path)
    assert result["records"] == 30
    assert len(result["root_sha256"]) == 64


def test_ood_root_fails_on_locked_package_drift(tmp_path):
    _build_ood(tmp_path)
    path = tmp_path / "opsd_ood_seed1001" / "ood_run_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["source_context"]["package_sha256"] = "0" * 64
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(RuntimeError, match="package hash mismatch"):
        compute_evidence_root("ood", tmp_path)
