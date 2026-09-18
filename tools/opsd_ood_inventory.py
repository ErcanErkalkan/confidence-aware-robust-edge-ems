from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from data_adapters.opsd_household import (
    OPSD_OOD_HOUSEHOLDS,
    OPSDHouseholdChannels,
    complete_day_blocks,
    native_net_profile,
    replay_profile_2min,
)
from opsd_ood_acquire import verify_locked_identity


MANIFEST_COLUMNS = (
    "household",
    "utc_date",
    "n_replay_bins",
    "coverage",
    "first_timestamp",
    "last_timestamp",
)


def _canonical_manifest_bytes(df: pd.DataFrame) -> bytes:
    ordered = df.loc[:, MANIFEST_COLUMNS].sort_values(
        ["household", "utc_date"], kind="mergesort"
    )
    text = ordered.to_csv(index=False, lineterminator="\n")
    return text.encode("utf-8")


def manifest_sha256(df: pd.DataFrame) -> str:
    return hashlib.sha256(_canonical_manifest_bytes(df)).hexdigest()


def required_usecols() -> list[str]:
    cols = ["utc_timestamp", "interpolated"]
    for household in OPSD_OOD_HOUSEHOLDS:
        ch = OPSDHouseholdChannels.for_household(household)
        cols.extend([ch.grid_import, ch.grid_export, ch.pv])
    return cols


def build_inventory_from_frame(
    df: pd.DataFrame,
    *,
    min_daily_coverage: float = 0.95,
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    rows = []
    qa: dict[str, dict[str, int]] = {}
    expected_bins = 720

    for household in OPSD_OOD_HOUSEHOLDS:
        native = native_net_profile(df, household)
        replay = replay_profile_2min(native)
        blocks = complete_day_blocks(
            replay, min_coverage=min_daily_coverage
        )
        valid_native = int(native["valid_native_interval"].sum())
        qa[household] = {
            "raw_rows": int(len(native)),
            "valid_native_intervals": valid_native,
            "replay_bins": int(len(replay)),
            "eligible_days": int(len(blocks)),
        }
        for date, block in blocks.items():
            n = int(len(block))
            rows.append(
                {
                    "household": household,
                    "utc_date": str(date),
                    "n_replay_bins": n,
                    "coverage": n / expected_bins,
                    "first_timestamp": pd.Timestamp(
                        block["timestamp"].iloc[0]
                    ).isoformat(),
                    "last_timestamp": pd.Timestamp(
                        block["timestamp"].iloc[-1]
                    ).isoformat(),
                }
            )

    manifest = pd.DataFrame(rows, columns=MANIFEST_COLUMNS)
    if manifest.empty:
        raise RuntimeError(
            "strict OPSD OOD policy produced zero eligible household-days"
        )
    if manifest.duplicated(["household", "utc_date"]).any():
        raise RuntimeError("duplicate household/day rows in OPSD inventory")
    return manifest, qa


def build_inventory_from_locked_zip(
    zip_path: Path,
    *,
    artifact_lock: dict,
    min_daily_coverage: float = 0.95,
) -> tuple[pd.DataFrame, dict]:
    observed = verify_locked_identity(zip_path, artifact_lock)
    csv_member = observed["resolved_members"][
        "household_data_1min_singleindex.csv"
    ]
    usecols = required_usecols()

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(csv_member) as fh:
            df = pd.read_csv(
                fh,
                usecols=usecols,
                low_memory=False,
            )

    manifest, qa = build_inventory_from_frame(
        df, min_daily_coverage=min_daily_coverage
    )
    summary = {
        "stage": "OPSD_OOD_ELIGIBLE_DAY_INVENTORY_ONLY",
        "claim_boundary": (
            "Data eligibility/QA only. No controller, optimizer or OOD "
            "performance metric is computed."
        ),
        "artifact_sha256": observed["sha256"],
        "artifact_byte_size": observed["byte_size"],
        "package_version": observed["package_version"],
        "households": list(OPSD_OOD_HOUSEHOLDS),
        "native_cadence_minutes": 1,
        "replay_cadence_minutes": 2,
        "min_daily_coverage": float(min_daily_coverage),
        "manifest_rows": int(len(manifest)),
        "manifest_sha256": manifest_sha256(manifest),
        "per_household_qa": qa,
    }
    return manifest, summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Generate strict hash-locked OPSD OOD eligible-day inventory"
    )
    p.add_argument("--zip", dest="zip_path", type=Path, required=True)
    p.add_argument("--artifact-lock-json", type=Path, required=True)
    p.add_argument("--output-csv", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    lock = json.loads(
        args.artifact_lock_json.read_text(encoding="utf-8")
    )
    manifest, summary = build_inventory_from_locked_zip(
        args.zip_path,
        artifact_lock=lock,
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.write_bytes(_canonical_manifest_bytes(manifest))
    args.output_json.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
