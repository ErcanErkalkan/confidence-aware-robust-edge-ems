from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from data_adapters.opencem import (
    DEFAULT_CONFIRMATORY_SPLIT,
    audit_raw_measurements,
    reconstruct_per_inverter_profiles,
    per_inverter_daily_blocks,
    assign_confirmatory_split,
)

KEY_COLS = [
    "read_ts", "inverter",
    "outsumw", "outw_a", "outw_b", "outw_c",
    "pv1power", "pv2power", "pv3power",
    "gridpowerw_a", "gridpowerw_b", "gridpowerw_c",
    "battsoc", "battvolt", "battcurr", "battchgpower",
]


def _finite_summary(s: pd.Series) -> dict:
    x = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if x.empty:
        return {"n": 0}
    q = x.quantile([0, 0.001, 0.01, 0.5, 0.99, 0.999, 1.0])
    return {
        "n": int(x.size),
        "min": float(q.loc[0.0]),
        "p001": float(q.loc[0.001]),
        "p01": float(q.loc[0.01]),
        "median": float(q.loc[0.5]),
        "p99": float(q.loc[0.99]),
        "p999": float(q.loc[0.999]),
        "max": float(q.loc[1.0]),
        "negative_count": int((x < 0).sum()),
    }


def load_verified_csvs(raw_root: Path, verification_csv: Path) -> list[Path]:
    v = pd.read_csv(verification_csv)
    if v.empty or not v["verified"].astype(bool).all():
        raise RuntimeError("QA requires every selected partition to be verified first")
    paths = [raw_root / p for p in v["path"].astype(str)]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Verified manifest references missing files: {missing[:3]}")
    return paths


def select_train_cadence_minutes(
    raw: pd.DataFrame,
    *,
    expected_inverters: tuple[int, ...] | None = None,
    local_timezone: str = "Asia/Shanghai",
    train_start: str = "2025-07-14",
    train_end: str = "2025-12-31",
    quantile: float = 0.95,
    max_gap_minutes: float = 30.0,
    candidate_minutes: tuple[int, ...] = (1, 2, 5, 10, 15, 30),
) -> dict:
    """Select one replay cadence using TRAIN timestamps only.

    Positive within-stream gaps larger than max_gap_minutes are treated as outages
    rather than acquisition cadence. The selected grid is the smallest declared
    candidate not finer than the worst per-inverter gap quantile. Validation and
    test timestamps never enter this choice.
    """
    if not (0.5 <= quantile < 1.0):
        raise ValueError("quantile must be in [0.5,1)")
    if not candidate_minutes or any(x <= 0 for x in candidate_minutes):
        raise ValueError("candidate_minutes must be positive")
    ts = pd.to_datetime(pd.to_numeric(raw["read_ts"], errors="coerce"), unit="s", utc=True, errors="coerce")
    inv = pd.to_numeric(raw["inverter"], errors="coerce")
    local_date = ts.dt.tz_convert(local_timezone).dt.tz_localize(None).dt.normalize()
    lo, hi = pd.Timestamp(train_start), pd.Timestamp(train_end)
    train = pd.DataFrame({"ts": ts, "inv": inv, "date": local_date})
    train = train[(train["date"] >= lo) & (train["date"] <= hi)].dropna()
    observed = tuple(sorted(train["inv"].astype(int).unique()))
    expected = tuple(sorted(expected_inverters)) if expected_inverters else observed
    if not expected or set(expected) - set(observed):
        raise ValueError(f"Expected train inverter IDs unavailable: observed={observed}, expected={expected}")

    stats = {}
    worst_q_min = 0.0
    cutoff = float(max_gap_minutes) * 60.0
    for i in expected:
        # Use timedelta arithmetic rather than datetime integer storage units.
        # Pandas 3 may store timezone-aware datetimes at microsecond resolution,
        # while older versions commonly used nanoseconds; assuming 1e9 units
        # therefore makes cadence selection version-dependent.
        x = train.loc[train["inv"].astype(int) == i, "ts"].drop_duplicates().sort_values()
        gaps = x.diff().dt.total_seconds().dropna().to_numpy(dtype=float)
        gaps = gaps[(gaps > 0) & (gaps <= cutoff)]
        if gaps.size < 100:
            raise ValueError(f"Insufficient within-train cadence samples for inverter {i}: {gaps.size}")
        q = float(np.quantile(gaps, quantile))
        worst_q_min = max(worst_q_min, q / 60.0)
        stats[str(i)] = {
            "n_positive_nonoutage_gaps": int(gaps.size),
            "median_seconds": float(np.median(gaps)),
            "p90_seconds": float(np.quantile(gaps, 0.90)),
            "p95_seconds": float(np.quantile(gaps, 0.95)),
            "p99_seconds": float(np.quantile(gaps, 0.99)),
            "selection_quantile_seconds": q,
        }
    candidates = sorted(set(int(x) for x in candidate_minutes))
    selected = next((x for x in candidates if x >= worst_q_min - 1e-12), None)
    if selected is None:
        raise ValueError(
            f"Observed train cadence quantile {worst_q_min:.3f} min exceeds declared candidates {candidates}"
        )
    return {
        "selection_source": "TRAIN_ONLY",
        "train_date_range": [train_start, train_end],
        "quantile": quantile,
        "max_gap_minutes_excluded_as_outage": max_gap_minutes,
        "candidate_minutes": candidates,
        "selected_minutes": int(selected),
        "per_inverter": stats,
    }


