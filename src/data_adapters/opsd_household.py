from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


OPSD_OOD_HOUSEHOLDS = ("residential3", "residential4", "residential6")
NATIVE_CADENCE_MINUTES = 1
REPLAY_CADENCE_MINUTES = 2


@dataclass(frozen=True)
class OPSDHouseholdChannels:
    household: str
    grid_import: str
    grid_export: str
    pv: str

    @classmethod
    def for_household(cls, household: str) -> "OPSDHouseholdChannels":
        household = str(household).lower()
        if household not in OPSD_OOD_HOUSEHOLDS:
            raise ValueError(
                f"household must be one of {OPSD_OOD_HOUSEHOLDS}, got {household!r}"
            )
        prefix = f"DE_KN_{household}"
        return cls(
            household=household,
            grid_import=f"{prefix}_grid_import",
            grid_export=f"{prefix}_grid_export",
            pv=f"{prefix}_pv",
        )


def _interpolation_mentions(marker: object, channels: Iterable[str]) -> bool:
    if marker is None or (isinstance(marker, float) and np.isnan(marker)):
        return False
    text = str(marker)
    if not text.strip():
        return False
    return any(str(channel) in text for channel in channels)


def native_net_profile(
    df: pd.DataFrame,
    household: str,
    *,
    timestamp_col: str = "utc_timestamp",
    interpolation_col: str = "interpolated",
    reset_tolerance_kwh: float = 1e-9,
) -> pd.DataFrame:
    """Derive 1-minute power from OPSD cumulative-energy channels."""
    ch = OPSDHouseholdChannels.for_household(household)
    required = [
        timestamp_col,
        interpolation_col,
        ch.grid_import,
        ch.grid_export,
        ch.pv,
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing OPSD columns: {missing}")

    work = df[required].copy()
    work[timestamp_col] = pd.to_datetime(
        work[timestamp_col], utc=True, errors="raise"
    )
    if work[timestamp_col].duplicated().any():
        raise ValueError("OPSD timestamps must be unique before differencing")
    work = work.sort_values(timestamp_col).reset_index(drop=True)

    for col in (ch.grid_import, ch.grid_export, ch.pv):
        work[col] = pd.to_numeric(work[col], errors="coerce")

    dt_min = work[timestamp_col].diff().dt.total_seconds() / 60.0
    exact_step = np.isclose(
        dt_min.to_numpy(dtype=float),
        float(NATIVE_CADENCE_MINUTES),
        rtol=0.0,
        atol=1e-9,
        equal_nan=False,
    )

    channel_names = (ch.grid_import, ch.grid_export, ch.pv)
    current_interp = work[interpolation_col].map(
        lambda x: _interpolation_mentions(x, channel_names)
    )
    previous_interp = current_interp.shift(1, fill_value=True)
    clean_endpoints = ~(current_interp | previous_interp)

    deltas = work[list(channel_names)].diff()
    delta_array = deltas.to_numpy(dtype=float)
    finite = np.isfinite(delta_array).all(axis=1)
    nonnegative = (
        delta_array >= -float(reset_tolerance_kwh)
    ).all(axis=1)

    valid = (
        pd.Series(exact_step, index=work.index)
        & clean_endpoints
        & pd.Series(finite, index=work.index)
        & pd.Series(nonnegative, index=work.index)
    )

    factor = 60.0 / float(NATIVE_CADENCE_MINUTES)
    import_kw = factor * deltas[ch.grid_import]
    export_kw = factor * deltas[ch.grid_export]
    pv_kw = factor * deltas[ch.pv]
    base_kw = import_kw - export_kw
    load_kw = base_kw + pv_kw

    out = pd.DataFrame(
        {
            "timestamp": work[timestamp_col],
            "load_kw": load_kw,
            "pv_kw": pv_kw,
            "wind_kw": 0.0,
            "base_kw": base_kw,
            "peak_flag": 0,
            "source": "OPSD Household Data 2020-04-15",
            "source_household": ch.household,
            "source_interpolated": current_interp.astype(bool),
            "valid_native_interval": valid.astype(bool),
        }
    )
    numeric = ["load_kw", "pv_kw", "wind_kw", "base_kw"]
    out.loc[~valid, numeric] = np.nan
    return out


def replay_profile_2min(
    native: pd.DataFrame,
    *,
    require_two_clean_minutes: bool = True,
) -> pd.DataFrame:
    """Aggregate valid native 1-minute net power to exact 2-minute replay bins."""
    required = {
        "timestamp",
        "load_kw",
        "pv_kw",
        "wind_kw",
        "base_kw",
        "valid_native_interval",
    }
    missing = sorted(required - set(native.columns))
    if missing:
        raise KeyError(f"Missing native OPSD profile columns: {missing}")

    x = native.copy()
    x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True, errors="raise")
    if x["timestamp"].duplicated().any():
        raise ValueError("native OPSD profile contains duplicate timestamps")
    x = x.sort_values("timestamp")
    x["bin"] = x["timestamp"].dt.floor(f"{REPLAY_CADENCE_MINUTES}min")

    valid = x[
        x["valid_native_interval"].astype(bool)
        & x[["load_kw", "pv_kw", "wind_kw", "base_kw"]].notna().all(axis=1)
    ].copy()
    grouped = valid.groupby("bin", sort=True)
    counts = grouped.size()
    agg = grouped[["load_kw", "pv_kw", "wind_kw", "base_kw"]].mean()
    if require_two_clean_minutes:
        agg = agg[counts == REPLAY_CADENCE_MINUTES]

    out = agg.reset_index().rename(columns={"bin": "timestamp"})
    out["peak_flag"] = 0
    out["source"] = "OPSD Household Data 2020-04-15"
    if "source_household" in x.columns and x["source_household"].nunique() == 1:
        out["source_household"] = str(x["source_household"].iloc[0])
    return out


def complete_day_blocks(
    replay: pd.DataFrame,
    *,
    min_coverage: float = 0.95,
) -> dict[str, pd.DataFrame]:
    """Return UTC day blocks meeting the predeclared 2-minute coverage gate."""
    if not (0.0 < float(min_coverage) <= 1.0):
        raise ValueError("min_coverage must be in (0,1]")
    x = replay.copy()
    x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True, errors="raise")
    x["utc_date"] = x["timestamp"].dt.strftime("%Y-%m-%d")
    expected = int(24 * 60 / REPLAY_CADENCE_MINUTES)
    threshold = int(np.ceil(expected * float(min_coverage)))
    blocks: dict[str, pd.DataFrame] = {}
    for date, frame in x.groupby("utc_date", sort=True):
        clean = frame.sort_values("timestamp").reset_index(drop=True)
        if len(clean) >= threshold:
            blocks[str(date)] = clean
    return blocks
