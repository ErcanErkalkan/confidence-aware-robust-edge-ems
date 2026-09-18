from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.risk import RiskConfig
from data_adapters.opsd_household import OPSDHouseholdChannels
from opsd_ood_inventory import build_inventory_from_frame, manifest_sha256
from opsd_ood_replay_inventory import build_full_replay_inventory
from opsd_ood_evaluate import (
    EXPECTED_STRATA,
    build_locked_ood_blocks,
    stratified_risk_summaries,
)


OBJECTIVES = (
    "cap_violation_pct_total",
    "lfp_cycle_loss_pct",
    "ramp95_kw_per_min",
    "flip_per_day",
)


def _raw_one_day():
    # One-minute pre-roll + full day + one endpoint after the day.
    ts = pd.date_range(
        "2025-12-31T23:59:00Z",
        periods=1442,
        freq="1min",
    )
    df = pd.DataFrame({"utc_timestamp": ts, "interpolated": ""})
    for h in ("residential3", "residential4", "residential6"):
        ch = OPSDHouseholdChannels.for_household(h)
        n = len(ts)
        df[ch.grid_import] = np.arange(n) / 60.0
        df[ch.grid_export] = np.arange(n) * 0.1 / 60.0
        df[ch.pv] = np.arange(n) * 0.3 / 60.0
    return df


def _locks(df):
    base, _ = build_inventory_from_frame(df)
    base_lock = {
        "min_daily_coverage": 0.95,
        "manifest_rows": len(base),
        "manifest_sha256": manifest_sha256(base),
    }
    full, summary = build_full_replay_inventory(
        df, base_inventory_lock=base_lock
    )
    full_lock = {
        "package_sha256": "x",
        "base_inventory_sha256": base_lock["manifest_sha256"],
        "manifest_rows": len(full),
        "manifest_sha256": summary["manifest_sha256"],
        "expected_bins_per_day": 720,
    }
    return base_lock, full_lock


def test_locked_ood_blocks_cover_both_sites_for_every_membership():
    df = _raw_one_day()
    base_lock, full_lock = _locks(df)
    blocks, meta, context = build_locked_ood_blocks(
        df,
        base_inventory_lock=base_lock,
        full_replay_lock=full_lock,
    )
    assert len(blocks) == 6
    assert len(meta) == 6
    assert set(meta["target_site_id"]) == {1, 2}
    assert set(meta["household"]) == {
        "residential3", "residential4", "residential6"
    }
    assert context["ood_block_count"] == 6


def test_locked_ood_blocks_fail_closed_on_inventory_hash_drift():
    df = _raw_one_day()
    base_lock, full_lock = _locks(df)
    full_lock["manifest_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        build_locked_ood_blocks(
            df,
            base_inventory_lock=base_lock,
            full_replay_lock=full_lock,
        )


def test_macro_ood_risk_equal_weights_six_strata_not_block_counts():
    rows = []
    # One method; wildly unequal day counts across strata.
    counts = {
        ("residential3", 1): 1,
        ("residential3", 2): 2,
        ("residential4", 1): 3,
        ("residential4", 2): 4,
        ("residential6", 1): 5,
        ("residential6", 2): 20,
    }
    stratum_values = {}
    for i, ((h, s), n) in enumerate(counts.items(), start=1):
        value = float(i)
        stratum_values[(h, s)] = value
        for k in range(n):
            rows.append({
                "method": "CRMT",
                "candidate_id": "c1",
                "household": h,
                "target_site_id": s,
                **{obj: value for obj in OBJECTIVES},
            })
    metrics = pd.DataFrame(rows)
    risk = RiskConfig(q=0.90, tail_weight=0.0)
    strata, macro, pooled = stratified_risk_summaries(
        metrics, risk=risk
    )
    assert len(strata) == EXPECTED_STRATA == 6
    expected_macro = np.mean(list(stratum_values.values()))
    for obj in OBJECTIVES:
        assert np.isclose(float(macro.iloc[0][obj]), expected_macro)
        assert not np.isclose(
            float(pooled.iloc[0][obj]), expected_macro
        )
