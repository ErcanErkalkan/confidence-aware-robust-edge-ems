"""New comparative sensitivity; frozen CAL-v2 evidence is reused, not replaced."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from crmt_edge_ems.contracts import ContractError, file_hash, pareto_mask
from crmt_edge_ems.profiling import peak_rss_bytes
from crmt_edge_ems.calibration.conservative_v2 import (
    calibrate_conservative, FIXED_CANDIDATES, IID_ASSUMPTION, KNOWN_SUPPORT,
)
from crmt_edge_ems.calibration.comparative_v3 import (
    day_bootstrap, diagnostics, filter_day_bootstrap, risk_day_panel,
)

SCENARIOS = [
    "IID_CLEAR_KNOWN_SPECIFIC_SUPPORT", "IID_CLEAR_COMMON_SUPPORT",
    "IID_NEAR_PARETO", "IID_FLAT_ALL_PARETO",
    "SERIAL_REFRESH_005", "SHIFT_POST_TARGET",
]
METHODS = ["CAL_V2_K10", "CAL_V2_K24", "CAL_V2_CAPACITY_ABSTAIN",
           "DAY_UNADJUSTED", "DAY_BONFERRONI", "DAY_MAXT",
           "BLOCK8_MAXT", "BLOCK16_MAXT", "ABSTAIN_NO_ELIMINATION"]


def write_json(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        if path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_csv(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        if path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _checkpoint_value(value):
    if value == "":
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def read_scenario_checkpoint(path, *, scenario, repetitions):
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        rows = [{key: _checkpoint_value(value) for key, value in row.items()}
                for row in csv.DictReader(stream)]
    expected = {(scenario, repetition, method)
                for repetition in range(repetitions) for method in METHODS}
    actual = [(row.get("scenario"), row.get("repetition"), row.get("method"))
              for row in rows]
    if len(rows) != len(expected) or len(set(actual)) != len(actual) or set(actual) != expected:
        raise ContractError("scenario checkpoint is incomplete, duplicated, or mismatched")
    return rows


def fixture(name, rng):
    n, c, i = 64, 12, 2
    width = np.full((c, 4), .1)
    a = np.repeat(np.linspace(.05, .65, c)[:, None], 4, axis=1)
    if "NEAR" in name or "SERIAL" in name:
        t = np.linspace(.1, .2, 4)
        a = np.vstack([np.stack((t, .3-t, t, .3-t), axis=1),
                       np.full((8, 4), .18)])
        width[:] = .5
    if "FLAT" in name:
        a[:] = .2
        width[:] = .5
    if name == "SERIAL_REFRESH_005":
        u = np.empty((n, c, i, 4))
        u[0] = rng.random((c, i, 4))
        for day in range(1, n):
            u[day] = np.where(rng.random((c, i, 4)) < .05,
                              rng.random((c, i, 4)), u[day-1])
    else:
        u = rng.random((n, c, i, 4))
    truth = 1.5*a+width*(.5+.5*.95)
    if name == "SHIFT_POST_TARGET":
        a[:] = .1
        width[:] = .5
        previous = np.linspace(.15, .85, c)[:, None, None]
        post = 1-previous
        probabilities = np.broadcast_to(previous, (n, c, i, 4)).copy()
        probabilities[-16:] = post
        u = (u < probabilities).astype(float)
        truth = np.broadcast_to(1.5*a+width*(post[:, 0, :]+.5), (c, 4)).copy()
    samples = a[None, :, None, :]+width[None, :, None, :]*u
    if name == "IID_CLEAR_COMMON_SUPPORT":
        lower, upper = 0., 1.
    else:
        lower, upper = a[:, None, :], (a+width)[:, None, :]
    assumption = IID_ASSUMPTION
    if name == "SERIAL_REFRESH_005":
        assumption = "DEPENDENT_DAY_VECTORS"
    if name == "SHIFT_POST_TARGET":
        assumption = "NONSTATIONARY_DAY_VECTORS"
    return samples, truth, lower, upper, assumption


def timed(call):
    wall, cpu = time.perf_counter(), time.process_time()
    value = call()
    return value, time.perf_counter()-wall, time.process_time()-cpu


def compare(samples, *, truth, lower, upper, assumption, seed, n_boot,
            chronology=None, methods=METHODS):
    n, c, _, _ = samples.shape
    rows = []
    if any(method.startswith("CAL_V2") for method in methods):
        try:
            cal, wall, cpu = timed(lambda: calibrate_conservative(
                samples, day_ids=[f"d{j}" for j in range(n)],
                candidate_ids=[f"c{j}" for j in range(c)],
                support_lower=lower, support_upper=upper,
                assumption=assumption, candidate_policy=FIXED_CANDIDATES,
                support_origin=KNOWN_SUPPORT, capacity=10,
            ))
            rejected = None
        except ContractError as exc:
            cal, rejected, wall, cpu = None, str(exc), 0., 0.
        for method in methods:
            if not method.startswith("CAL_V2"):
                continue
            if cal is None:
                stats = diagnostics(np.ones(c, bool), np.zeros((c, c), bool),
                                    np.full((c, c, 4), np.inf),
                                    capacity=24 if method == "CAL_V2_K24" else 10,
                                    truth=truth)
                stats.update(family_coverage=None, abstention=True,
                             status="REJECTED_UNSUPPORTED_REGIME", rejection_reason=rejected)
            else:
                stats = diagnostics(cal.retained, cal.declarations, cal.upper_differences,
                                    capacity=24 if method == "CAL_V2_K24" else 10,
                                    truth=truth, abstain_on_overflow=method.endswith("ABSTAIN"))
                stats.update(status="CONDITIONAL_IID_ONLY", rejection_reason=None,
                             dkw_epsilon=cal.dkw_epsilon)
            rows.append(dict(method=method, calibration_wall_seconds=wall,
                             calibration_cpu_seconds=cpu, shared_bootstrap_wall_seconds=0.,
                             shared_bootstrap_cpu_seconds=0., bootstrap_tail_resolution_sufficient=True,
                             **stats))
    for length in (1, 8, 16):
        names = {1: [("DAY_UNADJUSTED", "unadjusted"), ("DAY_BONFERRONI", "bonferroni"),
                     ("DAY_MAXT", "maxT")],
                 8: [("BLOCK8_MAXT", "maxT")], 16: [("BLOCK16_MAXT", "maxT")]}[length]
        names = [(name, method) for name, method in names if name in methods]
        if not names:
            continue
        boot, bwall, bcpu = timed(lambda: day_bootstrap(
            samples, n_boot=n_boot, seed=seed+length, block_length=length,
            chronology=chronology,
        ))
        for name, method in names:
            result, wall, cpu = timed(lambda: filter_day_bootstrap(boot, method=method))
            stats = diagnostics(result["retained"], result["declarations"],
                                result["upper_differences"], truth=truth)
            rows.append(dict(method=name, status="EXPLORATORY_NO_THEOREM",
                             calibration_wall_seconds=wall, calibration_cpu_seconds=cpu,
                             shared_bootstrap_wall_seconds=bwall, shared_bootstrap_cpu_seconds=bcpu,
                             bootstrap_tail_resolution_sufficient=result["bootstrap_tail_resolution_sufficient"],
                             **stats))
    if "ABSTAIN_NO_ELIMINATION" in methods:
        rows.append(dict(method="ABSTAIN_NO_ELIMINATION", status="VACUOUS_RETENTION_ONLY",
                         calibration_wall_seconds=0., calibration_cpu_seconds=0.,
                         shared_bootstrap_wall_seconds=0., shared_bootstrap_cpu_seconds=0.,
                         bootstrap_tail_resolution_sufficient=True,
                         **diagnostics(np.ones(c, bool), np.zeros((c, c), bool),
                                       np.full((c, c, 4), np.inf), truth=truth)))
        rows[-1]["abstention"] = True
    return rows


def historical_sensitivity(path, *, n_boot, seed):
    """A predeclared lexical subset of historical TRAIN; unknown truth stays null."""
    data = pd.read_csv(path)
    if set(data["split"].str.lower()) != {"train"}:
        raise ContractError("historical sensitivity is restricted to TRAIN")
    candidates = sorted(data.candidate_id.unique())[:12]
    data = data[data.candidate_id.isin(candidates)].copy()
    if data.duplicated(["candidate_id", "block_id"]).any():
        raise ContractError("duplicate historical candidate/block")
    parsed = data.block_id.str.extract(r"^opencem:inv([12]):(\d{4}-\d{2}-\d{2})$")
    if parsed.isna().any().any():
        raise ContractError("unrecognized historical inverter/day")
    data["inverter"], data["day"] = parsed[0].to_numpy(), parsed[1].to_numpy()
    counts = data.groupby("day").size()
    dates = sorted(counts[counts == len(candidates)*2].index)
    columns = ["cap_violation_pct_total", "lfp_cycle_loss_pct", "ramp95_kw_per_min", "flip_per_day"]
    grid = pd.MultiIndex.from_product([dates, candidates, ["1", "2"]], names=["day", "candidate_id", "inverter"])
    values = data.set_index(["day", "candidate_id", "inverter"])[columns].reindex(grid)
    if values.isna().any().any():
        raise ContractError("incomplete historical joint day panel")
    panel = values.to_numpy().reshape(len(dates), len(candidates), 2, 4)
    rows = compare(panel, truth=None, lower=0., upper=1., assumption="UNVERIFIED_REAL_DAY_DEPENDENCE",
                   seed=seed, n_boot=n_boot, methods=["CAL_V2_K10", "DAY_UNADJUSTED", "DAY_BONFERRONI", "DAY_MAXT", "ABSTAIN_NO_ELIMINATION"])
    empirical_front = pareto_mask(risk_day_panel(panel))
    for row in rows:
        row.update(scenario="HISTORICAL_TRAIN_LEXICAL12", repetition=0,
                   evidence_category="HISTORICAL_TRAIN_RESAMPLING_NOT_NEW_EMS",
                   candidate_count=len(candidates), support_days=len(dates),
                   support_inverters=2, known_truth=False,
                   dependence_regime="UNVERIFIED_REAL_DAY_DEPENDENCE",
                   historical_file=str(path), historical_file_sha256=file_hash(path),
                   empirical_reference_front_size=int(empirical_front.sum()),
                   reference_front_scope="Same finite panel; not known population Pareto truth",
                   historical_tail_weight=.5,
                   metric_scope="LEGACY_METRICS_REWEIGHTED_FOR_SENSITIVITY_NOT_ORIGINAL_OPTIMIZER_RISK")
    return rows, {"candidates": candidates, "dates": dates, "selected_rows": len(grid),
                  "excluded_unbalanced_rows": len(data)-len(grid),
                  "chronological_gaps": int(np.sum(np.diff(np.asarray(dates, dtype="datetime64[D]")).astype(int) != 1)),
                  "block_bootstrap_not_run": "Missing calendar-day support cannot be compressed into consecutive blocks"}


def run(out, *, repetitions=60, n_boot=399, seed=2026102806, historical=None):
    out = Path(out)
    plan = dict(version="CAL-COMPARATIVE-v3-20261028", synthetic_only=True,
                repetitions=repetitions, n_boot=n_boot, seed=seed, scenarios=SCENARIOS,
                methods=METHODS, days=64, candidates=12, inverters=2, alpha=.05,
                q=.9, tail_weight=.5, capacities=[10, 24],
                whole_day_resampling=True, block_lengths=[8, 16],
                false_elimination="At least one true population Pareto member removed",
                coverage="All ordered true risk differences below the simultaneous upper bounds",
                overflow="Retained archive size greater than stated capacity; no forced truncation",
                cost="Filter/calibration CPU+wall; bootstrap phase separate and shared across comparator filters; process RSS is lifetime high-water mark",
                historical_selection="Lexically first12 candidates; all joint complete two-inverter days; TRAIN only",
                historical=str(historical) if historical else None,
                execution_commit=None, execution_commit_reason="Uncommitted source; source hashes identify actual code",
                base_git_reference=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                source_sha256={str(p.relative_to(ROOT)): file_hash(p) for p in [Path(__file__), ROOT/"src/crmt_edge_ems/calibration/comparative_v3.py", ROOT/"src/crmt_edge_ems/calibration/conservative_v2.py"]},
                CALIBRATION_SCIENTIFICALLY_VALIDATED=False)
    out.mkdir(parents=True, exist_ok=True)
    plan_path = out/"PREDECLARED_COMPARATIVE_PLAN.json"
    verification_path = out/"CAL_V2_CHECKPOINT_VERIFICATION_RECEIPT.json"
    plan_keys = ("version", "synthetic_only", "repetitions", "n_boot", "seed",
                 "scenarios", "methods", "days", "candidates", "inverters",
                 "alpha", "q", "tail_weight", "capacities",
                 "whole_day_resampling", "block_lengths", "historical_selection",
                 "historical", "base_git_reference", "execution_commit",
                 "execution_commit_reason", "CALIBRATION_SCIENTIFICALLY_VALIDATED")
    if plan_path.exists():
        previous_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if any(previous_plan.get(key) != plan[key] for key in plan_keys):
            raise ContractError("existing comparative plan differs from requested design")
        checkpoint_paths = [out/f"CHECKPOINT_{i:02d}.csv" for i in range(len(SCENARIOS))]
        present = [path for path in checkpoint_paths if path.exists()]
        if present:
            if not verification_path.is_file():
                raise ContractError("existing checkpoints lack a verification receipt")
            verification = json.loads(verification_path.read_text(encoding="utf-8-sig"))
            if verification.get("plan_sha256") != file_hash(plan_path):
                raise ContractError("verified plan hash changed")
            if verification.get("source_hashes") != previous_plan.get("source_sha256"):
                raise ContractError("checkpoint source receipt differs from frozen plan")
            for path in present:
                if verification.get("checkpoint_hashes", {}).get(path.name) != file_hash(path):
                    raise ContractError("verified checkpoint hash changed")
            for key, value in previous_plan["source_sha256"].items():
                if key.replace("\\", "/") != "experiments/calibration/run_comparative_v3.py":
                    if plan["source_sha256"].get(key) != value:
                        raise ContractError("calibration implementation changed since checkpoint")
            if historical is not None:
                if verification.get("historical_input_sha256") != file_hash(Path(historical)):
                    raise ContractError("historical TRAIN input changed since checkpoint")
        if any((out/name).exists() for name in (
                "COMPARATIVE_PER_REPETITION.csv", "CAL_V2_COMPARATIVE_EXPERIMENTS.csv",
                "CAL_V2_OVERFLOW_ANALYSIS.csv", "CAL_V2_ASSUMPTION_MATRIX.csv")):
            raise ContractError("final outputs already exist; refusing to overwrite")
        plan = previous_plan
    else:
        write_json(plan_path, plan)

    rows = []
    resumed_scenarios = []
    for si, scenario in enumerate(SCENARIOS):
        checkpoint = out/f"CHECKPOINT_{si:02d}.csv"
        if checkpoint.exists():
            restored = read_scenario_checkpoint(
                checkpoint, scenario=scenario, repetitions=repetitions)
            rows.extend(restored)
            resumed_scenarios.append(scenario)
            print(f"{scenario}: restored verified checkpoint", flush=True)

    for si, scenario in enumerate(SCENARIOS):
        if scenario in resumed_scenarios:
            continue
        for rep in range(repetitions):
            rng = np.random.default_rng(np.random.SeedSequence([seed, si, rep]))
            panel, truth, lower, upper, assumption = fixture(scenario, rng)
            for row in compare(panel, truth=truth, lower=lower, upper=upper,
                               assumption=assumption, seed=seed+si*10000+rep,
                               n_boot=n_boot, chronology=np.arange(len(panel))):
                row.update(scenario=scenario, repetition=rep, known_truth=True,
                           evidence_category="KNOWN_TRUTH_SYNTHETIC_COMPARISON",
                           support_days=len(panel), candidate_count=panel.shape[1],
                           dependence_regime=assumption,
                           process_peak_rss_bytes=peak_rss_bytes())
                rows.append(row)
        print(f"{scenario}: {repetitions} repetitions completed", flush=True)
        checkpoint_rows = [r for r in rows if r["scenario"] == scenario]
        write_csv(out/f"CHECKPOINT_{si:02d}.csv", checkpoint_rows)
    historical_metadata = None
    if historical:
        history_rows, historical_metadata = historical_sensitivity(Path(historical), n_boot=n_boot, seed=seed)
        rows.extend(history_rows)
    write_csv(out/"COMPARATIVE_PER_REPETITION.csv", rows)
    summary = []
    for scenario in sorted(set(r["scenario"] for r in rows)):
        for method in sorted(set(r["method"] for r in rows if r["scenario"] == scenario)):
            group = [r for r in rows if r["scenario"] == scenario and r["method"] == method]
            record = dict(scenario=scenario, method=method, attempts=len(group),
                          known_truth=group[0]["known_truth"],
                          rejected=sum(r["status"] == "REJECTED_UNSUPPORTED_REGIME" for r in group),
                          mean_archive_size=float(np.mean([r["archive_size"] for r in group])),
                          mean_retained_pareto_fraction=None,
                          mean_calibration_cpu_seconds=float(np.mean([r["calibration_cpu_seconds"] for r in group])),
                          mean_calibration_wall_seconds=float(np.mean([r["calibration_wall_seconds"] for r in group])),
                          mean_shared_bootstrap_cpu_seconds=float(np.mean([r["shared_bootstrap_cpu_seconds"] for r in group])),
                          mean_shared_bootstrap_wall_seconds=float(np.mean([r["shared_bootstrap_wall_seconds"] for r in group])),
                          max_process_peak_rss_bytes=max(
                              (r.get("process_peak_rss_bytes") or 0) for r in group),
                          inadequate_bootstrap_tail_resolution=sum(not r["bootstrap_tail_resolution_sufficient"] for r in group))
            retention = [r["retained_pareto_fraction"] for r in group if r["retained_pareto_fraction"] is not None]
            if retention:
                record["mean_retained_pareto_fraction"] = float(np.mean(retention))
            for key in ("false_elimination", "family_coverage", "false_dominance", "archive_overflow", "abstention"):
                vals = [r[key] for r in group if r[key] is not None]
                count = sum(vals)
                ci = binomtest(count, len(vals)).proportion_ci() if vals else None
                record.update({f"{key}_n": len(vals), f"{key}_count": count if vals else None,
                               f"{key}_rate": count/len(vals) if vals else None,
                               f"{key}_ci95_low": float(ci.low) if ci else None,
                               f"{key}_ci95_high": float(ci.high) if ci else None})
            summary.append(record)
    write_csv(out/"CAL_V2_COMPARATIVE_EXPERIMENTS.csv", summary)
    write_csv(out/"CAL_V2_OVERFLOW_ANALYSIS.csv", [
        {k: v for k, v in r.items() if "overflow" in k or "abstention" in k or k in ("scenario", "method", "attempts", "mean_archive_size", "mean_retained_pareto_fraction", "known_truth", "rejected")}
        for r in summary])
    assumption_matrix = []
    dependence_labels = {
        "IID_CLEAR_KNOWN_SPECIFIC_SUPPORT": "IID, known candidate-specific bounded support",
        "IID_CLEAR_COMMON_SUPPORT": "IID, common [0,1] support",
        "IID_NEAR_PARETO": "IID, near Pareto ties and broad support",
        "IID_FLAT_ALL_PARETO": "IID, flat risk vectors; all candidates Pareto",
        "SERIAL_REFRESH_005": "Serial day dependence; 0.05 refresh probability",
        "SHIFT_POST_TARGET": "Nonstationary target; post-shift population differs",
        "HISTORICAL_TRAIN_LEXICAL12": "Historical TRAIN; dependence and population truth unverified",
    }
    for scenario in sorted(set(row["scenario"] for row in rows)):
        scenario_rows = [row for row in rows if row["scenario"] == scenario]
        for method in sorted(set(row["method"] for row in scenario_rows)):
            group = [row for row in scenario_rows if row["method"] == method]
            assumption_matrix.append({
                "scenario": scenario, "method": method,
                "dependence_regime": dependence_labels.get(scenario, "UNSPECIFIED"),
                "method_assumption": ("CAL-v2 conditional IID theorem assumptions"
                                      if method.startswith("CAL_V2")
                                      else "Whole-day paired bootstrap; block length 8/16 where named"
                                      if method.startswith(("DAY_", "BLOCK"))
                                      else "No-elimination abstention baseline"),
                "known_population_truth": bool(group[0]["known_truth"]),
                "support_days": group[0].get("support_days"),
                "repetitions": len(group),
                "dependence_sensitivity_scope": "DESIGNED_SYNTHETIC_STRESS_NOT_FIELD_VALIDATION",
            })
    write_csv(out/"CAL_V2_ASSUMPTION_MATRIX.csv", assumption_matrix)
    scope = dict(version=plan["version"], records=len(rows), synthetic_records=len(rows)-(5 if historical else 0),
                 historical_records=5 if historical else 0, historical_metadata=historical_metadata,
                 truth_scope="Analytic affine uniform or Bernoulli population risks; serial uniform marginal stationary; shifted target is post-shift population",
                 CALIBRATION_SCIENTIFICALLY_VALIDATED=False,
                 archive_wide_operational_95_guarantee=False, locked=False,
                 R19_DESIGN_APPROVED=False, R19_PROSPECTIVE_EXECUTED=False,
                 INDEPENDENT_TEST_EXECUTED=False, python=sys.version, platform=platform.platform(),
                 config_sha256=file_hash(out/"PREDECLARED_COMPARATIVE_PLAN.json"),
                 execution_commit=None, base_git_reference=plan["base_git_reference"], source_sha256=plan["source_sha256"],
                 limits=["Synthetic repeated-panel rates are Monte Carlo estimates, not real-data calibration",
                         "Rejected CAL-v2 regimes have null coverage and fail-closed full retention",
                         "Bonferroni bootstrap quantiles have inadequate family-tail resolution at399draws",
                         "No K-shortlist selection or operational utility evaluated",
                         "Historical TRAIN subset has no known population truth, verified support or IID evidence",
                         "Shared bootstrap costs must not be summed across filters as independent runs"])
    scope["resumed_scenarios"] = resumed_scenarios
    scope["newly_executed_scenarios"] = [s for s in SCENARIOS if s not in resumed_scenarios]
    scope["continuation_driver_sha256"] = file_hash(Path(__file__))
    write_json(out/"CAL_V2_SCIENTIFIC_SCOPE.json", scope)
    write_report(out/"CAL_V2_COMPARATIVE_FINAL_REPORT_TR.md", summary, plan, scope)
    output_hashes = {p.name: file_hash(p) for p in sorted(out.iterdir()) if p.is_file()
                     and p.name != "CAL_V2_EXECUTION_RECEIPT.json"}
    write_json(out/"ARTIFACT_MANIFEST_SHA256.json", output_hashes)
    write_json(out/"CAL_V2_EXECUTION_RECEIPT.json", {
        "experiment_id": plan["version"], "plan_sha256": file_hash(plan_path),
        "checkpoint_verification_receipt_sha256": (
            file_hash(verification_path) if verification_path.exists() else None),
        "completed_scenarios": list(SCENARIOS), "resumed_scenarios": resumed_scenarios,
        "newly_executed_scenarios": [s for s in SCENARIOS if s not in resumed_scenarios],
        "repetitions_per_scenario": repetitions, "bootstrap_repetitions": n_boot,
        "synthetic_rows": sum(1 for row in rows if row["evidence_category"] == "KNOWN_TRUTH_SYNTHETIC_COMPARISON"),
        "historical_rows": sum(1 for row in rows if row["evidence_category"] == "HISTORICAL_TRAIN_RESAMPLING_NOT_NEW_EMS"),
        "checkpoint_sha256": {p.name: file_hash(p) for p in sorted(out.glob("CHECKPOINT_*.csv"))},
        "output_sha256": output_hashes, "continuation_driver_sha256": file_hash(Path(__file__)),
        "CALIBRATION_SCIENTIFICALLY_VALIDATED": False,
        "archive_wide_operational_95_guarantee": False,
        "INDEPENDENT_TEST_EXECUTED": False, "R19_DESIGN_APPROVED": False,
        "R19_PROSPECTIVE_EXECUTED": False,
    })
    return scope


def write_report(path, summary, plan, scope):
    def show(value, digits=3):
        if value is None or pd.isna(value):
            return "—"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return f"{float(value):.{digits}f}"

    lines = [
        "# CAL-v2/v3 karşılaştırmalı deney — nihai rapor",
        "",
        f"Deney: `{plan['version']}`; 6 senaryo × {plan['repetitions']} tekrar; "
        f"{len(plan['methods'])} yöntem; {plan['n_boot']} bootstrap tekrar.",
        f"Bu devamda mevcut checkpoint’lerden sürdürülen senaryolar: "
        f"{', '.join(scope['resumed_scenarios']) or 'yok'}.",
        f"Yeni çalıştırılan senaryolar: {', '.join(scope['newly_executed_scenarios']) or 'yok'}.",
        "",
        "## Sonuçlar",
        "",
        "| Senaryo | Yöntem | n | Yanlış eleme | Kapsama | Pareto tutma | Taşma | Abstention | Filtre CPU s | Bootstrap wall s | Tepe RSS bayt |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['scenario']} | {row['method']} | {row['attempts']} | "
            f"{show(row.get('false_elimination_rate'))} | {show(row.get('family_coverage_rate'))} | "
            f"{show(row.get('mean_retained_pareto_fraction'))} | "
            f"{show(row.get('archive_overflow_rate'))} | {show(row.get('abstention_rate'))} | "
            f"{show(row.get('mean_calibration_cpu_seconds'))} | "
            f"{show(row.get('mean_shared_bootstrap_wall_seconds'))} | "
            f"{show(row.get('max_process_peak_rss_bytes'), 0)} |")
    lines.extend([
        "",
        "## Varsayım ve kanıt sınırları",
        "",
        "- CAL-v2 sonuçları yalnızca tasarımda belirtilen IID ve destek varsayımlarına koşulludur; sentetik bilinen-gerçeklik testleri gerçek saha verisinde bağımsız garanti doğrulaması değildir.",
        "- `SERIAL_REFRESH_005` ve `SHIFT_POST_TARGET` bağımlılık/dağılım kayması stres senaryolarıdır. Ret veya abstention, güvenilir kapsama kanıtı olarak yorumlanmamalıdır.",
        "- Gün bootstrap’ı aday ve inverter eşleşmesini birlikte korur; 399 tekrar özellikle çoklu karşılaştırmalı Bonferroni kuyruk çözünürlüğünü garanti etmez. Blok bootstrap yalnız kesintisiz sentetik takvim üzerinde keşifseldir.",
        "- Historical TRAIN satırları bilinen popülasyon Pareto gerçeği değildir; optimizer riskinin özgün yeniden üretimi veya yeni EMS çalıştırması sayılmaz.",
        "- Arşiv taşması raporlanır; hiçbir yöntem arşivi zorla budamaz. `CAL_V2_CAPACITY_ABSTAIN` taşmada seçim yapmaz.",
        "- CPU/wall/RSS, ölçülen uygulama aşaması içindir. Paylaşılan bootstrap maliyeti yöntem filtrelerine ayrı bağımsız iş gibi eklenmemelidir.",
        "",
        "## Bilimsel durum",
        "",
        "`CALIBRATION_SCIENTIFICALLY_VALIDATED=false`; `archive_wide_operational_95_guarantee=false`; "
        "`INDEPENDENT_TEST_EXECUTED=false`. Tasarım ve tekrarlar mühendislik karşılaştırmasıdır; "
        "CAL-v2 koşullu garantisinin saha doğrulaması veya prospektif doğrulama değildir.",
        "",
    ])
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write("\n".join(lines))
        if path.exists():
            raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--historical", type=Path)
    parser.add_argument("--repetitions", type=int, default=60)
    parser.add_argument("--n-boot", type=int, default=399)
    args = parser.parse_args()
    print(json.dumps(run(args.out, repetitions=args.repetitions, n_boot=args.n_boot,
                         historical=args.historical), ensure_ascii=False))
