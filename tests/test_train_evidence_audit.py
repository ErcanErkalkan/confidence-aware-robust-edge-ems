from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import opencem_train_evidence_audit as audit
from crmt_edge_ems.protocol import (
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    CRMT_CANDIDATE_POOL_SIZE,
    METHOD_IDS,
    OPTIMIZER_SEEDS,
)


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_run(root: Path, method: str, seed: int, manifest_sha: str):
    d = root / f"{method}_seed{seed}"
    d.mkdir(parents=True)
    front = d / "optimizer_front.csv"
    ledger = d / "ledger.csv"
    cand_name = (
        "candidate_metrics.csv" if method == "CRMT"
        else "candidate_evaluations.csv"
    )
    cand = d / cand_name
    front_hash = _write(front, "candidate_id\nx\n")
    candidate_hash = _write(cand, "candidate_id\nx\n")
    ledger_frame = pd.DataFrame(
        {
            "ordinal": range(1, CONFIRMATORY_CONTROLLER_BLOCK_BUDGET + 1),
            "method_id": method,
            "candidate_id": "c",
            "block_id": "b",
            "unit": "controller_block_evaluation",
        }
    )
    ledger_frame.to_csv(ledger, index=False, lineterminator="\n")
    ledger_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()
    summary = {
        "stage": "TRAIN_OPTIMIZATION_ONLY",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "method": method,
        "seed": seed,
        "controller_block_budget": CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
        "ledger_used": CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
        "candidate_count": (
            CRMT_CANDIDATE_POOL_SIZE if method == "CRMT" else 60
        ),
        "data_context": {
            "manifest_sha256": manifest_sha,
            "train_block_count": 210,
        },
        "git_sha": "g",
        "files_sha256": {
            "optimizer_front.csv": front_hash,
            "ledger.csv": ledger_hash,
            cand_name: candidate_hash,
        },
    }
    (d / "run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )


def test_train_evidence_audit_accepts_complete_exact_design(tmp_path, monkeypatch):
    methods = ("SOBOL", "CRMT")
    seeds = (1001, 1002)
    monkeypatch.setattr(audit, "METHOD_IDS", methods)
    monkeypatch.setattr(audit, "OPTIMIZER_SEEDS", seeds)
    for method in methods:
        for seed in seeds:
            _make_run(tmp_path, method, seed, "manifest")
    frame, report = audit.audit_train_evidence(
        tmp_path, expected_manifest_sha256="manifest"
    )
    assert len(frame) == 4
    assert report["verified_runs"] == 4
    assert set(frame["ledger_rows"]) == {
        CONFIRMATORY_CONTROLLER_BLOCK_BUDGET
    }


def test_train_evidence_audit_fails_closed_on_tampered_ledger(tmp_path, monkeypatch):
    methods = ("SOBOL",)
    seeds = (1001,)
    monkeypatch.setattr(audit, "METHOD_IDS", methods)
    monkeypatch.setattr(audit, "OPTIMIZER_SEEDS", seeds)
    _make_run(tmp_path, "SOBOL", 1001, "manifest")
    ledger = tmp_path / "SOBOL_seed1001" / "ledger.csv"
    ledger.write_text("ordinal,method_id,candidate_id,block_id,unit\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ledger hash mismatch"):
        audit.audit_train_evidence(
            tmp_path, expected_manifest_sha256="manifest"
        )


def test_train_evidence_audit_accepts_frozen_split_block_count_schema(tmp_path, monkeypatch):
    import hashlib
    import json

    import numpy as np
    import pandas as pd

    import opencem_train_evidence_audit as audit

    monkeypatch.setattr(audit, "METHOD_IDS", ("SOBOL",))
    monkeypatch.setattr(audit, "OPTIMIZER_SEEDS", (1001,))
    monkeypatch.setattr(audit, "TRAIN_BLOCK_COUNT", 2)
    monkeypatch.setattr(audit, "CONFIRMATORY_CONTROLLER_BLOCK_BUDGET", 2)

    run_dir = tmp_path / "SOBOL_seed1001"
    run_dir.mkdir()
    front = run_dir / "optimizer_front.csv"
    ledger = run_dir / "ledger.csv"
    candidates = run_dir / "candidate_evaluations.csv"
    front.write_text("front_id\nSOBOL-front-0001\n", encoding="utf-8")
    pd.DataFrame(
        {
            "ordinal": [1, 2],
            "method_id": ["SOBOL", "SOBOL"],
            "candidate_id": ["c1", "c1"],
            "block_id": ["b1", "b2"],
            "unit": [
                "controller_block_evaluation",
                "controller_block_evaluation",
            ],
        }
    ).to_csv(ledger, index=False)
    candidates.write_text("candidate_id\nc1\n", encoding="utf-8")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    summary = {
        "stage": "TRAIN_OPTIMIZATION_ONLY",
        "protocol_version": audit.PROTOCOL_VERSION,
        "method": "SOBOL",
        "seed": 1001,
        "controller_block_budget": 2,
        "ledger_used": 2,
        "candidate_count": 60,
        "data_context": {
            "manifest_sha256": "manifest",
            "split": "train",
            "split_block_count": 2,
        },
        "files_sha256": {
            "optimizer_front.csv": sha(front),
            "ledger.csv": sha(ledger),
            "candidate_evaluations.csv": sha(candidates),
        },
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    frame, report = audit.audit_train_evidence(
        tmp_path, expected_manifest_sha256="manifest"
    )
    assert len(frame) == 1
    assert report["verified_runs"] == 1


def test_train_evidence_audit_rejects_conflicting_block_count_aliases(tmp_path, monkeypatch):
    import hashlib
    import json
    import pandas as pd
    import pytest

    import opencem_train_evidence_audit as audit

    monkeypatch.setattr(audit, "METHOD_IDS", ("SOBOL",))
    monkeypatch.setattr(audit, "OPTIMIZER_SEEDS", (1001,))
    monkeypatch.setattr(audit, "TRAIN_BLOCK_COUNT", 2)
    monkeypatch.setattr(audit, "CONFIRMATORY_CONTROLLER_BLOCK_BUDGET", 2)

    run_dir = tmp_path / "SOBOL_seed1001"
    run_dir.mkdir()
    front = run_dir / "optimizer_front.csv"
    ledger = run_dir / "ledger.csv"
    candidates = run_dir / "candidate_evaluations.csv"
    front.write_text("front_id\nSOBOL-front-0001\n", encoding="utf-8")
    pd.DataFrame(
        {
            "ordinal": [1, 2],
            "method_id": ["SOBOL", "SOBOL"],
            "candidate_id": ["c1", "c1"],
            "block_id": ["b1", "b2"],
            "unit": ["controller_block_evaluation"] * 2,
        }
    ).to_csv(ledger, index=False)
    candidates.write_text("candidate_id\nc1\n", encoding="utf-8")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    summary = {
        "stage": "TRAIN_OPTIMIZATION_ONLY",
        "protocol_version": audit.PROTOCOL_VERSION,
        "method": "SOBOL",
        "seed": 1001,
        "controller_block_budget": 2,
        "ledger_used": 2,
        "candidate_count": 60,
        "data_context": {
            "manifest_sha256": "manifest",
            "split": "train",
            "train_block_count": 2,
            "split_block_count": 3,
        },
        "files_sha256": {
            "optimizer_front.csv": sha(front),
            "ledger.csv": sha(ledger),
            "candidate_evaluations.csv": sha(candidates),
        },
    }
    (run_dir / "run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="inconsistent TRAIN block-count aliases"):
        audit.audit_train_evidence(
            tmp_path, expected_manifest_sha256="manifest"
        )
