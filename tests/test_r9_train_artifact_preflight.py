"""Synthetic fail-closed tests; never uses experimental OpenCEM TEST data."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from r9_equal_capacity_20261023.r9_train_artifact_preflight import (
    OBJECTIVES, SOURCE_SHA, OPENCEM_SHA, SOURCE_MANIFEST_SHA,
    PreflightBlocked, inspect_pair, inspect_all,
)


def _csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cell(root, f, *, seed=1001, c=1, a=0):
    name = "C%d_F%d_A%d" % (c, f, a)
    path = root / ("seed%d" % seed) / name
    path.mkdir(parents=True, exist_ok=True)
    events = [("c1", "b1"), ("c1", "b2"), ("c2", "b1"), ("c2", "b2")]
    _csv(path / "ledger.csv",
         ["ordinal", "method_id", "candidate_id", "block_id", "unit"],
         [[n, "CRMT", cid, bid, "controller_block_evaluation"]
          for n, (cid, bid) in enumerate(events, 1)])
    _csv(path / "candidate_metrics.csv",
         ["candidate_id", "block_id", "split", *OBJECTIVES],
         [[cid, bid, "train", 0.1 if cid == "c1" else 0.3,
           0.2, 0.7, 1.5] for cid, bid in events])
    _csv(path / "optimizer_front.csv", ["candidate_id"], [["c1"]])
    summary = {
        "stage": "GATE3_FACTORIAL_TRAIN_ONLY",
        "seed": seed, "condition_id": name, "status": "EXPLORATORY",
        "source_repo": "ErcanErkalkan/confidence-aware-robust-edge-ems",
        "original_git_sha": SOURCE_SHA,
        "source_data_commit": OPENCEM_SHA,
        "canonical_manifest_sha256": SOURCE_MANIFEST_SHA,
        "source_context": {"split": "train"},
        "candidate_count": 2, "train_budget_used": 4,
        "archive_count": 1, "risk_q": 0.9,
        "risk_tail_weight": 0.5 if c else 0.0,
        "archive_mode": "confidence" if f else "risk_pareto",
        "allocation_mode": "adaptive" if a else "round_robin",
        "files_sha256": {
            n: _sha(path / n) for n in
            ("ledger.csv", "candidate_metrics.csv", "optimizer_front.csv")
        },
    }
    (path / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return path


def _signed_edit(folder, file_name, editor):
    file = folder / file_name
    editor(file)
    summary = json.loads((folder / "run_summary.json").read_text())
    summary["files_sha256"][file_name] = _sha(file)
    (folder / "run_summary.json").write_text(json.dumps(summary))


def _pair(tmp_path):
    _cell(tmp_path, 0)
    _cell(tmp_path, 1)
    return tmp_path


def test_realistic_synthetic_pair_passes(tmp_path):
    root = _pair(tmp_path)
    result = inspect_pair(root, 1001, 1, 0, budget=4, pool=2)
    assert result["matched_train_event_count"] == 4
    assert result["scientific_four_objective_mismatch_count"] == 0
    assert result["F0_archive_size"] == result["F1_archive_size"] == 1
    assert result["status"] == "VERIFIED_HISTORICAL_TRAIN_ONLY_NOT_R9_TEST"


def test_absent_files_block(tmp_path):
    root = _pair(tmp_path)
    (root / "seed1001/C1_F0_A0/ledger.csv").unlink()
    with pytest.raises(PreflightBlocked, match="missing or empty"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_tampered_csv_digest_blocks(tmp_path):
    root = _pair(tmp_path)
    f0 = root / "seed1001/C1_F0_A0"
    with (f0 / "candidate_metrics.csv").open("a") as f:
        f.write("unexpected-row\n")
    with pytest.raises(PreflightBlocked, match="SHA256 mismatch"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_signed_test_split_is_still_blocked(tmp_path):
    root = _pair(tmp_path)
    f0 = root / "seed1001/C1_F0_A0"
    _signed_edit(f0, "candidate_metrics.csv",
                 lambda p: p.write_text(p.read_text().replace(",train,", ",test,")))
    with pytest.raises(PreflightBlocked, match="TEST/VAL row"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_signed_objective_drift_blocks(tmp_path):
    root = _pair(tmp_path)
    f1 = root / "seed1001/C1_F1_A0"
    _signed_edit(f1, "candidate_metrics.csv",
                 lambda p: p.write_text(p.read_text().replace(",0.1,0.2,", ",0.12,0.2,")))
    with pytest.raises(PreflightBlocked, match="objective rows differ"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_wrong_risk_factor_blocks(tmp_path):
    root = _pair(tmp_path)
    f1 = root / "seed1001/C1_F1_A0/run_summary.json"
    j = json.loads(f1.read_text())
    j["risk_tail_weight"] = 0.0
    f1.write_text(json.dumps(j))
    with pytest.raises(PreflightBlocked, match="risk lambda mismatch"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_duplicate_metrics_signed_blocks(tmp_path):
    root = _pair(tmp_path)
    f1 = root / "seed1001/C1_F1_A0"
    def edit(p):
        lines = p.read_text().splitlines()
        lines[-1] = lines[-2]
        p.write_text("\n".join(lines) + "\n")
    _signed_edit(f1, "candidate_metrics.csv", edit)
    with pytest.raises(PreflightBlocked, match="duplicate metric event"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_signed_unknown_archive_member_blocks(tmp_path):
    root = _pair(tmp_path)
    f0 = root / "seed1001/C1_F0_A0"
    _signed_edit(f0, "optimizer_front.csv",
                 lambda p: p.write_text("candidate_id\nnot_in_pool\n"))
    with pytest.raises(PreflightBlocked, match="outside TRAIN pool"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)


def test_full_audit_refuses_partial_data(tmp_path):
    root = _pair(tmp_path)
    with pytest.raises(PreflightBlocked, match="missing"):
        inspect_all(root)


def test_signed_evaluation_budget_tamper_blocks(tmp_path):
    root = _pair(tmp_path)
    f0 = root / "seed1001/C1_F0_A0/run_summary.json"
    j = json.loads(f0.read_text())
    j["train_budget_used"] = 3
    f0.write_text(json.dumps(j))
    with pytest.raises(PreflightBlocked, match="train_budget_used mismatch"):
        inspect_pair(root, 1001, 1, 0, budget=4, pool=2)
