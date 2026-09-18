from __future__ import annotations

import numpy as np
import pandas as pd

from data_adapters.opsd_household import OPSDHouseholdChannels
from opsd_ood_inventory import build_inventory_from_frame, manifest_sha256
from opsd_ood_replay_inventory import (
    build_full_replay_inventory,
    full_regular_days,
)


def _raw(days=2):
    n = days * 1440 + 1
    ts = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({"utc_timestamp": ts, "interpolated": ""})
    for h in ("residential3", "residential4", "residential6"):
        ch = OPSDHouseholdChannels.for_household(h)
        df[ch.grid_import] = np.arange(n) / 60.0
        df[ch.grid_export] = np.arange(n) * 0.1 / 60.0
        df[ch.pv] = np.arange(n) * 0.3 / 60.0
    return df


def _base_lock(df):
    m, _ = build_inventory_from_frame(df)
    return {
        "min_daily_coverage": 0.95,
        "manifest_rows": len(m),
        "manifest_sha256": manifest_sha256(m),
    }


def test_full_replay_inventory_is_exact_and_subset():
    df = _raw(2)
    manifest, summary = build_full_replay_inventory(
        df, base_inventory_lock=_base_lock(df)
    )
    assert len(manifest) == 6
    assert set(manifest["n_replay_bins"]) == {720}
    assert set(manifest["coverage"]) == {1.0}
    assert summary["manifest_rows"] == 6
    assert len(summary["manifest_sha256"]) == 64


def test_missing_two_minute_bin_excludes_day_from_full_replay():
    df = _raw(2)
    ch = OPSDHouseholdChannels.for_household("residential3")
    # Dirty both endpoint-derived intervals around one minute on Jan 1.
    df.loc[100, "interpolated"] = ch.grid_import + ";"
    manifest, _ = build_full_replay_inventory(
        df, base_inventory_lock=_base_lock(df)
    )
    jan1_r3 = (
        (manifest["household"] == "residential3")
        & (manifest["utc_date"] == "2026-01-01")
    )
    assert not jan1_r3.any()
    assert len(manifest) == 5
