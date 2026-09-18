from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from crmt_edge_ems.parameter_space import PARAM_NAMES, decode_unit_vector, repair_unit_vector
from crmt_edge_ems.replay import ReplayBlock, ReplayEvaluator
from crmt_edge_ems.site_model import PRIMARY_OPENCEM_CADENCE_MINUTES, build_primary_opencem_site
from data_adapters.opencem import (
    DEFAULT_CONFIRMATORY_SPLIT,
    assign_confirmatory_split,
    per_inverter_daily_blocks,
    reconstruct_per_inverter_profiles,
)
from opencem_qa import (
    KEY_COLS,
    block_manifest_sha256,
    complete_day_block_manifest,
    load_verified_csvs,
)


def _load_raw(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        header = pd.read_csv(path, nrows=0)
        cols = [c for c in KEY_COLS if c in header.columns]
        frames.append(pd.read_csv(path, usecols=cols))
    return pd.concat(frames, ignore_index=True)


def _evenly_spaced(keys: list[str], n: int) -> list[str]:
    if n <= 0:
        raise ValueError("samples_per_inverter must be > 0")
    if not keys:
        raise ValueError("no keys available")
    count = min(int(n), len(keys))
    idx = np.linspace(0, len(keys) - 1, num=count, dtype=int)
    return [keys[i] for i in sorted(set(int(x) for x in idx))]


def _midspace_params(site):
    u = np.full(len(PARAM_NAMES), 0.5, dtype=float)
    return decode_unit_vector(repair_unit_vector(u, site=site))


def run_preflight(
    paths: list[Path],
    *,
    lock: dict,
    samples_per_inverter: int = 5,
) -> dict:
    raw = _load_raw(paths)
    cadence = int(lock["cadence_minutes"])
    if cadence != PRIMARY_OPENCEM_CADENCE_MINUTES:
        raise RuntimeError("runtime lock cadence disagrees with primary protocol")

    profiles = reconstruct_per_inverter_profiles(
        raw,
        frequency=f"{cadence}min",
        expected_inverters=(1, 2),
        min_samples_per_inverter_bin=1,
    )
    blocks = per_inverter_daily_blocks(
        profiles,
        expected_frequency_minutes=cadence,
        min_coverage=float(lock["min_daily_coverage"]),
    )
    manifest = complete_day_block_manifest(blocks, cadence_minutes=cadence)
    observed_hash = block_manifest_sha256(manifest)
    if observed_hash != str(lock["canonical_csv_sha256"]):
        raise RuntimeError(
            f"block manifest hash mismatch: observed={observed_hash}, "
            f"expected={lock['canonical_csv_sha256']}"
        )
    if len(manifest) != int(lock["row_count"]):
        raise RuntimeError("block manifest row count mismatch")

    records = []
    by_inverter = {}
    for inv in (1, 2):
        assigned = assign_confirmatory_split(blocks[inv], split=DEFAULT_CONFIRMATORY_SPLIT)
        train = assigned["train"]
        dates = sorted(train)
        selected = _evenly_spaced(dates, samples_per_inverter)
        site = build_primary_opencem_site(inv)
        params = _midspace_params(site)
        evaluator = ReplayEvaluator(site, method_id="RUNTIME_PREFLIGHT")

        warm_date = selected[0]
        warm = ReplayBlock(
            f"opencem:inv{inv}:{warm_date}",
            train[warm_date],
            source="OpenCEM",
            split="train",
        )
        evaluator.evaluate(params, [warm], candidate_id=f"warmup-inv{inv}")

        inv_times = []
        for date in selected:
            block = ReplayBlock(
                f"opencem:inv{inv}:{date}",
                train[date],
                source="OpenCEM",
                split="train",
            )
            t0 = time.perf_counter()
            evaluator.evaluate(params, [block], candidate_id=f"runtime-inv{inv}-{date}")
            wall = time.perf_counter() - t0
            inv_times.append(wall)
            records.append({
                "inverter_id": inv,
                "block_id": block.block_id,
                "local_date": date,
                "n_ticks": int(len(train[date])),
                "wall_seconds": float(wall),
            })
        x = np.asarray(inv_times, dtype=float)
        by_inverter[str(inv)] = {
            "n_samples": int(x.size),
            "median_wall_seconds": float(np.median(x)),
            "p95_wall_seconds": float(np.quantile(x, 0.95)),
            "max_wall_seconds": float(np.max(x)),
            "train_block_count": int(len(train)),
        }

    all_times = np.asarray([r["wall_seconds"] for r in records], dtype=float)
    estimated_full_train_seconds = sum(
        by_inverter[str(inv)]["median_wall_seconds"]
        * by_inverter[str(inv)]["train_block_count"]
        for inv in (1, 2)
    )
    return {
        "purpose": "runtime_preflight_only",
        "claim_boundary": "No controller-performance or optimizer-quality claim.",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "manifest_sha256": observed_hash,
        "manifest_rows": int(len(manifest)),
        "cadence_minutes": cadence,
        "samples_per_inverter": int(samples_per_inverter),
        "records": records,
        "by_inverter": by_inverter,
        "overall": {
            "n_samples": int(all_times.size),
            "median_wall_seconds": float(np.median(all_times)),
            "p95_wall_seconds": float(np.quantile(all_times, 0.95)),
            "max_wall_seconds": float(np.max(all_times)),
            "estimated_one_full_train_candidate_seconds_from_inverter_medians": float(
                estimated_full_train_seconds
            ),
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="OpenCEM real-data controller-block runtime preflight")
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--lock-json", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--samples-per-inverter", type=int, default=5)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.lock_json.read_text(encoding="utf-8"))
    report = run_preflight(paths, lock=lock, samples_per_inverter=args.samples_per_inverter)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "manifest_sha256": report["manifest_sha256"],
        "samples_per_inverter": report["samples_per_inverter"],
        "by_inverter": report["by_inverter"],
        "overall": report["overall"],
        "claim_boundary": report["claim_boundary"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
