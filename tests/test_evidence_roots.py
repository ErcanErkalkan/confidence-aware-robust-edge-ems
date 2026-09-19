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
