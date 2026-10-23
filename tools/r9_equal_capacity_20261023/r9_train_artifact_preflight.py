#!/usr/bin/env python3
"""Read-only fail-closed integrity check of *historical* 5x8 Gate3 TRAIN files.

Input layout: root/seed1001/C0_F0_A0/{run_summary.json,ledger.csv,
candidate_metrics.csv,optimizer_front.csv}, and equivalent cells.
This tool cannot evaluate TRAIN, VALIDATION or TEST; it does not freeze R9 design.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

OBJECTIVES = (
    "cap_violation_pct_total", "lfp_cycle_loss_pct",
    "ramp95_kw_per_min", "flip_per_day",
)
SOURCE_SHA = "be5756321617087ca421a639d60a99513f29d889"
OPENCEM_SHA = "5884d253a5267fb240b7a8df6fa9e4d49a905167"
SOURCE_MANIFEST_SHA = "3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1"
CSV_NAMES = ("ledger.csv", "candidate_metrics.csv", "optimizer_front.csv")


class PreflightBlocked(ValueError):
    """No scientific claim is allowed on incorrect or missing TRAIN inputs."""


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise PreflightBlocked(explanation)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path: Path, fields: set[str]):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        require(reader.fieldnames is not None and fields <= set(reader.fieldnames),
                str(path) + " missing required CSV columns")
        for row in reader:
            require(None not in row, str(path) + " malformed CSV row")
            yield row


def read_cell(root: Path, seed: int, c: int, f: int, a: int,
              budget: int, pool: int) -> dict:
    condition = "C%d_F%d_A%d" % (c, f, a)
    directory = root / ("seed%d" % seed) / condition
    require(directory.is_dir(), str(directory) + " missing")
    all_paths = {n: directory / n for n in ("run_summary.json",) + CSV_NAMES}
    for name, path in all_paths.items():
        require(path.is_file() and path.stat().st_size > 0,
                str(path) + " missing or empty")
    summary = json.loads(all_paths["run_summary.json"].read_text(encoding="utf-8"))
    require(isinstance(summary, dict), condition + " summary not an object")
    expected = {
        "stage": "GATE3_FACTORIAL_TRAIN_ONLY",
        "seed": seed,
        "condition_id": condition,
        "status": "EXPLORATORY",
        "source_repo": "ErcanErkalkan/confidence-aware-robust-edge-ems",
        "original_git_sha": SOURCE_SHA,
        "source_data_commit": OPENCEM_SHA,
        "canonical_manifest_sha256": SOURCE_MANIFEST_SHA,
        "candidate_count": pool,
        "train_budget_used": budget,
        "archive_mode": "confidence" if f else "risk_pareto",
        "allocation_mode": "adaptive" if a else "round_robin",
    }
    for key, value in expected.items():
        require(summary.get(key) == value, condition + ": " + key + " mismatch")
    require(math.isclose(float(summary.get("risk_q", -1)), 0.9, abs_tol=1e-12),
            condition + ": risk quantile mismatch")
    require(math.isclose(float(summary.get("risk_tail_weight", -1)),
                         0.5 if c else 0.0, abs_tol=1e-12),
            condition + ": C/risk lambda mismatch")
    require(summary.get("source_context", {}).get("split") == "train",
            condition + ": source split not TRAIN")
    expected_sha = summary.get("files_sha256", {})
    require(isinstance(expected_sha, dict), condition + ": no file digest map")
    hashes = {}
    for name in CSV_NAMES:
        got = sha256_file(all_paths[name])
        require(got == expected_sha.get(name),
                condition + ": SHA256 mismatch for " + name)
        hashes[name] = got

    pairs = set()
    method_ids = set()
    ledger_count = 0
    for row in rows(all_paths["ledger.csv"],
                    {"ordinal", "method_id", "candidate_id", "block_id", "unit"}):
        ledger_count += 1
        require(row["ordinal"] == str(ledger_count),
                condition + ": ledger sequence inconsistent")
        require(row["unit"] == "controller_block_evaluation",
                condition + ": ledger unit mismatch")
        require(row["method_id"] == "CRMT",
                condition + ": ledger method not CRMT")
        candidate = row["candidate_id"].strip()
        block = row["block_id"].strip()
        require(candidate and block and row["candidate_id"] == candidate
                and row["block_id"] == block,
                condition + ": invalid event IDs")
        pair = (candidate, block)
        require(pair not in pairs, condition + ": duplicated controller-block event")
        pairs.add(pair)
        method_ids.add(candidate)
    require(ledger_count == budget and len(method_ids) == pool,
            condition + ": actual ledger budget/pool mismatch")

    metric_values = {}
    for row in rows(all_paths["candidate_metrics.csv"],
                    {"candidate_id", "block_id", "split", *OBJECTIVES}):
        require(row["split"].casefold() == "train",
                condition + ": TEST/VAL row in TRAIN metrics")
        key = (row["candidate_id"], row["block_id"])
        require(key in pairs, condition + ": metric not in TRAIN ledger")
        require(key not in metric_values, condition + ": duplicate metric event")
        try:
            objectives = tuple(float(row[k]) for k in OBJECTIVES)
        except (ValueError, TypeError, OverflowError) as exc:
            raise PreflightBlocked(condition + ": invalid metric numeric value") from exc
        require(all(math.isfinite(x) for x in objectives),
                condition + ": nonfinite metric")
        metric_values[key] = objectives
    require(len(metric_values) == ledger_count,
            condition + ": metric/ledger event coverage mismatch")

    archive = set()
    for row in rows(all_paths["optimizer_front.csv"], {"candidate_id"}):
        candidate = row["candidate_id"].strip()
        require(candidate in method_ids, condition + ": archive candidate outside TRAIN pool")
        require(candidate not in archive, condition + ": duplicate archive member")
        archive.add(candidate)
    require(len(archive) == summary.get("archive_count"),
            condition + ": native archive size mismatch")
    return {
        "condition": condition, "seed": seed, "budget": ledger_count,
        "unique_candidates": len(method_ids), "archive_size": len(archive),
        "csv_sha256": hashes, "ledger_pairs": pairs,
        "objective_by_event": metric_values,
    }


def inspect_pair(root: Path, seed: int, c: int, a: int,
                 budget: int = 12600, pool: int = 256) -> dict:
    f0 = read_cell(root, seed, c, 0, a, budget, pool)
    f1 = read_cell(root, seed, c, 1, a, budget, pool)
    require(f0["ledger_pairs"] == f1["ledger_pairs"],
            "F0 and F1 have different TRAIN evaluation pairs")
    differences = 0
    maximum = 0.0
    for key, vec in f0["objective_by_event"].items():
        other = f1["objective_by_event"].get(key)
        require(other is not None, "F0 and F1 have different TRAIN metric event IDs")
        deviation = max(abs(x-y) for x, y in zip(vec, other))
        maximum = max(maximum, deviation)
        if deviation > 1e-12:
            differences += 1
    require(differences == 0, "F0/F1 TRAIN objective rows differ")
    return {
        "seed": seed, "C": c, "A": a, "budget_per_F_arm": budget,
        "matched_train_event_count": len(f0["ledger_pairs"]),
        "scientific_four_objective_mismatch_count": differences,
        "max_abs_objective_difference": maximum,
        "F0_archive_size": f0["archive_size"], "F1_archive_size": f1["archive_size"],
        "F0_files_sha256": f0["csv_sha256"], "F1_files_sha256": f1["csv_sha256"],
        "status": "VERIFIED_HISTORICAL_TRAIN_ONLY_NOT_R9_TEST",
    }


def inspect_all(root: Path) -> dict:
    audit = []
    for seed in range(1001, 1006):
        for c in (0, 1):
            for a in (0, 1):
                audit.append(inspect_pair(root, seed, c, a))
    require(len(audit) == 20, "historical pair count mismatch")
    return {
        "status": "HISTORICAL_TRAIN_SHA_AND_METRIC_AUDIT_ONLY",
        "independent_TEST": "NOT_RUN",
        "preregistration": "NOT_LOCKED",
        "pairs": audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=None,
                        help="Sample only one seed (requires all 4 C/A pairs); omit for 5 seeds")
    args = parser.parse_args()
    try:
        require(args.root.is_dir(), "provided TRAIN root directory is missing")
        if args.seed is None:
            outcome = inspect_all(args.root)
        else:
            require(1001 <= args.seed <= 1005, "seed must be 1001..1005")
            outcome = {
                "status": "HISTORICAL_TRAIN_SAMPLE_SHA_AND_METRIC_AUDIT_ONLY",
                "independent_TEST": "NOT_RUN",
                "pairs": [inspect_pair(args.root, args.seed, c, a)
                          for c in (0, 1) for a in (0, 1)]
            }
        require(args.output_json.resolve() != args.root.resolve(),
                "output cannot overwrite input directory")
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
        print(outcome["status"] + ": " + str(len(outcome["pairs"])) + " pairs; TEST NO-GO")
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, "R9_TRAIN_SOURCE_PREFLIGHT_BLOCKED: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
