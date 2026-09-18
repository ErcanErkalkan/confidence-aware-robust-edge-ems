from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_adapters.opsd_household import (
    OPSDHouseholdChannels,
    complete_day_blocks,
    native_net_profile,
    replay_profile_2min,
)


def _raw(n=7, household="residential3"):
    ch = OPSDHouseholdChannels.for_household(household)
    ts = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    imp = np.arange(n) * (1.0 / 60.0)
    exp = np.arange(n) * (0.2 / 60.0)
    pv = np.arange(n) * (0.4 / 60.0)
    return pd.DataFrame({
        "utc_timestamp": ts,
        "interpolated": "",
        ch.grid_import: imp,
        ch.grid_export: exp,
        ch.pv: pv,
    })


def test_opsd_cumulative_energy_to_native_net_power():
    x = native_net_profile(_raw(), "residential3")
    valid = x[x["valid_native_interval"]]
    assert len(valid) == 6
    assert np.allclose(valid["base_kw"], 0.8)
    assert np.allclose(valid["pv_kw"], 0.4)
    assert np.allclose(valid["load_kw"], 1.2)


def test_opsd_reset_gap_and_relevant_interpolation_are_invalid():
    df = _raw(8)
    ch = OPSDHouseholdChannels.for_household("residential3")
    df.loc[3, "interpolated"] = ch.grid_import + ";"
    df.loc[6:, ch.pv] = 0.0
    df.loc[7, "utc_timestamp"] = pd.Timestamp("2026-01-01T00:09:00Z")
    x = native_net_profile(df, "residential3")
    assert not bool(x.loc[3, "valid_native_interval"])
    assert not bool(x.loc[4, "valid_native_interval"])
    assert not bool(x.loc[6, "valid_native_interval"])
    assert not bool(x.loc[7, "valid_native_interval"])


def test_opsd_two_minute_replay_requires_two_clean_native_minutes():
    x = native_net_profile(_raw(8), "residential3")
    r = replay_profile_2min(x)
    assert list(r["timestamp"]) == [
        pd.Timestamp("2026-01-01T00:02:00Z"),
        pd.Timestamp("2026-01-01T00:04:00Z"),
        pd.Timestamp("2026-01-01T00:06:00Z"),
    ]
    assert np.allclose(r["base_kw"], 0.8)


def test_opsd_adapter_rejects_noncohort_household():
    with pytest.raises(ValueError):
        OPSDHouseholdChannels.for_household("residential1")


def test_opsd_complete_day_gate_is_deterministic():
    ts = pd.date_range(
        "2026-01-01", periods=720, freq="2min", tz="UTC"
    )
    p = pd.DataFrame({
        "timestamp": ts,
        "load_kw": 1.0,
        "pv_kw": 0.0,
        "wind_kw": 0.0,
        "base_kw": 1.0,
        "peak_flag": 0,
        "valid_native_interval": True,
    })
    assert "2026-01-01" in complete_day_blocks(p, min_coverage=0.95)
    assert not complete_day_blocks(p.iloc[:680], min_coverage=0.95)
