from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

import opencem_sensitivity_suite as sensitivity


def _write_selection(tmp_path):
    selection_dir = tmp_path / "selection"
    selection_dir.mkdir()
    selected = pd.DataFrame({
        "method": ["CRMT"],
        "candidate_id": ["c1"],
        "base_soft_low": [0.30],
        "base_soft_high": [0.70],
        "prep_power_cap_frac": [0.10],
        "lookahead_gain": [0.01],
        "reserve_enter_margin": [0.02],
        "reserve_exit_margin": [0.01],
        "hold_decay": [0.60],
        "near_cap_forecast_buffer_frac": [0.05],
        "near_cap_soc_boost": [0.02],
    })
    selected_path = selection_dir / "selected_candidates.csv"
    selected.to_csv(selected_path, index=False, lineterminator="\n")
    digest = hashlib.sha256(selected_path.read_bytes()).hexdigest()
    lock = {
        "stage": "VALIDATION_SELECTION_LOCK",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "selection_rule_id": "validation-equal-weight-chebyshev-v1",
        "seed": 1001,
        "data_context": {"manifest_sha256": "manifest"},
        "selected_candidates_sha256": digest,
    }
    lock_path = selection_dir / "selection_lock.json"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    return selection_dir, digest


def test_primary_internal_evidence_must_match_selection_lock(tmp_path):
    selection_dir, selected_digest = _write_selection(tmp_path)
    primary = tmp_path / "primary"
    primary.mkdir()
    bad = {
        "stage": "ONE_SHOT_INTERNAL_TEST",
        "seed": 1001,
        "selection_lock_sha256": "wrong",
        "selected_candidates_sha256": selected_digest,
        "data_context": {"manifest_sha256": "manifest"},
    }
    (primary / "internal_test_run_summary.json").write_text(
        json.dumps(bad), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="different selection lock"):
        sensitivity.verify_primary_internal_test(
            primary,
            selection_dir=selection_dir,
            expected_manifest_sha256="manifest",
        )


def test_primary_internal_evidence_accepts_exact_selection_lock(tmp_path):
    selection_dir, selected_digest = _write_selection(tmp_path)
    lock_digest = hashlib.sha256(
        (selection_dir / "selection_lock.json").read_bytes()
    ).hexdigest()
    primary = tmp_path / "primary"
    primary.mkdir()
    good = {
        "stage": "ONE_SHOT_INTERNAL_TEST",
        "seed": 1001,
        "selection_lock_sha256": lock_digest,
        "selected_candidates_sha256": selected_digest,
        "data_context": {"manifest_sha256": "manifest"},
    }
    (primary / "internal_test_run_summary.json").write_text(
        json.dumps(good), encoding="utf-8"
    )
    out = sensitivity.verify_primary_internal_test(
        primary,
        selection_dir=selection_dir,
        expected_manifest_sha256="manifest",
    )
    assert out["stage"] == "ONE_SHOT_INTERNAL_TEST"
