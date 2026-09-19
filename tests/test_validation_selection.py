from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.protocol import METHOD_IDS
from crmt_edge_ems.selection import score_validation_candidates, select_one_per_method
import opencem_internal_test as internal


OBJECTIVES = (
    "cap_violation_pct_total",
    "lfp_cycle_loss_pct",
    "ramp95_kw_per_min",
    "flip_per_day",
)


def test_common_validation_normalization_and_chebyshev_selection():
    rows = []
    for method, vals in {
        "A": [(1, 9, 5, 4), (4, 4, 4, 4)],
        "B": [(9, 1, 5, 4), (5, 5, 3, 3)],
    }.items():
        for i, values in enumerate(vals):
            rows.append(
                {"method": method, "candidate_id": f"{method}{i}", **dict(zip(OBJECTIVES, values))}
            )
    scored, refs = score_validation_candidates(pd.DataFrame(rows), objectives=OBJECTIVES)
    selected = select_one_per_method(scored)
    assert set(selected["method"]) == {"A", "B"}
    assert refs["cap_violation_pct_total"]["ideal"] == 1.0
    assert refs["cap_violation_pct_total"]["observed_worst"] == 9.0
    assert np.isfinite(scored["normalized_linf"]).all()
    assert np.isfinite(scored["normalized_l1"]).all()


def test_degenerate_validation_objective_contributes_zero():
    df = pd.DataFrame(
        {
            "method": ["A", "B"],
            "candidate_id": ["a", "b"],
            "o1": [1.0, 2.0],
            "o2": [7.0, 7.0],
        }
    )
    scored, refs = score_validation_candidates(df, objectives=("o1", "o2"))
    assert refs["o2"]["degenerate"] is True
    assert np.allclose(scored["norm__o2"], 0.0)


def test_selection_ties_are_deterministic_by_candidate_id():
    df = pd.DataFrame(
        {
            "method": ["A", "A"],
            "candidate_id": ["z", "a"],
            "normalized_linf": [0.5, 0.5],
            "normalized_l1": [1.0, 1.0],
        }
    )
    out = select_one_per_method(df)
    assert out.iloc[0]["candidate_id"] == "a"


def test_internal_test_rejects_modified_selected_candidate_csv(tmp_path):
    selected = pd.DataFrame(
        {
            "method": list(METHOD_IDS),
            "candidate_id": [f"c{i}" for i in range(len(METHOD_IDS))],
            "base_soft_low": 0.3,
            "base_soft_high": 0.7,
            "prep_power_cap_frac": 0.1,
            "lookahead_gain": 0.01,
            "reserve_enter_margin": 0.02,
            "reserve_exit_margin": 0.01,
            "hold_decay": 0.6,
            "near_cap_forecast_buffer_frac": 0.05,
            "near_cap_soc_boost": 0.02,
        }
    )
    selected_path = tmp_path / "selected_candidates.csv"
    selected.to_csv(selected_path, index=False, lineterminator="\n")
    import hashlib
    digest = hashlib.sha256(selected_path.read_bytes()).hexdigest()
    lock = {
        "stage": "VALIDATION_SELECTION_LOCK",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "selection_rule_id": "validation-equal-weight-chebyshev-v1",
        "seed": 1001,
        "data_context": {"manifest_sha256": "abc"},
        "selected_candidates_sha256": digest,
    }
    (tmp_path / "selection_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    selected.loc[0, "base_soft_low"] = 0.31
    selected.to_csv(selected_path, index=False, lineterminator="\n")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        internal.load_locked_selection(
            tmp_path, expected_manifest_sha256="abc"
        )


def test_fixed_validation_reference_is_reused_without_clipping():
    from crmt_edge_ems.selection import score_validation_candidates_with_reference
    df = pd.DataFrame(
        {
            "method": ["ABL", "ABL"],
            "candidate_id": ["a", "b"],
            "o1": [-1.0, 12.0],
            "o2": [5.0, 5.0],
        }
    )
    refs = {
        "o1": {"ideal": 0.0, "observed_worst": 10.0, "span": 10.0, "degenerate": False},
        "o2": {"ideal": 5.0, "observed_worst": 5.0, "span": 0.0, "degenerate": True},
    }
    scored = score_validation_candidates_with_reference(
        df, objectives=("o1", "o2"), references=refs
    )
    assert np.isclose(scored.loc[0, "norm__o1"], -0.1)
    assert np.isclose(scored.loc[1, "norm__o1"], 1.2)
    assert np.allclose(scored["norm__o2"], 0.0)
    assert set(scored["normalization_reference_source"]) == {"primary_validation_lock"}
