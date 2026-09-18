from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_adapters.opsd_household import OPSDHouseholdChannels
from opsd_ood_inventory import (
    build_inventory_from_frame,
    manifest_sha256,
)


def _multi_household_day():
    ts = pd.date_range(
        "2026-01-01",
        periods=1441,
        freq="1min",
        tz="UTC",
    )
    df = pd.DataFrame({
        "utc_timestamp": ts,
        "interpolated": "",
    })
    for h in ("residential3", "residential4", "residential6"):
        ch = OPSDHouseholdChannels.for_household(h)
        n = len(ts)
        df[ch.grid_import] = np.arange(n) * (1.0 / 60.0)
        df[ch.grid_export] = np.arange(n) * (0.1 / 60.0)
        df[ch.pv] = np.arange(n) * (0.3 / 60.0)
    return df


def test_inventory_builds_one_complete_day_per_household():
    manifest, qa = build_inventory_from_frame(_multi_household_day())
    assert len(manifest) == 3
    assert set(manifest["household"]) == {
        "residential3", "residential4", "residential6"
    }
    assert set(manifest["utc_date"]) == {"2026-01-01"}
    assert (manifest["coverage"] >= 0.95).all()
    assert len(manifest_sha256(manifest)) == 64
    assert all(v["eligible_days"] == 1 for v in qa.values())


def test_manifest_hash_is_order_independent():
    manifest, _ = build_inventory_from_frame(_multi_household_day())
    shuffled = manifest.sample(frac=1.0, random_state=7)
    assert manifest_sha256(manifest) == manifest_sha256(shuffled)


def test_strict_interpolation_policy_can_remove_day():
    df = _multi_household_day()
    ch = OPSDHouseholdChannels.for_household("residential3")
    # Dirty >5% of the day for residential3.
    for i in range(1, 100):
        df.loc[i, "interpolated"] = ch.grid_import + ";"
    manifest, _ = build_inventory_from_frame(df)
    assert not (
        (manifest["household"] == "residential3")
        & (manifest["utc_date"] == "2026-01-01")
    ).any()
    assert len(manifest) == 2
