from __future__ import annotations

import hashlib
import json

import pandas as pd

from crmt_edge_ems.protocol import METHOD_IDS
from crmt_edge_ems.risk import DEFAULT_OBJECTIVES
import opencem_confirmatory_report as report


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_seed(root_v, root_i, seed):
    vd = root_v / f"validation_selection_seed{seed}"
    idr = root_i / f"internal_test_seed{seed}"
    vd.mkdir(parents=True)
    idr.mkdir(parents=True)

    rows = []
    selected_rows = []
    for mi, method in enumerate(METHOD_IDS):
        for ci in range(2):
            row = {
                "method": method,
                "candidate_id": f"{method}-c{ci}",
                "cap_violation_pct_total": float(mi + ci + seed * 0.01),
                "lfp_cycle_loss_pct": float(2 * mi + ci + 1),
                "ramp95_kw_per_min": float(10 + mi - ci),
                "flip_per_day": float(5 + mi + ci),
            }
            rows.append(row)
        selected_rows.append({
            "method": method,
            "candidate_id": f"{method}-c0",
        })
    scores = pd.DataFrame(rows)
    scores_path = vd / "validation_candidate_scores.csv"
    scores.to_csv(scores_path, index=False, lineterminator="\n")
    selected = pd.DataFrame(selected_rows)
    selected_path = vd / "selected_candidates.csv"
    selected.to_csv(selected_path, index=False, lineterminator="\n")

    lock = {
        "stage": "VALIDATION_SELECTION_LOCK",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "seed": seed,
        "data_context": {"manifest_sha256": "manifest"},
        "files_sha256": {
            "validation_candidate_scores.csv": _sha(scores_path),
        },
        "selected_candidates_sha256": _sha(selected_path),
    }
    lock_path = vd / "selection_lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    internal_rows = []
    for mi, method in enumerate(METHOD_IDS):
        internal_rows.append({
            "method": method,
            "candidate_id": f"{method}-c0",
            "cap_violation_pct_total": float(mi + seed * 0.02),
            "lfp_cycle_loss_pct": float(1 + mi + seed * 0.01),
            "ramp95_kw_per_min": float(9 + mi + seed * 0.01),
            "flip_per_day": float(4 + mi + seed * 0.01),
        })
    internal = pd.DataFrame(internal_rows)
    risk_path = idr / "internal_test_risk_summary.csv"
    internal.to_csv(risk_path, index=False, lineterminator="\n")
    internal_summary = {
        "stage": "ONE_SHOT_INTERNAL_TEST",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "seed": seed,
        "selection_lock_sha256": _sha(lock_path),
        "selected_candidates_sha256": _sha(selected_path),
        "data_context": {"manifest_sha256": "manifest"},
        "files_sha256": {
            "internal_test_risk_summary.csv": _sha(risk_path),
        },
    }
    (idr / "internal_test_run_summary.json").write_text(
        json.dumps(internal_summary),
        encoding="utf-8",
    )


def test_confirmatory_report_builds_all_prelocked_tables(tmp_path, monkeypatch):
    validation_root = tmp_path / "validation"
    internal_root = tmp_path / "internal"
    for seed in range(1, 6):
        _make_seed(validation_root, internal_root, seed)

    # Keep unit test fast while preserving the production method path.
    monkeypatch.setattr(report, "STATISTICAL_BOOTSTRAP_DRAWS", 1000)
    out = tmp_path / "report"
    summary = report.build_confirmatory_report(
        validation_root=validation_root,
        internal_root=internal_root,
        output_dir=out,
        seeds=range(1, 6),
    )
    assert summary["stage"] == "CONFIRMATORY_STATISTICAL_REPORT"
    expected = {
        "internal_seed_metrics.csv",
        "internal_descriptive.csv",
        "internal_friedman.csv",
        "internal_pairwise_wilcoxon_holm.csv",
        "optimizer_quality_seed.csv",
        "optimizer_quality_descriptive.csv",
        "optimizer_quality_friedman.csv",
        "optimizer_quality_pairwise_wilcoxon_holm.csv",
    }
    assert expected == set(summary["files_sha256"])
    for name in expected:
        assert (out / name).is_file()
