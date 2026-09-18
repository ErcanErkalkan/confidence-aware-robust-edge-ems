from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from crmt_edge_ems.site_model import calibrate_train_grid_caps

from data_adapters.opencem import (
    DEFAULT_CONFIRMATORY_SPLIT,
    audit_raw_measurements,
    reconstruct_per_inverter_profiles,
    per_inverter_daily_blocks,
    assign_confirmatory_split,
    collapse_same_timestamp_replay_signals,
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


def replay_signal_duplicate_diagnostics(df: pd.DataFrame) -> dict:
    """Characterize duplicate (read_ts, inverter) keys for replay-driving signals.

    The diagnostic intentionally uses only load/PV channels that can affect the
    reconstructed exogenous replay trace. Battery/grid telemetry differences do
    not turn otherwise identical replay inputs into distinct exogenous samples.
    No deduplication policy is applied here; this function is diagnostic only.
    """
    keys = ["read_ts", "inverter"]
    missing_keys = [c for c in keys if c not in df.columns]
    if missing_keys:
        raise KeyError(f"Missing duplicate-diagnostic key columns: {missing_keys}")
    signal_cols = [
        c for c in ("outsumw", "outw_a", "outw_b", "outw_c", "pv1power", "pv2power", "pv3power")
        if c in df.columns
    ]
    if not signal_cols:
        raise KeyError("No replay-driving load/PV columns available for duplicate diagnostics")

    dup_mask = df.duplicated(keys, keep=False)
    dup = df.loc[dup_mask, keys + signal_cols].copy()
    if dup.empty:
        return {
            "key_duplicate_extra_rows": 0,
            "duplicate_key_groups": 0,
            "exact_replay_signal_duplicate_extra_rows": 0,
            "conflicting_replay_signal_groups": 0,
            "max_key_multiplicity": 1,
            "key_multiplicity_quantiles": {"p50": 1.0, "p90": 1.0, "p95": 1.0, "p99": 1.0},
            "per_inverter": {},
            "signal_columns": signal_cols,
        }

    sizes = dup.groupby(keys, sort=False).size()
    unique_signal_rows = dup.drop_duplicates(keys + signal_cols, keep="first")
    distinct_signal_count = unique_signal_rows.groupby(keys, sort=False).size()
    exact_extra = int(dup.duplicated(keys + signal_cols, keep="first").sum())
    conflicts = int((distinct_signal_count > 1).sum())

    signal_delta_summary = {}
    for col in signal_cols:
        tmp = dup[keys].copy()
        tmp["_v"] = pd.to_numeric(dup[col], errors="coerce")
        ext = tmp.groupby(keys, sort=False)["_v"].agg(["min", "max"])
        delta = (ext["max"] - ext["min"]).replace([np.inf, -np.inf], np.nan).dropna()
        positive = delta[delta > 0.0]
        signal_delta_summary[col] = {
            "groups_with_numeric_delta": int(delta.size),
            "conflicting_groups": int(positive.size),
            "median_abs_delta": float(positive.median()) if positive.size else 0.0,
            "p95_abs_delta": float(positive.quantile(0.95)) if positive.size else 0.0,
            "p99_abs_delta": float(positive.quantile(0.99)) if positive.size else 0.0,
            "max_abs_delta": float(positive.max()) if positive.size else 0.0,
        }

    per_inv = {}
    for inv, g in dup.groupby("inverter", sort=True):
        gs = g.groupby(keys, sort=False).size()
        gu = g.drop_duplicates(keys + signal_cols, keep="first").groupby(keys, sort=False).size()
        per_inv[str(int(inv))] = {
            "duplicate_key_groups": int(gs.size),
            "key_duplicate_extra_rows": int((gs - 1).sum()),
            "conflicting_replay_signal_groups": int((gu > 1).sum()),
            "max_key_multiplicity": int(gs.max()),
        }

    return {
        "key_duplicate_extra_rows": int((sizes - 1).sum()),
        "duplicate_key_groups": int(sizes.size),
        "exact_replay_signal_duplicate_extra_rows": exact_extra,
        "conflicting_replay_signal_groups": conflicts,
        "max_key_multiplicity": int(sizes.max()),
        "key_multiplicity_quantiles": {
            "p50": float(sizes.quantile(0.50)),
            "p90": float(sizes.quantile(0.90)),
            "p95": float(sizes.quantile(0.95)),
            "p99": float(sizes.quantile(0.99)),
        },
        "per_inverter": per_inv,
        "signal_columns": signal_cols,
        "conflicting_signal_abs_delta": signal_delta_summary,
    }


def _json_safe(value):
    """Recursively normalize QA output to standard JSON-serializable Python types."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


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
    ids = tuple(int(x) for x in sorted(pd.to_numeric(raw["inverter"], errors="coerce").dropna().astype(int).unique()))
    if expected_inverters is not None and tuple(sorted(expected_inverters)) != ids:
        raise ValueError(f"Unexpected inverter IDs: observed={ids}, expected={expected_inverters}")

    duplicate_diagnostics = replay_signal_duplicate_diagnostics(raw)
    collapsed_replay = collapse_same_timestamp_replay_signals(raw)
    cadence = select_train_cadence_minutes(raw, expected_inverters=expected_inverters or ids)
    selected_minutes = int(cadence["selected_minutes"])

    per_inverter_raw = {}
    for inv in ids:
        g = raw[pd.to_numeric(raw["inverter"], errors="coerce") == inv].copy()
        gts = pd.to_datetime(
            pd.to_numeric(g["read_ts"], errors="coerce"), unit="s", utc=True, errors="coerce"
        )
        finite_ts = gts.dropna().drop_duplicates().sort_values()
        gaps = finite_ts.diff().dt.total_seconds().dropna().to_numpy(dtype=float)
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
    train_cap_calibration = {}
    for inv, inv_blocks in blocks.items():
        assigned = assign_confirmatory_split(inv_blocks, split=DEFAULT_CONFIRMATORY_SPLIT)
        split_counts[str(inv)] = {k: len(v) for k, v in assigned.items()}
        try:
            cap = calibrate_train_grid_caps(
                list(assigned["train"].values()),
                import_quantile=0.90,
                export_quantile=0.90,
                min_samples_each_direction=100,
            )
            train_cap_calibration[str(inv)] = {
                "status": "CALIBRATED",
                "source_split": "TRAIN_ONLY",
                "import_quantile": cap.import_quantile,
                "export_quantile": cap.export_quantile,
                "import_cap_kw": cap.import_cap_kw,
                "export_cap_kw": cap.export_cap_kw,
                "n_import_samples": cap.n_import_samples,
                "n_export_samples": cap.n_export_samples,
            }
        except ValueError as exc:
            train_cap_calibration[str(inv)] = {
                "status": "INSUFFICIENT_DIRECTIONAL_SAMPLES",
                "source_split": "TRAIN_ONLY",
                "import_quantile": 0.90,
                "export_quantile": 0.90,
                "error": str(exc),
            }

    block_manifest = complete_day_block_manifest(blocks, cadence_minutes=selected_minutes)
    block_manifest_hash = block_manifest_sha256(block_manifest)

    power_columns = [c for c in KEY_COLS if c in raw.columns and c not in {"read_ts", "inverter"}]
    report = {
        "files": len(paths),
        "rows": int(len(raw)),
        "inverter_ids": list(ids),
        "timestamp_utc_min": ts.min().isoformat() if ts.notna().any() else None,
        "timestamp_utc_max": ts.max().isoformat() if ts.notna().any() else None,
        "invalid_timestamp_count": int(ts.isna().sum()),
        "duplicate_read_ts_inverter": int(raw.duplicated(["read_ts", "inverter"]).sum()),
        "replay_signal_duplicate_diagnostics": duplicate_diagnostics,
        "replay_timestamp_collapse_policy": "mean replay-driving channels per (read_ts, inverter) before temporal resampling",
        "replay_rows_after_timestamp_collapse": int(len(collapsed_replay)),
        "per_file": per_file,
        "per_inverter_raw": per_inverter_raw,
        "power_summary_w": {c: _finite_summary(raw[c]) for c in power_columns},
        "train_only_cadence_selection": cadence,
        "complete_days_95pct_per_inverter": {str(k): len(v) for k, v in blocks.items()},
        "complete_days_by_split": split_counts,
        "train_only_grid_cap_calibration": train_cap_calibration,
        "complete_day_block_manifest": block_manifest.to_dict(orient="records"),
        "complete_day_block_manifest_sha256": block_manifest_hash,
        "neutral_peak_flag_verified": all(int(p["peak_flag"].sum()) == 0 for p in profiles.values()),
    }
    return _json_safe(report)


def complete_day_block_manifest(
    blocks: dict[int, dict[str, pd.DataFrame]],
    *,
    cadence_minutes: int,
) -> pd.DataFrame:
    """Create the machine-readable frozen block inventory from complete-day blocks."""
    rows = []
    for inv, inv_blocks in sorted(blocks.items()):
        assigned = assign_confirmatory_split(inv_blocks, split=DEFAULT_CONFIRMATORY_SPLIT)
        for split_name, split_blocks in assigned.items():
            for local_date, frame in sorted(split_blocks.items()):
                ts = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
                if ts.isna().any():
                    raise ValueError(f"Invalid timestamp in block inv={inv}, date={local_date}")
                rows.append({
                    "block_id": f"opencem:inv{int(inv)}:{local_date}",
                    "inverter_id": int(inv),
                    "local_date": str(local_date),
                    "split": str(split_name),
                    "cadence_minutes": int(cadence_minutes),
                    "n_ticks": int(len(frame)),
                    "timestamp_utc_min": ts.min().isoformat(),
                    "timestamp_utc_max": ts.max().isoformat(),
                    "source_commit": "5884d253a5267fb240b7a8df6fa9e4d49a905167",
                })
    columns = [
        "block_id", "inverter_id", "local_date", "split", "cadence_minutes",
        "n_ticks", "timestamp_utc_min", "timestamp_utc_max", "source_commit",
    ]
    out = pd.DataFrame(rows, columns=columns)
    if not out.empty and out["block_id"].duplicated().any():
        raise RuntimeError("Duplicate OpenCEM block IDs in manifest")
    return out.sort_values(["split", "inverter_id", "local_date"]).reset_index(drop=True)


def canonical_block_manifest_bytes(manifest: pd.DataFrame) -> bytes:
    """Canonical UTF-8/LF CSV bytes used for cryptographic manifest locking."""
    return manifest.to_csv(index=False, lineterminator="\n").encode("utf-8")


def block_manifest_sha256(manifest: pd.DataFrame) -> str:
    return hashlib.sha256(canonical_block_manifest_bytes(manifest)).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description="OpenCEM verified-partition QA")
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--block-manifest-csv", type=Path, default=None)
    p.add_argument("--expected-inverters", default="", help="comma-separated integer IDs")
    args = p.parse_args()
    expected = tuple(int(x) for x in args.expected_inverters.split(",") if x.strip()) or None
    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    report = run_qa(paths, expected_inverters=expected)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.block_manifest_csv is not None:
        args.block_manifest_csv.parent.mkdir(parents=True, exist_ok=True)
        manifest_df = pd.DataFrame(report["complete_day_block_manifest"])
        args.block_manifest_csv.write_bytes(canonical_block_manifest_bytes(manifest_df))
    print(json.dumps({
        "files": report["files"], "rows": report["rows"],
        "inverters": report["inverter_ids"],
        "complete_days": report["complete_days_95pct_per_inverter"],
        "splits": report["complete_days_by_split"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
