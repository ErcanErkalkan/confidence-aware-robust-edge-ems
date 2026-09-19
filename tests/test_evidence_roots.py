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
