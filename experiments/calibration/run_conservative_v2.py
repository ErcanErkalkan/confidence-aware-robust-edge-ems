"""Predeclared known-truth synthetic CAL-v2 stress driver.

Creates a new output directory and writes the complete plan BEFORE drawing
samples. No operational data, prospective EMS experiment, or gate approval.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

import numpy as np
from scipy.stats import binomtest

from crmt_edge_ems.contracts import ContractError, digest, file_hash, integer, pareto_mask
from crmt_edge_ems.calibration.conservative_v2 import (
    FIXED_CANDIDATES, IID_ASSUMPTION, KNOWN_SUPPORT, METHOD_ID,
    calibrate_conservative, known_truth_metrics,
)

SCENARIOS = (
    {"id": "IID_UNIFORM_COMMON_SUPPORT", "days": 64, "candidates": 12,
     "inverters": 2, "law": "uniform", "support": "common", "assumption": IID_ASSUMPTION},
    {"id": "IID_PERFECT_WITHIN_DAY_CORRELATION", "days": 64, "candidates": 12,
     "inverters": 2, "law": "common_uniform", "support": "known_specific", "assumption": IID_ASSUMPTION},
    {"id": "IID_BERNOULLI_SMALL_SAMPLE", "days": 16, "candidates": 12,
     "inverters": 2, "law": "bernoulli", "support": "known_specific", "assumption": IID_ASSUMPTION},
    {"id": "IID_SMALL_SAMPLE_TRADEOFF", "days": 8, "candidates": 12,
     "inverters": 2, "law": "tradeoff", "support": "known_specific", "assumption": IID_ASSUMPTION},
    {"id": "DEPENDENT_MARKOV_DAYS_REJECTED", "days": 64, "candidates": 12,
     "inverters": 2, "law": "markov", "support": "known_specific", "assumption": "DEPENDENT_DAY_VECTORS"},
    {"id": "NONSTATIONARY_DAYS_REJECTED", "days": 64, "candidates": 12,
     "inverters": 2, "law": "shift", "support": "known_specific", "assumption": "NONSTATIONARY_DAY_VECTORS"},
)


def _write(path, payload):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def _panel(scenario, rng, *, q, weight):
    n, c, i = (scenario[key] for key in ("days", "candidates", "inverters"))
    t = np.linspace(0.05, 0.65, c)
    if scenario["law"] == "tradeoff":
        a = np.stack((t, 0.7-t, t, 0.7-t), axis=1)
        width = np.full((c, 4), 0.02)
    else:
        a = np.repeat(t[:, None], 4, axis=1)
        width = np.full((c, 4), 0.1)
    law = scenario["law"]
    if law in {"uniform", "tradeoff"}:
        u = rng.random((n, c, i, 4))
        truth = (1+weight)*a + width*(0.5 + weight*(1+q)/2)
    elif law == "common_uniform":
        u = np.broadcast_to(rng.random((n, 1, 1, 1)), (n, c, i, 4))
        truth = (1+weight)*a + width*(0.5 + weight*(1+q)/2)
    else:
        p = 0.3
        if law == "bernoulli":
            u = (rng.random((n, c, i, 4)) < p).astype(float)
        elif law == "markov":
            # Stationary Bernoulli(.3) marginals, serial dependence across days.
            state = float(rng.random() < p)
            chain = []
            for _ in range(n):
                if rng.random() < 0.1:
                    state = float(rng.random() < p)
                chain.append(state)
            u = np.broadcast_to(np.asarray(chain)[:, None, None, None], (n, c, i, 4))
        elif law == "shift":
            probabilities = np.where(np.arange(n) < n//2, 0.1, 0.9)
            u = (rng.random((n, c, i, 4)) < probabilities[:, None, None, None]).astype(float)
            p = 0.9  # Declared post-shift target, not an IID calibration population.
        else:
            raise ValueError("unrecognized frozen scenario")
        truth = (1+weight)*a + width*(p + weight*min(1, p/(1-q)))
    panel = a[None, :, None, :] + width[None, :, None, :]*u
    if scenario["support"] == "common":
        lower, upper = 0.0, 1.0
    else:
        lower, upper = a[:, None, :], (a+width)[:, None, :]
    return panel, truth, lower, upper


def _measure(call):
    tracemalloc.start()
    cpu = time.process_time()
    wall = time.perf_counter()
    try:
        result, error = call(), None
    except ContractError as exc:
        result, error = None, str(exc)
    elapsed = time.perf_counter()-wall
    cpu_elapsed = time.process_time()-cpu
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, error, {
        "calibration_wall_seconds": elapsed,
        "calibration_cpu_seconds": cpu_elapsed,
        "peak_python_traced_bytes": peak,
        "process_peak_rss_bytes": None,
        "rss_reason": "RSS not measured by this portable driver; traced bytes are not RSS",
        "simulator_event_count": 0,
        "bootstrap_draws": 0,
    }


def run(out, *, repetitions=80, seed=20261028):
    repetitions = integer(repetitions, "repetitions", 1)
    seed = integer(seed, "seed")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    config = {
        "protocol_id": "CAL-v2-BOUNDED-IID-SYNTHETIC-PLAN-20261028",
        "scope": "PREDECLARED_SYNTHETIC_ENGINEERING_STUDY_NOT_FIELD_CALIBRATION",
        "repetitions": repetitions, "seed": seed, "alpha": 0.05,
        "q": 0.9, "tail_weight": 0.5, "capacity": 10,
        "scenarios": list(SCENARIOS), "candidate_policy": FIXED_CANDIDATES,
        "support_origin": KNOWN_SUPPORT,
        "methods": [METHOD_ID, "ABSTAIN_NO_ELIMINATION"],
        "rejected_regime_policy": "Do not produce CAL-v2 intervals under unsupported assumptions",
        "selection_policy": None,
        "cost_scope": "Calibration call only; data generation/serialization excluded; tracing overhead included",
        "SUBMISSION_READY": False, "CALIBRATION_SCIENTIFICALLY_VALIDATED": False,
    }
    # No random generator is constructed and no sample is drawn before this write.
    _write(out/"PREDECLARED_CONFIG.json", config)
    config_hash = file_hash(out/"PREDECLARED_CONFIG.json")
    rows = []
    for scenario_index, scenario in enumerate(SCENARIOS):
        for repetition in range(repetitions):
            rng = np.random.default_rng(np.random.SeedSequence([seed, scenario_index, repetition]))
            panel, truth, lower, upper = _panel(
                scenario, rng, q=config["q"], weight=config["tail_weight"],
            )
            candidate_ids = [f"c{j:03d}" for j in range(scenario["candidates"])]
            day_ids = [f"day{j:04d}" for j in range(scenario["days"])]
            result, error, cost = _measure(lambda: calibrate_conservative(
                panel, day_ids=day_ids, candidate_ids=candidate_ids,
                support_lower=lower, support_upper=upper,
                assumption=scenario["assumption"], candidate_policy=FIXED_CANDIDATES,
                support_origin=KNOWN_SUPPORT, alpha=config["alpha"], q=config["q"],
                tail_weight=config["tail_weight"], capacity=config["capacity"],
            ))
            expected_rejection = scenario["assumption"] != IID_ASSUMPTION
            row = {
                "scenario": scenario["id"], "repetition": repetition,
                "method": METHOD_ID, "scope": "KNOWN_TRUTH_SYNTHETIC_ONLY",
                "config_sha256": config_hash,
                "status": "REJECTED_UNSUPPORTED_ASSUMPTION" if error else "EVALUATED_CONDITIONAL_IID",
                "expected_rejection": expected_rejection, "failure_reason": error,
                "truth_sha256": digest(truth.tolist()), **cost,
            }
            if error and not expected_rejection:
                raise RuntimeError(f"valid frozen regime failed: {scenario['id']}: {error}")
            if not error and expected_rejection:
                raise RuntimeError("unsupported regime unexpectedly admitted")
            if result is not None:
                row.update(known_truth_metrics(result, truth))
                row["input_sha256"] = result.input_sha256
                row["dkw_epsilon"] = result.dkw_epsilon
            rows.append(row)
            # A separate no-elimination comparator: full retention is not K10 utility.
            retained, _, baseline_cost = _measure(
                lambda: np.ones(len(candidate_ids), dtype=bool)
            )
            front = pareto_mask(truth)
            baseline = {
                "family_risk_undercoverage": False,
                "family_difference_undercoverage": False,
                "false_dominance_declaration": False,
                "false_pareto_removal": False,
                "true_pareto_retention": 1.0,
                "archive_overflow": int(retained.sum()) > config["capacity"],
                "archive_size": int(retained.sum()),
                "true_pareto_size": int(front.sum()), "selection_fidelity": None,
                "selection_fidelity_reason": "No elimination or K-shortlist; unbounded vacuous intervals",
            }
            rows.append({
                "scenario": scenario["id"], "repetition": repetition,
                "method": "ABSTAIN_NO_ELIMINATION", "scope": "KNOWN_TRUTH_SYNTHETIC_ONLY",
                "config_sha256": config_hash, "status": "VACUOUS_BOUNDS_NO_UTILITY_CLAIM",
                "expected_rejection": False, "failure_reason": None,
                "truth_sha256": digest(truth.tolist()), **baseline, **baseline_cost,
            })
    columns = sorted({key for row in rows for key in row})
    with (out/"synthetic_records.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    groups = []
    for scenario in SCENARIOS:
        for method in config["methods"]:
            records = [
                row for row in rows
                if row["scenario"] == scenario["id"] and row["method"] == method
            ]
            accepted = [row for row in records if "family_risk_undercoverage" in row]
            item = {
                "scenario": scenario["id"], "method": method,
                "attempts": len(records), "evaluated_known_truth_records": len(accepted),
                "unsupported_rejections": sum(
                    row["status"] == "REJECTED_UNSUPPORTED_ASSUMPTION" for row in records
                ),
                "mean_calibration_wall_seconds": float(np.mean([
                    row["calibration_wall_seconds"] for row in records
                ])),
                "mean_calibration_cpu_seconds": float(np.mean([
                    row["calibration_cpu_seconds"] for row in records
                ])),
                "maximum_python_traced_bytes": max(row["peak_python_traced_bytes"] for row in records),
                "selection_fidelity": None,
            }
            for metric in (
                "family_risk_undercoverage", "family_difference_undercoverage",
                "false_dominance_declaration", "false_pareto_removal", "archive_overflow",
            ):
                if accepted:
                    count = sum(bool(row[metric]) for row in accepted)
                    ci = binomtest(count, len(accepted)).proportion_ci(confidence_level=0.95)
                    item[metric] = {
                        "count": count, "n": len(accepted), "rate": count/len(accepted),
                        "binomial_ci95": [float(ci.low), float(ci.high)],
                    }
                else:
                    item[metric] = None
            item["mean_true_pareto_retention"] = (
                float(np.mean([row["true_pareto_retention"] for row in accepted]))
                if accepted else None
            )
            groups.append(item)
    summary = {
        "status": "SYNTHETIC_CONDITIONAL_BOUND_AND_REJECTION_EVIDENCE_ONLY",
        "CALIBRATION_SCIENTIFICALLY_VALIDATED": False,
        "real_data_validation": False, "prospective_experiment_executed": False,
        "conditional_iid_bound_implemented": True,
        "config_sha256": config_hash, "records": len(rows),
        "groups": groups,
        "limits": [
            "No inferred IID validity for OpenCEM or any real distribution shift",
            "Abstention and overflow are not a solved capacity-constrained selection method",
            "Known-truth synthetic rates do not validate field calibration",
            "No K-shortlist selection fidelity is estimated",
            "Peak traced allocation is not process RSS or hardware energy",
        ],
        "environment": {
            "python": sys.version, "platform": platform.platform(),
            "processor": platform.processor(), "logical_cpu_count": os.cpu_count(),
            "numpy": np.__version__, "github_commit_environment": os.environ.get("GITHUB_SHA"),
        },
    }
    _write(out/"CALIBRATION_VALIDATION.json", summary)
    _write(out/"SUMMARY.json", summary)
    with (out/"RESULTS.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        path.name: file_hash(path)
        for path in sorted(out.iterdir()) if path.is_file()
    }
    _write(out/"ARTIFACT_MANIFEST_SHA256.json", manifest)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20261028)
    args = parser.parse_args()
    result = run(args.out, repetitions=args.repetitions, seed=args.seed)
    print(json.dumps({
        "status": result["status"], "records": result["records"],
        "out": str(args.out), "CALIBRATION_SCIENTIFICALLY_VALIDATED": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
