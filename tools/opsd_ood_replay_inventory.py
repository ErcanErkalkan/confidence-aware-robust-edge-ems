from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd

from data_adapters.opsd_household import (
    OPSD_OOD_HOUSEHOLDS,
    native_net_profile,
    replay_profile_2min,
)
from opsd_ood_acquire import verify_locked_identity
from opsd_ood_inventory import (
    MANIFEST_COLUMNS,
    build_inventory_from_frame,
    manifest_sha256,
    required_usecols,
)


EXPECTED_BINS_PER_DAY = 720


def _canonical_bytes(df: pd.DataFrame) -> bytes:
    ordered = df.loc[:, MANIFEST_COLUMNS].sort_values(
        ["household", "utc_date"], kind="mergesort"
    )
    return ordered.to_csv(index=False, lineterminator="\n").encode("utf-8")


def full_regular_days(
    replay: pd.DataFrame,
    *,
    household: str,
) -> dict[str, pd.DataFrame]:
    x = replay.copy()
    x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True, errors="raise")
    if x["timestamp"].duplicated().any():
        raise ValueError("OPSD replay timestamps must be unique")
    x["utc_date"] = x["timestamp"].dt.strftime("%Y-%m-%d")

    out: dict[str, pd.DataFrame] = {}
    for date, frame in x.groupby("utc_date", sort=True):
        g = frame.sort_values("timestamp").reset_index(drop=True)
        if len(g) != EXPECTED_BINS_PER_DAY:
            continue
        start = pd.Timestamp(f"{date}T00:00:00Z")
        expected = pd.date_range(
            start,
            periods=EXPECTED_BINS_PER_DAY,
            freq="2min",
        )
        observed = pd.DatetimeIndex(g["timestamp"])
        if not observed.equals(expected):
            continue
        out[str(date)] = g
    return out


def build_full_replay_inventory(
    df: pd.DataFrame,
    *,
    base_inventory_lock: dict,
) -> tuple[pd.DataFrame, dict]:
    base_manifest, _ = build_inventory_from_frame(
        df,
        min_daily_coverage=float(base_inventory_lock["min_daily_coverage"]),
    )
    observed_base_hash = manifest_sha256(base_manifest)
    if int(len(base_manifest)) != int(base_inventory_lock["manifest_rows"]):
        raise RuntimeError("base OPSD eligible-day row-count mismatch")
    if observed_base_hash != str(base_inventory_lock["manifest_sha256"]):
        raise RuntimeError("base OPSD eligible-day manifest hash mismatch")

    rows = []
    counts = {}
    for household in OPSD_OOD_HOUSEHOLDS:
        native = native_net_profile(df, household)
        replay = replay_profile_2min(native)
        blocks = full_regular_days(replay, household=household)
        counts[household] = int(len(blocks))
        for date, block in blocks.items():
            rows.append({
                "household": household,
                "utc_date": date,
                "n_replay_bins": EXPECTED_BINS_PER_DAY,
                "coverage": 1.0,
                "first_timestamp": pd.Timestamp(
                    block["timestamp"].iloc[0]
                ).isoformat(),
                "last_timestamp": pd.Timestamp(
                    block["timestamp"].iloc[-1]
                ).isoformat(),
            })

    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    if manifest.empty:
        raise RuntimeError("OPSD full-regular replay inventory is empty")
    if manifest.duplicated(["household", "utc_date"]).any():
        raise RuntimeError("duplicate OPSD full-day membership")
    if not set(
        zip(manifest["household"], manifest["utc_date"])
    ).issubset(
        set(zip(base_manifest["household"], base_manifest["utc_date"]))
    ):
        raise RuntimeError("full-day replay inventory is not a subset of base inventory")

    summary = {
        "stage": "OPSD_OOD_FULL_REGULAR_REPLAY_INVENTORY_ONLY",
        "claim_boundary": (
            "Timestamp/replay safety inventory only. No controller or OOD "
            "performance metric is computed."
        ),
        "base_inventory_sha256": observed_base_hash,
        "manifest_rows": int(len(manifest)),
        "manifest_sha256": hashlib.sha256(
            _canonical_bytes(manifest)
        ).hexdigest(),
        "expected_bins_per_day": EXPECTED_BINS_PER_DAY,
        "coverage": 1.0,
        "per_household_full_days": counts,
    }
    return manifest, summary


def build_from_locked_zip(
    zip_path: Path,
    *,
    artifact_lock: dict,
    base_inventory_lock: dict,
) -> tuple[pd.DataFrame, dict]:
    observed = verify_locked_identity(zip_path, artifact_lock)
    member = observed["resolved_members"][
        "household_data_1min_singleindex.csv"
    ]
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(member) as fh:
            df = pd.read_csv(
                fh,
                usecols=required_usecols(),
                low_memory=False,
            )
    manifest, summary = build_full_replay_inventory(
        df,
        base_inventory_lock=base_inventory_lock,
    )
    summary["artifact_sha256"] = observed["sha256"]
    summary["artifact_byte_size"] = observed["byte_size"]
    return manifest, summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Generate full-regular OPSD OOD replay-day inventory"
    )
    p.add_argument("--zip", dest="zip_path", type=Path, required=True)
    p.add_argument("--artifact-lock-json", type=Path, required=True)
    p.add_argument("--base-inventory-lock-json", type=Path, required=True)
    p.add_argument("--output-csv", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    artifact_lock = json.loads(
        args.artifact_lock_json.read_text(encoding="utf-8")
    )
    base_lock = json.loads(
        args.base_inventory_lock_json.read_text(encoding="utf-8")
    )
    manifest, summary = build_from_locked_zip(
        args.zip_path,
        artifact_lock=artifact_lock,
        base_inventory_lock=base_lock,
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.write_bytes(_canonical_bytes(manifest))
    args.output_json.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
