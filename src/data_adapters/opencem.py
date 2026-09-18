from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .common import canonical_profile


MIN_SCHEMA = ("read_ts", "inverter", "pv1power")
_LOAD_TOTAL_CANDIDATE = "outsumw"
_LOAD_PHASES = ("outw_a", "outw_b", "outw_c")
_PV_PHASES = ("pv1power", "pv2power", "pv3power")


@dataclass(frozen=True)
class OpenCEMSchemaAudit:
    rows: int
    columns: tuple[str, ...]
    missing_minimum: tuple[str, ...]
    inverter_ids: tuple[int, ...]
    has_total_load: bool
    has_phase_load: bool

    @property
    def minimum_schema_ok(self) -> bool:
        return not self.missing_minimum and (self.has_total_load or self.has_phase_load)


@dataclass(frozen=True)
class ChronologicalSplit:
    train_start: str = "2025-07-14"
    train_end: str = "2025-12-31"
    validation_start: str = "2026-01-01"
    validation_end: str = "2026-02-28"
    test_start: str = "2026-03-01"
    test_end: str = "2026-04-11"

    def validate(self) -> None:
        dates = [
            pd.Timestamp(self.train_start), pd.Timestamp(self.train_end),
            pd.Timestamp(self.validation_start), pd.Timestamp(self.validation_end),
            pd.Timestamp(self.test_start), pd.Timestamp(self.test_end),
        ]
        if not (
            dates[0] <= dates[1] < dates[2] <= dates[3] < dates[4] <= dates[5]
        ):
            raise ValueError("Chronological split ranges must be ordered and non-overlapping")


DEFAULT_CONFIRMATORY_SPLIT = ChronologicalSplit()


def audit_raw_measurements(df: pd.DataFrame) -> OpenCEMSchemaAudit:
    cols = tuple(map(str, df.columns))
    missing = tuple(c for c in MIN_SCHEMA if c not in df.columns)
    inv = (
        tuple(int(x) for x in sorted(pd.to_numeric(df["inverter"], errors="coerce").dropna().astype(int).unique()))
        if "inverter" in df else ()
    )
    return OpenCEMSchemaAudit(
        rows=len(df),
        columns=cols,
        missing_minimum=missing,
        inverter_ids=inv,
        has_total_load=_LOAD_TOTAL_CANDIDATE in df.columns,
        has_phase_load=any(c in df.columns for c in _LOAD_PHASES),
    )


def refuse_unsafe_grid_as_uncontrolled_base() -> None:
    raise RuntimeError(
        "OpenCEM gridpower telemetry must not be treated as uncontrolled base_kw: "
        "the measured system already contains battery/inverter behavior. Use the "
        "measured AC load output and PV generation channels to reconstruct the "
        "battery-free exogenous net profile."
    )