def run_qa(paths: list[Path], *, expected_inverters: tuple[int, ...] | None = None) -> dict:
    frames = []
    per_file = []
    for path in paths:
        header = pd.read_csv(path, nrows=0)
        selected_cols = [c for c in KEY_COLS if c in header.columns]
        df = pd.read_csv(path, usecols=selected_cols)
        audit = audit_raw_measurements(df)
        if not audit.minimum_schema_ok:
            raise ValueError(f"Minimum schema failed for {path}: {audit}")
        per_file.append({
            "file": str(path),
            "rows": int(len(df)),
            "columns": list(audit.columns),
            "inverter_ids": list(audit.inverter_ids),
            "duplicate_read_ts_inverter": int(df.duplicated(["read_ts", "inverter"]).sum()),
            "missing_fraction": {
                c: float(df[c].isna().mean()) for c in KEY_COLS if c in df.columns
            },
        })
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    ts = pd.to_datetime(pd.to_numeric(raw["read_ts"], errors="coerce"), unit="s", utc=True, errors="coerce")
    ids = tuple(sorted(pd.to_numeric(raw["inverter"], errors="coerce").dropna().astype(int).unique()))
    if expected_inverters is not None and tuple(sorted(expected_inverters)) != ids:
        raise ValueError(f"Unexpected inverter IDs: observed={ids}, expected={expected_inverters}")

    cadence = select_train_cadence_minutes(raw, expected_inverters=expected_inverters or ids)
    selected_minutes = int(cadence["selected_minutes"])

    per_inverter_raw = {}
    for inv in ids:
        g = raw[pd.to_numeric(raw["inverter"], errors="coerce") == inv].copy()
        gts = pd.to_datetime(
            pd.to_numeric(g["read_ts"], errors="coerce"), unit="s", utc=True, errors="coerce"
        )
        finite_ts = gts.dropna().drop_duplicates().sort_values()
        gaps = finite_ts.astype("int64").to_numpy() / 1e9
        gaps = np.diff(gaps) if len(gaps) > 1 else np.array([], dtype=float)
        gaps = gaps[gaps > 0]
        per_inverter_raw[str(inv)] = {
            "rows": int(len(g)),
            "unique_valid_timestamps": int(finite_ts.size),
            "timestamp_utc_min": finite_ts.min().isoformat() if finite_ts.size else None,
            "timestamp_utc_max": finite_ts.max().isoformat() if finite_ts.size else None,
            "duplicate_read_ts": int(g.duplicated(["read_ts"]).sum()),
            "missing_fraction": {
                c: float(g[c].isna().mean()) for c in KEY_COLS if c in g.columns
            },
            "raw_gap_seconds": {
                "n": int(gaps.size),
                "median": float(np.median(gaps)) if gaps.size else None,
                "p95": float(np.quantile(gaps, 0.95)) if gaps.size else None,
                "p99": float(np.quantile(gaps, 0.99)) if gaps.size else None,
                "max": float(np.max(gaps)) if gaps.size else None,
            },
        }
    profiles = reconstruct_per_inverter_profiles(
        raw, frequency=f"{selected_minutes}min",
        expected_inverters=expected_inverters or ids, min_samples_per_inverter_bin=1
    )
    blocks = per_inverter_daily_blocks(
        profiles, expected_frequency_minutes=selected_minutes, min_coverage=0.95
    )
    split_counts = {}
    for inv, inv_blocks in blocks.items():
        assigned = assign_confirmatory_split(inv_blocks, split=DEFAULT_CONFIRMATORY_SPLIT)
        split_counts[str(inv)] = {k: len(v) for k, v in assigned.items()}

    power_columns = [c for c in KEY_COLS if c in raw.columns and c not in {"read_ts", "inverter"}]
    report = {
        "files": len(paths),
        "rows": int(len(raw)),
        "inverter_ids": list(ids),
        "timestamp_utc_min": ts.min().isoformat() if ts.notna().any() else None,
        "timestamp_utc_max": ts.max().isoformat() if ts.notna().any() else None,
        "invalid_timestamp_count": int(ts.isna().sum()),
        "duplicate_read_ts_inverter": int(raw.duplicated(["read_ts", "inverter"]).sum()),
        "per_file": per_file,
        "per_inverter_raw": per_inverter_raw,
        "power_summary_w": {c: _finite_summary(raw[c]) for c in power_columns},
        "train_only_cadence_selection": cadence,
        "complete_days_95pct_per_inverter": {str(k): len(v) for k, v in blocks.items()},
        "complete_days_by_split": split_counts,
        "neutral_peak_flag_verified": all(int(p["peak_flag"].sum()) == 0 for p in profiles.values()),
    }
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="OpenCEM verified-partition QA")
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--expected-inverters", default="", help="comma-separated integer IDs")
    args = p.parse_args()
    expected = tuple(int(x) for x in args.expected_inverters.split(",") if x.strip()) or None
    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    report = run_qa(paths, expected_inverters=expected)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "files": report["files"], "rows": report["rows"],
        "inverters": report["inverter_ids"],
        "complete_days": report["complete_days_95pct_per_inverter"],
        "splits": report["complete_days_by_split"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