def _numeric(df: pd.DataFrame, names: Sequence[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for name in names:
        out[name] = pd.to_numeric(df[name], errors="coerce") if name in df.columns else np.nan
    return out


def _load_w(df: pd.DataFrame) -> pd.Series:
    # OpenCEM README identifies outsumw/outw_* as output active power (load).
    # Prefer outsumw; phase sum is only a missing-value fallback.
    total = (
        pd.to_numeric(df[_LOAD_TOTAL_CANDIDATE], errors="coerce")
        if _LOAD_TOTAL_CANDIDATE in df
        else pd.Series(np.nan, index=df.index)
    )
    phase = _numeric(df, _LOAD_PHASES).sum(axis=1, min_count=1)
    load = total.where(total.notna(), phase)
    return load.where(load >= 0.0)


def _pv_w(df: pd.DataFrame) -> pd.Series:
    # The public schema exposes pv1/pv2/pv3 power channels per inverter.
    pv = _numeric(df, _PV_PHASES).sum(axis=1, min_count=1)
    return pv.where(pv >= 0.0)


def collapse_same_timestamp_replay_signals(raw: pd.DataFrame) -> pd.DataFrame:
    """Collapse repeated (read_ts, inverter) replay samples before resampling.

    OpenCEM contains many duplicate timestamp/inverter keys. Because the replay
    reconstruction uses load/PV telemetry as exogenous inputs, duplicated rows
    must not receive extra statistical weight inside a later time bin. For each
    key, available replay-driving channels are therefore averaged once. The rule
    is deterministic and independent of CSV row ordering; exact duplicates are
    unchanged and conflicting pairs contribute their arithmetic midpoint.
    """
    keys = ["read_ts", "inverter"]
    missing = [c for c in keys if c not in raw.columns]
    if missing:
        raise KeyError(f"Missing collapse key columns: {missing}")
    signal_cols = [
        c for c in (_LOAD_TOTAL_CANDIDATE, *_LOAD_PHASES, *_PV_PHASES)
        if c in raw.columns
    ]
    if not signal_cols:
        raise KeyError("No replay-driving load/PV columns available for timestamp collapse")
    work = raw[keys + signal_cols].copy()
    work["read_ts"] = pd.to_numeric(work["read_ts"], errors="coerce")
    work["inverter"] = pd.to_numeric(work["inverter"], errors="coerce")
    for c in signal_cols:
        work[c] = pd.to_numeric(work[c], errors="coerce")
    work = work.dropna(subset=keys)
    collapsed = work.groupby(keys, as_index=False, sort=True, dropna=False)[signal_cols].mean()
    return collapsed


def reconstruct_counterfactual_profile(
    raw: pd.DataFrame,
    *,
    frequency: str = "1min",
    local_timezone: str = "Asia/Shanghai",
    expected_inverters: Sequence[int] | None = None,
    min_samples_per_inverter_bin: int = 1,
) -> pd.DataFrame:
    """Reconstruct an exogenous battery-free trace from OpenCEM measurements.

    Frozen semantics:
      * AC inverter output active power is treated as served load demand.
      * PV power channels are treated as exogenous renewable generation.
      * battery-free base_kw = load_kw - pv_kw.
      * measured grid import is excluded because it already reflects the deployed
        battery/inverter/controller behavior and is therefore not an exogenous
        uncontrolled baseline.

    Inverter streams are resampled indepently and aggregated only after
    resampling, so a higher-rate stream cannot receive extra statistical weight.
    With expected_inverters supplied, only bins in which every expected inverter
    has both load and PV observations survive.
    """
    audit = audit_raw_measurements(raw)
    if not audit.minimum_schema_ok:
        raise ValueError(
            f"OpenCEM minimum schema failed: missing={audit.missing_minimum}, "
            f"has_total_load={audit.has_total_load}, has_phase_load={audit.has_phase_load}"
        )
    if min_samples_per_inverter_bin < 1:
        raise ValueError("min_samples_per_inverter_bin must be >= 1")

    x = pd.DataFrame({
        "timestamp": pd.to_datetime(
            pd.to_numeric(raw["read_ts"], errors="coerce"), unit="s", utc=True, errors="coerce"
        ),
        "inverter": pd.to_numeric(raw["inverter"], errors="coerce"),
        "load_kw": _load_w(raw) / 1000.0,
        "pv_kw": _pv_w(raw) / 1000.0,
    }).dropna(subset=["timestamp", "inverter"])
    x["inverter"] = x["inverter"].astype(int)

    expected = (
        tuple(sorted(int(i) for i in expected_inverters))
        if expected_inverters is not None
        else audit.inverter_ids
    )
    if not expected:
        raise ValueError("No inverter IDs available")
    unknown = sorted(set(expected) - set(audit.inverter_ids))
    if unknown:
        raise ValueError(f"Expected inverter IDs absent from input: {unknown}")

    frames: list[pd.DataFrame] = []
    for inv in expected:
        g = x[x["inverter"] == inv].set_index("timestamp").sort_index()
        values = g[["load_kw", "pv_kw"]].resample(frequency).mean()
        counts = g[["load_kw", "pv_kw"]].resample(frequency).count()
        valid = (
            (counts["load_kw"] >= min_samples_per_inverter_bin)
            & (counts["pv_kw"] >= min_samples_per_inverter_bin)
        )
        values = values.loc[valid].copy()
        values["inverter"] = inv
        frames.append(values.reset_index())

    long = pd.concat(frames, ignore_index=True)
    load_p = long.pivot(index="timestamp", columns="inverter", values="load_kw").reindex(columns=list(expected))
    pv_p = long.pivot(index="timestamp", columns="inverter", values="pv_kw").reindex(columns=list(expected))
    complete = load_p.notna().all(axis=1) & pv_p.notna().all(axis=1)
    load = load_p.loc[complete, list(expected)].sum(axis=1)
    pv = pv_p.loc[complete, list(expected)].sum(axis=1)

    local = load.index.tz_convert(local_timezone)
    # No tariff/peak window is inferred from telemetry. The raw replay profile
    # is neutral (peak_flag=0); any operating-window stress definition must be
    # applied explicitly by the locked experiment protocol.
    out = canonical_profile(load.index, load.to_numpy(), pv.to_numpy(), peak_flag=None)
    out["source"] = "OpenCEM"
    out["source_inverters"] = ",".join(map(str, expected))
    out["local_date"] = pd.Index(local.date).astype(str)
    return out.reset_index(drop=True)


def apply_peak_window(
    profile: pd.DataFrame,
    *,
    local_timezone: str,
    start_hour: int,
    end_hour: int,
) -> pd.DataFrame:
    """Apply an explicit protocol-defined local operating window.

    This is intentionally separate from raw data reconstruction so a tariff or
    grid-stress window cannot be silently inferred from OpenCEM telemetry.
    Supports ordinary windows (e.g. 17--22) and wrap-around windows (22--6).
    """
    if not (0 <= int(start_hour) <= 23 and 0 <= int(end_hour) <= 23):
        raise ValueError("start_hour and end_hour must be in 0..23")
    if int(start_hour) == int(end_hour):
        raise ValueError("start_hour and end_hour must differ")
    if "timestamp" not in profile.columns:
        raise KeyError("profile must contain timestamp")
    ts = pd.to_datetime(profile["timestamp"], utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError("profile contains invalid timestamps")
    h = ts.dt.tz_convert(local_timezone).dt.hour
    if start_hour < end_hour:
        flag = (h >= start_hour) & (h < end_hour)
    else:
        flag = (h >= start_hour) | (h < end_hour)
    out = profile.copy()
    out["peak_flag"] = flag.astype(int).to_numpy()
    return out


def daily_blocks(
    profile: pd.DataFrame,
    *,
    expected_frequency_minutes: int = 1,
    min_coverage: float = 0.95,
) -> dict[str, pd.DataFrame]:
    """Return local-date blocks passing a predeclared completeness gate."""
    if "local_date" not in profile.columns:
        raise KeyError("profile must contain local_date from reconstruct_counterfactual_profile")
    if expected_frequency_minutes <= 0:
        raise ValueError("expected_frequency_minutes must be > 0")
    if not (0.0 < min_coverage <= 1.0):
        raise ValueError("min_coverage must be in (0, 1]")
    expected = int(round(24 * 60 / expected_frequency_minutes))
    minimum = int(np.ceil(min_coverage * expected))
    blocks: dict[str, pd.DataFrame] = {}
    for date, g in profile.groupby("local_date", sort=True):
        if len(g) >= minimum:
            blocks[str(date)] = g.sort_values("timestamp").reset_index(drop=True)
    return blocks


def assign_confirmatory_split(
    blocks: dict[str, pd.DataFrame],
    *,
    split: ChronologicalSplit = DEFAULT_CONFIRMATORY_SPLIT,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Assign complete local-day blocks to frozen chronological splits.

    Dates outside the frozen ranges are deliberately excluded. In particular,
    the partial boundary dates implied by the immutable OpenCEM coverage
    (2025-07-13 local start and 2026-04-12 local end) cannot enter a split.
    """
    split.validate()
    ranges = {
        "train": (pd.Timestamp(split.train_start), pd.Timestamp(split.train_end)),
        "validation": (pd.Timestamp(split.validation_start), pd.Timestamp(split.validation_end)),
        "internal_test": (pd.Timestamp(split.test_start), pd.Timestamp(split.test_end)),
    }
    assigned: dict[str, dict[str, pd.DataFrame]] = {k: {} for k in ranges}
    seen: set[str] = set()
    for date, frame in sorted(blocks.items()):
        d = pd.Timestamp(date)
        matched = [name for name, (lo, hi) in ranges.items() if lo <= d <= hi]
        if len(matched) > 1:
            raise RuntimeError(f"Split overlap for {date}: {matched}")
        if matched:
            name = matched[0]
            if date in seen:
                raise RuntimeError(f"Duplicate day assignment: {date}")
            assigned[name][date] = frame
            seen.add(date)
    return assigned


def build_from_validated_components(
    timestamp: Iterable,
    load_kw: Iterable[float],
    pv_kw: Iterable[float],
    *,
    peak_flag: Iterable[int] | None = None,
) -> pd.DataFrame:
    out = canonical_profile(timestamp, load_kw, pv_kw, peak_flag=peak_flag)
    out["source"] = "OpenCEM"
    return out


def reconstruct_per_inverter_profiles(
    raw: pd.DataFrame,
    *,
    frequency: str = "1min",
    local_timezone: str = "Asia/Shanghai",
    expected_inverters: Sequence[int] | None = None,
    min_samples_per_inverter_bin: int = 1,
) -> dict[int, pd.DataFrame]:
    """Reconstruct physically independent OpenCEM subsystem profiles.

    OpenCEM documents two independent PV-battery subsystems. For confirmatory
    real-data replay, each inverter/subsystem is therefore retained as its own
    block domain. Cross-inverter aggregation remains available through
    `reconstruct_counterfactual_profile` only for secondary sensitivity work.
    """
    audit = audit_raw_measurements(raw)
    if not audit.minimum_schema_ok:
        raise ValueError(
            f"OpenCEM minimum schema failed: missing={audit.missing_minimum}, "
            f"has_total_load={audit.has_total_load}, has_phase_load={audit.has_phase_load}"
        )
    if min_samples_per_inverter_bin < 1:
        raise ValueError("min_samples_per_inverter_bin must be >= 1")

    x = pd.DataFrame({
        "timestamp": pd.to_datetime(
            pd.to_numeric(raw["read_ts"], errors="coerce"), unit="s", utc=True, errors="coerce"
        ),
        "inverter": pd.to_numeric(raw["inverter"], errors="coerce"),
        "load_kw": _load_w(raw) / 1000.0,
        "pv_kw": _pv_w(raw) / 1000.0,
    }).dropna(subset=["timestamp", "inverter"])
    x["inverter"] = x["inverter"].astype(int)

    expected = (
        tuple(sorted(int(i) for i in expected_inverters))
        if expected_inverters is not None
        else audit.inverter_ids
    )
    if not expected:
        raise ValueError("No inverter IDs available")
    unknown = sorted(set(expected) - set(audit.inverter_ids))
    if unknown:
        raise ValueError(f"Expected inverter IDs absent from input: {unknown}")

    profiles: dict[int, pd.DataFrame] = {}
    for inv in expected:
        g = x[x["inverter"] == inv].set_index("timestamp").sort_index()
        values = g[["load_kw", "pv_kw"]].resample(frequency).mean()
        counts = g[["load_kw", "pv_kw"]].resample(frequency).count()
        valid = (
            (counts["load_kw"] >= min_samples_per_inverter_bin)
            & (counts["pv_kw"] >= min_samples_per_inverter_bin)
        )
        values = values.loc[valid]
        local = values.index.tz_convert(local_timezone)
        p = canonical_profile(
            values.index,
            values["load_kw"].to_numpy(),
            values["pv_kw"].to_numpy(),
            peak_flag=None,
        )
        p["source"] = "OpenCEM"
        p["source_inverter"] = int(inv)
        p["local_date"] = pd.Index(local.date).astype(str)
        profiles[int(inv)] = p.reset_index(drop=True)
    return profiles


def per_inverter_daily_blocks(
    profiles: dict[int, pd.DataFrame],
    *,
    expected_frequency_minutes: int = 1,
    min_coverage: float = 0.95,
) -> dict[int, dict[str, pd.DataFrame]]:
    """Apply the same complete-day gate independently to each subsystem."""
    return {
        int(inv): daily_blocks(
            profile,
            expected_frequency_minutes=expected_frequency_minutes,
            min_coverage=min_coverage,
        )
        for inv, profile in sorted(profiles.items())
    }
