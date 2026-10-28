#!/usr/bin/env python3
"""Checkpointed exposed TRAIN/VALIDATION engineering evidence, not original traces.

Uses the completed19-partition raw reconstruction without redownloading raw data.
No internal_TEST is executed. Candidate parameters and raw data remain private.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import platform
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "src"))
from crmt_edge_ems.contracts import ContractError, OBJECTIVES, canonical, digest, file_hash, pareto_mask
from crmt_edge_ems.metric_replay_audit import ReplayCheckpoints, trajectory_hash, verified_controller_profile
from crmt_edge_ems.metrics_v2 import compute_metrics_v2
from crmt_edge_ems.metrics_v3 import CapacityPolicy, compute_metrics_v3, METRICS_VERSION
from crmt_edge_ems.parameter_space import PARAM_NAMES, build_tuned_controller
from crmt_edge_ems.profiling import peak_rss_bytes
from crmt_edge_ems.safety import SafetyLimits, simulate_checked
from crmt_edge_ems.site_model import build_primary_opencem_site
from crmt_edge_ems.indicators import exact_hypervolume
from jer_microgrid.metrics import compute_metrics
from jer_microgrid.simulation import simulate_controller

SCOPE = "NEW_ENGINEERING_REPLAY_OF_EXPOSED_REAL_TRAIN_NOT_ORIGINAL_EXECUTION_NOT_INDEPENDENT_TEST"
BLOCKS = [f"opencem:inv{inv}:{day}" for day in ("2025-08-02", "2025-08-31") for inv in (1, 2)]
METRICS = (*OBJECTIVES, "efcrf", "idod")
VERSIONS = {"legacy": compute_metrics, "v2": compute_metrics_v2, "v3": compute_metrics_v3}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def source_identity():
    # Bind the complete imported source tree plus this driver at execution start.
    paths = sorted((SOURCE / "src").rglob("*.py")) + [Path(__file__).resolve()]
    manifest = {p.relative_to(SOURCE).as_posix(): file_hash(p) for p in paths}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip()
    return {"base_commit": head, "source_manifest_sha256": digest(manifest), "source_files": manifest,
            "execution_identity": "BASE_COMMIT_PLUS_HASHED_WORKING_SOURCE_NOT_COMMIT_ONLY"}


def load_inputs(project):
    historical = project / "02_DATASETS/05_RECOVERED_HISTORICAL_TRAIN_20261027/seed1001_C1_A1"
    evidence = project / "10_FINAL_REMEDIATION_AND_VALIDATION"
    inputs = {"full_raw_reconstruction": evidence / "14_OPENCEM_19_RAW_VALUES_20261028/FULL_292256_RECONSTRUCTED_VALUES.csv",
              "block_validation": evidence / "14_OPENCEM_19_RAW_VALUES_20261028/FULL_406_DAY_VALIDATION.csv",
              "front_F0": historical / "F0/optimizer_front.csv", "front_F1": historical / "F1/optimizer_front.csv",
              "historical_metrics": historical / "F0/candidate_metrics.csv"}
    hashes = {key: file_hash(value) for key, value in inputs.items()}
    f0, f1 = (pd.read_csv(inputs["front_" + f]) for f in ("F0", "F1"))
    for front in (f0, f1):
        if front.candidate_id.isna().any() or front.candidate_id.duplicated().any() or not set(PARAM_NAMES) <= set(front):
            raise ContractError("historical parameter identity missing or duplicate")
        if not np.isfinite(front[list(PARAM_NAMES)].to_numpy(dtype=float)).all():
            raise ContractError("historical parameters nonfinite")
    if len(f0) != 18 or len(f1) != 236 or not set(f0.candidate_id) <= set(f1.candidate_id):
        raise ContractError("expected frozen18/236 nested archive registries")
    a, b = (f.set_index("candidate_id").loc[sorted(f0.candidate_id), list(PARAM_NAMES)] for f in (f0, f1))
    if not np.array_equal(a.to_numpy(), b.to_numpy()):
        raise ContractError("F0/F1 shared candidate parameter mismatch")
    meta = pd.read_csv(inputs["block_validation"])
    if len(meta) != 406 or meta.block_id.duplicated().any() or not set(meta.split) <= {"train", "validation", "internal_test"}:
        raise ContractError("unexpected frozen block/split registry")
    raw = pd.read_csv(inputs["full_raw_reconstruction"])
    if set(raw.block_id) != set(meta.block_id):
        raise ContractError("raw reconstruction and block registry differ")
    hist = pd.read_csv(inputs["historical_metrics"])
    if hist.duplicated(["candidate_id", "block_id"]).any() or set(hist.split) != {"train"}:
        raise ContractError("invalid historical TRAIN metric table")
    return inputs, hashes, f0, f1.sort_values("candidate_id"), meta, raw, hist


def measured_call(call):
    wall, cpu = time.perf_counter(), time.process_time()
    value = call()
    return value, time.perf_counter() - wall, time.process_time() - cpu


def save_trace(payload, key, series):
    for col in ("timestamp", "base_kw", "cmd_kw", "grid_kw", "soc", "soc_next", "p_imp_cap", "p_exp_cap", "mode"):
        payload[key + "__" + col] = (pd.DatetimeIndex(series[col]).as_unit("ns").asi8 if col == "timestamp"
                                         else series[col].to_numpy(dtype="U32" if col == "mode" else np.float64))


def metric_rescore(args, loaded, source):
    inputs, hashes, f0, f1, meta, raw, hist = loaded
    out = args.out_root / "02_METRICS_AND_PARETO"
    out.mkdir(parents=True, exist_ok=True)
    profiles = {}
    for block in BLOCKS:
        if meta.set_index("block_id").loc[block, "split"] != "train":
            raise ContractError("pilot rescore must use TRAIN only")
        profiles[block] = verified_controller_profile(raw[raw.block_id == block])[0]
    binding = {"input_sha256": hashes, "source": source, "scope": SCOPE, "blocks": BLOCKS,
               "batch_candidates": args.batch_size, "capacity_policy": asdict(CapacityPolicy())}
    store = ReplayCheckpoints(out / "checkpoints", binding)
    hist = hist.set_index(["candidate_id", "block_id"])
    all_rows = []
    for offset in range(0, len(f1), args.batch_size):
        name = f"rescore_{offset // args.batch_size:04d}"
        rows = store.read_batch(name)
        if rows is not None:
            all_rows.extend(rows)
            continue
        rows, traces = [], {}
        for candidate in f1.iloc[offset:offset + args.batch_size].itertuples(index=False):
            params = {key: float(getattr(candidate, key)) for key in PARAM_NAMES}
            for block, profile in profiles.items():
                inv = int(block.split(":")[1][3:])
                site = build_primary_opencem_site(inv)
                record = {"candidate_id": candidate.candidate_id, "block_id": block, "split": "train", "n_ticks": len(profile),
                          "scope": SCOPE, "execution_base_commit": source["base_commit"],
                          "execution_source_sha256": source["source_manifest_sha256"], "metrics_version_v3": METRICS_VERSION,
                          "candidate_parameter_sha256": digest(params), "F0_member": candidate.candidate_id in set(f0.candidate_id)}
                try:
                    sim, wall, cpu = measured_call(lambda: simulate_controller(profile, build_tuned_controller(site, params), site))
                    series = sim.series
                    record.update({"simulation_wall_seconds": wall, "simulation_cpu_seconds": cpu,
                                   "trajectory_sha256": trajectory_hash(series), "trace_key": "event_" + str(len(rows))})
                    save_trace(traces, record["trace_key"], series)
                    original = hist.loc[(candidate.candidate_id, block)]
                    for label, fn in VERSIONS.items():
                        metric, mwall, mcpu = measured_call(lambda fn=fn: fn(series, site))
                        record[label + "_metrics_wall_seconds"] = mwall
                        record[label + "_metrics_cpu_seconds"] = mcpu
                        for col in METRICS:
                            record[label + "_" + col] = float(metric[col])
                            record["original_stored_" + col] = float(original[col])
                        if label == "v3":
                            record.update({key: metric[key] for key in ("capacity_numerical_only_ticks", "capacity_violating_ticks",
                                            "capacity_max_positive_excess_kw", "capacity_policy_id", "capacity_tolerance_kw")})
                    record["peak_process_lifetime_rss_bytes"] = peak_rss_bytes()
                    record["result"] = "SUCCESS_NEW_SIMULATED_TRAJECTORY"
                except Exception as exc:
                    record.update({"result": "FAILED_NO_METRIC_INFERENCE", "error_type": type(exc).__name__, "detail": str(exc)[:1000]})
                rows.append(record)
        artifact = store.root / (name + "_PRIVATE_TRAJECTORIES.npz")
        np.savez_compressed(artifact, **traces)
        store.write_batch(name, rows, artifacts=[artifact])
        all_rows.extend(rows)
        print(json.dumps({"stage": "rescore", "completed": len(all_rows), "expected": 4 * len(f1)}, ensure_ascii=False), flush=True)
    frame = pd.DataFrame(all_rows)
    frame.to_csv(out / "FULL_F0_F1_METRIC_RESCORING.csv", index=False, float_format="%.17g")
    summary = analyze_scores(frame, f0, f1, out)
    summary.update({"scope": SCOPE, "execution_source": source, "input_sha256": hashes,
                    "attempted_events": len(frame), "successful_events": int(frame.result.eq("SUCCESS_NEW_SIMULATED_TRAJECTORY").sum()),
                    "failed_events": int(frame.result.ne("SUCCESS_NEW_SIMULATED_TRAJECTORY").sum()),
                    "F0_candidates": len(f0), "F1_candidates": len(f1), "four_TRAIN_blocks": BLOCKS,
                    "historical_optimizer_metric_events": 12600, "historical_optimizer_reconstructed": False,
                    "independent_TEST_executed": False, "capacity_policy": asdict(CapacityPolicy()),
                    "original_trajectory_status": "ORIGINAL_PER_TICK_CONTROLLER_TRACES_UNAVAILABLE_NEW_TRACES_PRESERVED_PRIVATE_NPZ",
                    "batch_resume_policy": "SOURCE_INPUT_CONFIG_HASH_BOUND_WITH_BATCH_AND_TRACE_HASH_VERIFICATION"})
    good = frame[frame.result.eq("SUCCESS_NEW_SIMULATED_TRAJECTORY")]
    summary["metric_impacts"] = {}
    for col in METRICS:
        delta = good["v2_" + col] - good["legacy_" + col]
        olddelta = good["legacy_" + col] - good["original_stored_" + col]
        summary["metric_impacts"][col] = {"changed_v2_gt1e-12": int((delta.abs() > 1e-12).sum()),
              "v2_minus_legacy_mean": float(delta.mean()), "v2_minus_legacy_min": float(delta.min()),
              "v2_minus_legacy_max": float(delta.max()), "legacy_original_parity_within1e-9": int((olddelta.abs() <= 1e-9).sum()),
              "legacy_original_max_abs_diff": float(olddelta.abs().max())}
    summary["capacity_effect"] = {"legacy_violating_ticks": int(good.capacity_numerical_only_ticks.sum() + good.capacity_violating_ticks.sum()),
                                   "numerical_only_ticks": int(good.capacity_numerical_only_ticks.sum()),
                                   "v3_violating_ticks": int(good.capacity_violating_ticks.sum()),
                                   "affected_events": int(good.capacity_numerical_only_ticks.gt(0).sum()),
                                   "max_positive_excess_kw": float(good.capacity_max_positive_excess_kw.max())}
    write_json(out / "METRIC_CORRECTION_VALIDATION_RECEIPT.json", summary)
    write_json(out / "EXECUTION_SOURCE_MANIFEST.json", source)
    lines = ["# Metrik düzeltmesinin bilimsel etkisi", "", f"Tam F0 arşivi18 ve tam F1 arşivi236 aday; {len(frame)} yeni aday/blok mühendislik değerlendirmesi.",
             "Dört önceden maruz kalınmış gerçek TRAIN bloğu kullanıldı; optimizer çalıştırılmadı, tarihsel12600 olay yeniden oluşturulmadı.",
             "Özgün tarihsel trajectory dosyaları yoktur. Yeni aynı trajectory üzerinde legacy, v2 ve v3 birlikte hesaplandı; yeni izler checkpoint NPZ dosyalarında korunur.",
             "", "Legacy üç noktalı Rainflow yarım çevriminde ortadaki dönüşü siler; v2 en eski dönüşü siler. [0.2,0.8,0.2] ağırlıklı derinliği0.3 yerine0.6 olur.",
             "v2 tam SOC dizisine son soc_next durumunu ekler. Bunlar model proxy metrikleridir; fiziksel batarya ömrü doğrulaması değildir.",
             "", "Risk tanımı mean+0.5*üst-kuyruk ortalaması; q=0.90 ve n=4 için ceil((1-q)n)=1, dolayısıyla kuyruk tek en kötü bloktur. Bu dört blokta CVaR hassasiyeti/bağımsız belirsizlik çıkarımı yapılamaz.",
             "Pareto tüm boyutlar minimizasyon, tam <= ve en az bir < ile belirlenir; eşit vektörlerin aday kimlikleri korunur. Sıralama ortak ölçekli eşit ağırlık skoru için keşifseldir.",
             "HV her arşivde üç sürümün birleşimi üzerinden ortak ideal/span ile normalize edilir; referans1.05/1.10/1.20 duyarlılığı raporlanır. Sürüm başına ayrı ölçek fit edilmez.",
             "", "v3 kapasite politikası: varsayılan abs1e-12kW, relative0. Güvenlik veto karşılaştırmasıyla aynıdır; limit+tol eşitliği ihlal sayılmaz. Negatif limit ve eksik/nonfinite değer reddedilir.",
             "Ölçüm çözünürlüğü bilinmiyor; tahmin edilmedi. İleride bilinen çözünürlük yakın sınır belirsizliği olarak kaydedilir, toleransı gevşetmez.", "", "## Sayısal sonuçlar", "", "```json", json.dumps({key: summary[key] for key in ("archives", "metric_impacts", "capacity_effect")}, indent=2, ensure_ascii=False), "```", "", "## Kalan engel", "", "Özgün12600 olayın tamamının terminal SOC/komut izleri ve tarihsel yürütme kaynak kimliği yok. Bu nedenle tarihsel optimizer risk vektörü, özgün Pareto arşivi ve makaledeki optimizer kalite iddiaları yeni dört-blok skorlarıyla doğrulanmış sayılamaz. Yeni rescore tam aday kapsamı sağlar; tam tarihsel olay kapsamı sağlamaz."]
    (out / "METRIC_CORRECTION_SCIENTIFIC_IMPACT_TR.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame, summary


def analyze_scores(frame, f0, f1, out):
    success = frame[frame.result.eq("SUCCESS_NEW_SIMULATED_TRAJECTORY")]
    membership, impacts, hvs, ranks = [], [], [], []
    summary = {"archives": {}}
    for label, front in (("F0", f0), ("F1", f1)):
        ids = sorted(front.candidate_id)
        group = success[success.candidate_id.isin(ids)].groupby("candidate_id")
        counts = group.size()
        if set(counts.index) != set(ids) or not counts.eq(len(BLOCKS)).all():
            summary["archives"][label] = {"status": "INCOMPLETE_NO_PARETO_OR_HV_INFERENCE", "complete_candidates": int(counts.eq(len(BLOCKS)).sum())}
            continue
        summary["archives"][label] = {}
        for aggregation in ("mean", "mean_plus_half_cvar90"):
            arrays = {}
            for version in VERSIONS:
                matrix = []
                for candidate in ids:
                    values = group.get_group(candidate)[[version + "_" + col for col in OBJECTIVES]].to_numpy(dtype=float)
                    means = values.mean(axis=0)
                    k = max(1, math.ceil((1 - .9) * len(values)))
                    tail = np.sort(values, axis=0)[-k:].mean(axis=0)
                    score = means if aggregation == "mean" else means + .5 * tail
                    matrix.append(score)
                    for j, col in enumerate(OBJECTIVES):
                        impacts.append({"archive": label, "candidate_id": candidate, "metric_version": version,
                                        "aggregation": aggregation, "objective": col, "n_blocks": len(values),
                                        "tail_blocks_k": k, "mean": means[j], "cvar90_ceil_tail": tail[j], "score": score[j]})
                arrays[version] = np.asarray(matrix)
            union = np.vstack(list(arrays.values()))
            ideal, span = union.min(axis=0), np.ptp(union, axis=0)
            normalized = {v: (a - ideal) / np.where(span > 0, span, 1) for v, a in arrays.items()}
            masks = {v: pareto_mask(a) for v, a in arrays.items()}
            ranking = {v: rankdata(a.mean(axis=1), method="average") for v, a in normalized.items()}
            detail = {"n_candidates": len(ids), "n_blocks": len(BLOCKS), "tail_blocks_k": 1}
            for v in VERSIONS:
                detail[v + "_pareto_count"] = int(masks[v].sum())
                for reference in (1.05, 1.10, 1.20):
                    hvs.append({"archive": label, "aggregation": aggregation, "metric_version": v,
                                "reference_each_dimension": reference, "normalized_hypervolume": exact_hypervolume(normalized[v], [reference] * 4),
                                "common_ideal_json": json.dumps(ideal.tolist()), "common_span_json": json.dumps(span.tolist()),
                                "normalization_scope": "POOLED_LEGACY_V2_V3_WITHIN_SAME_ARCHIVE_AGGREGATION"})
            for v in ("v2", "v3"):
                detail[v + "_membership_changed_vs_legacy"] = int((masks[v] != masks["legacy"]).sum())
                detail[v + "_rank_spearman_vs_legacy"] = float(spearmanr(ranking["legacy"], ranking[v]).statistic)
                def pairs(x):
                    return {(i, j) for i in range(len(x)) for j in range(len(x)) if i != j and np.all(x[i] <= x[j]) and np.any(x[i] < x[j])}
                old, new = pairs(arrays["legacy"]), pairs(arrays[v])
                detail[v + "_lost_dominance_pairs"] = len(old - new)
                detail[v + "_gained_dominance_pairs"] = len(new - old)
            for i, candidate in enumerate(ids):
                membership.append({"archive": label, "aggregation": aggregation, "candidate_id": candidate,
                    **{v + "_nondominated": bool(masks[v][i]) for v in VERSIONS},
                    **{v + "_changed_vs_legacy": bool(masks[v][i] != masks["legacy"][i]) for v in ("v2", "v3")}})
                ranks.append({"archive": label, "aggregation": aggregation, "candidate_id": candidate,
                              **{v + "_equal_weight_normalized_rank": float(ranking[v][i]) for v in VERSIONS},
                              "ranking_scope": "EXPLORATORY_EQUAL_WEIGHT_COMMON_SCALE_NOT_OPTIMIZER_SELECTION"})
            summary["archives"][label][aggregation] = detail
    pd.DataFrame(membership).to_csv(out / "PARETO_MEMBERSHIP_BEFORE_AFTER.csv", index=False)
    pd.DataFrame(impacts).to_csv(out / "MEAN_CVAR_METRIC_IMPACT.csv", index=False, float_format="%.17g")
    pd.DataFrame(hvs).to_csv(out / "HYPERVOLUME_SENSITIVITY.csv", index=False, float_format="%.17g")
    pd.DataFrame(ranks).to_csv(out / "CANDIDATE_RANK_EFFECTS.csv", index=False, float_format="%.17g")
    return summary


def checked_replay(args, loaded, source):
    inputs, hashes, f0, f1, meta, raw, hist = loaded
    out = args.out_root / "05_REAL_DATA_REPLAY"
    out.mkdir(parents=True, exist_ok=True)
    candidate = f0.sort_values("candidate_id").iloc[0]
    params = {key: float(candidate[key]) for key in PARAM_NAMES}
    eligible = meta[meta.split.isin(["train", "validation"]) & meta.full_720_contiguous.eq(True)].sort_values("block_id")
    if len(eligible) != 307:
        raise ContractError("expected307 eligible full TRAIN/VALIDATION days")
    store = ReplayCheckpoints(out / "checkpoints", {"input_sha256": hashes, "source": source, "candidate": candidate.candidate_id,
                                  "params": params, "batch_days": args.batch_size, "splits": ["train", "validation"]})
    all_rows, parity = [], []
    for offset in range(0, len(eligible), args.batch_size):
        name = f"replay_{offset // args.batch_size:04d}"
        rows = store.read_batch(name)
        if rows is not None:
            all_rows.extend(rows)
            continue
        rows, traces = [], {}
        for block in eligible.iloc[offset:offset + args.batch_size].itertuples(index=False):
            record = {"block_id": block.block_id, "split": block.split, "candidate_id": str(candidate.candidate_id),
                      "n_input_ticks": int(block.bins), "safety_basis": "SCENARIO_ASSUMPTIONS_NOT_CERTIFIED",
                      "scope": "NEW_CHECKED_ENGINEERING_REPLAY_OF_EXPOSED_REAL_TRAIN_VALIDATION_NO_TEST",
                      "execution_base_commit": source["base_commit"], "execution_source_sha256": source["source_manifest_sha256"]}
            wall, cpu = time.perf_counter(), time.process_time()
            try:
                profile, delta = verified_controller_profile(raw[raw.block_id == block.block_id])
                record.update(delta)
                site = build_primary_opencem_site(int(block.block_id.split(":")[1][3:]))
                result = simulate_checked(profile, build_tuned_controller(site, params), site, SafetyLimits.from_site(site))
                record.update({"result": "PASS_CHECKED_ENGINEERING_SIMULATION", "n_output_ticks": len(result.series),
                               "trajectory_sha256": trajectory_hash(result.series), "trace_key": "event_" + str(len(rows))})
                save_trace(traces, record["trace_key"], result.series)
                for version, fn in VERSIONS.items():
                    metric = fn(result.series, site)
                    for col in METRICS:
                        record[version + "_" + col] = float(metric[col])
                    if version == "v3":
                        record.update({key: metric[key] for key in ("capacity_numerical_only_ticks", "capacity_violating_ticks", "capacity_max_positive_excess_kw")})
            except Exception as exc:
                record.update({"result": "FAIL_CLOSED_VETO_OR_INPUT_ERROR_NO_PARTIAL_METRICS", "error_type": type(exc).__name__,
                               "veto_codes": list(getattr(exc, "codes", ())), "failure_receipt": getattr(exc, "receipt", None), "reason": str(exc)[:1000]})
            record.update({"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                           "peak_process_lifetime_rss_bytes": peak_rss_bytes()})
            rows.append(record)
        artifact = store.root / (name + "_PRIVATE_TRAJECTORIES.npz")
        np.savez_compressed(artifact, **traces)
        store.write_batch(name, rows, artifacts=[artifact])
        all_rows.extend(rows)
        print(json.dumps({"stage": "checked_replay", "completed": len(all_rows), "expected": len(eligible)}), flush=True)
    result = pd.DataFrame(all_rows)
    result.to_csv(out / "CHECKED_EMS_DAYWISE_RESULTS.csv", index=False, float_format="%.17g")
    parity_cols = ["block_id", "split", "n_input_ticks", "input_tensor_parity", "profile_sha256"] + [name + "_max_abs_raw_frozen_kw" for name in ("load_kw", "pv_kw", "base_kw")]
    result.reindex(columns=parity_cols).to_csv(out / "RAW_TO_CONTROLLER_INPUT_PARITY.csv", index=False, float_format="%.17g")
    coverage = meta.copy()
    by_block = result.set_index("block_id")
    coverage["new_execution_status"] = ["EXCLUDED_INTERNAL_TEST_NO_NEW_EXECUTION" if row.split == "internal_test"
        else "PARTIAL_DAY_EXCLUDED_NO_FILL_OR_FULL_DAY_CLAIM" if not row.full_720_contiguous
        else by_block.loc[row.block_id, "result"] for row in meta.itertuples(index=False)]
    coverage.to_csv(out / "EMS_REPLAY_COVERAGE_MATRIX.csv", index=False)
    passed = result[result.result.eq("PASS_CHECKED_ENGINEERING_SIMULATION")]
    summary = {"execution_source": source, "input_sha256": hashes, "fixed_candidate": str(candidate.candidate_id),
               "candidate_parameter_sha256": digest(params), "input_registry_blocks": len(meta), "attempted_legal_full_days": len(result),
               "passed_days": len(passed), "vetoed_or_invalid_days": len(result) - len(passed),
               "TRAIN_attempted": int(result.split.eq("train").sum()), "VALIDATION_attempted": int(result.split.eq("validation").sum()),
               "TRAIN_passed": int(passed.split.eq("train").sum()), "VALIDATION_passed": int(passed.split.eq("validation").sum()),
               "internal_TEST_blocks_excluded": int(meta.split.eq("internal_test").sum()),
               "partial_legal_days_excluded": int((meta.split.isin(["train", "validation"]) & ~meta.full_720_contiguous).sum()),
               "partial_total_blocks": int((~meta.full_720_contiguous).sum()), "total_full_historical_days": int(meta.full_720_contiguous.sum()),
               "CPU_seconds_sum": float(result.cpu_seconds.sum()), "wall_seconds_sum": float(result.wall_seconds.sum()),
               "peak_process_lifetime_RSS_bytes": int(result.peak_process_lifetime_rss_bytes.max()),
               "memory_scope": "PROCESS_LIFETIME_HIGH_WATER_NOT_PER_EVENT_PEAK", "new_independent_TEST_executed": False,
               "original_controller_input_tensor_available": False, "original_controller_trace_reconstructed": False,
               "new_trace_preservation": "COMPRESSED_PRIVATE_NPZ_PER_CHECKPOINT_BATCH_NO_TIMING_IN_TRACE_HASH",
               "capacity_numerical_only_ticks_passed_days": int(passed.capacity_numerical_only_ticks.sum()) if len(passed) else 0,
               "capacity_v3_violating_ticks_passed_days": int(passed.capacity_violating_ticks.sum()) if len(passed) else 0,
               "physical_safety_validated": False, "HIL_validated": False, "hard_real_time_certified": False,
               "result_scope": "SCENARIO_SAFETY_VETO_ENGINEERING_ONLY;FAILED_DAYS_EXCLUDED_NO_PARTIAL_METRICS"}
    write_json(out / "CHECKED_EMS_EXECUTION_RECEIPTS.json", summary)
    (out / "EMS_REPRODUCIBILITY_AUDIT_TR.md").write_text("# EMS yeniden üretilebilirlik denetimi\n\n"
        "Mevcut19 ham dosya doğrulaması yeniden çalıştırılmadı. Doğrulanmış292256 bin ve406 blok kaydı kullanıldı.\n\n"
        f"TRAIN195 ve VALIDATION112 tam gün: {len(result)} sabit aday denemesi, {len(passed)} geçiş, {len(result)-len(passed)} fail-closed veto/hata.\n\n"
        "78 tarihsel internal_TEST bloğu çalıştırılmadı.21 yasal split kısmi bloğu tam gün olarak çalıştırılmadı; doldurma/interpolasyon yok. Toplam381 tam günün74 internal_TEST günü kapsam dışıdır.\n\n"
        "Raw load/PV/base→frozen replay sayısal eşliği kontrol edildi; profile girişinde base korunur ve tarihsel adapter gibi peak_flag=0 kullanılır. Özgün controller tensor/trace mevcut olmadığından orijinal tensor bit eşliği ve özgün komut/SOC dizisi kanıtlanamaz.\n\n"
        "Güvenlik varsayımları model senaryosudur. Veto olan günlerde kısmi izlerden başarı metriği üretilmedi. CPU ve wall zaman ölçüldü; RAM süreç ömür boyu high-water markıdır. Inline kontrol süreç timeout containment sağlamaz, hard-real-time veya saha güvenliği sertifikası değildir.\n\n"
        "```json\n" + json.dumps({k: v for k, v in summary.items() if k not in {"execution_source", "input_sha256"}}, indent=2, ensure_ascii=False) + "\n```\n", encoding="utf-8")
    return result, summary


def compute_evidence(args, loaded, metric_frame=None):
    inputs, hashes, f0, f1, meta, raw, hist = loaded
    out = args.out_root / "06_ABLATION_AND_COMPUTE"
    out.mkdir(parents=True, exist_ok=True)
    historical_root = args.project_root / "02_DATASETS/05_RECOVERED_HISTORICAL_TRAIN_20261027"
    rows = []
    for folder in sorted(historical_root.glob("seed*/F*")):
        summary_path, metrics_path = folder / "run_summary.json", folder / "candidate_metrics.csv"
        if not summary_path.exists() or not metrics_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        df = pd.read_csv(metrics_path, usecols=["candidate_id", "n_ticks", "mean_cpu_ms", "max_cpu_ms"])
        rows.append({"seed": summary["seed"], "condition": summary["condition_id"], "candidate_block_evaluations": len(df),
                     "budget_recorded": summary["train_budget_used"], "archive_size": summary["archive_count"],
                     "recorded_controller_step_wall_seconds_proxy": float((df.mean_cpu_ms * df.n_ticks).sum() / 1000),
                     "max_recorded_step_wall_ms": float(df.max_cpu_ms.max()), "candidate_metrics_sha256": file_hash(metrics_path),
                     "original_execution_commit": summary["original_git_sha"], "cpu_seconds": None, "wall_seconds_end_to_end": None,
                     "peak_RAM_bytes": None, "optimizer_seconds": None, "calibration_seconds": None,
                     "archive_construction_seconds": None, "selection_seconds": None,
                     "cost_evidence_scope": "ARCHIVED_PER_STEP_PERF_COUNTER_SUM_ONLY_NOT_TOTAL_CPU_OR_END_TO_END_COST"})
    historical = pd.DataFrame(rows)
    historical.to_csv(out / "HISTORICAL_COMPUTE_ACCOUNTING.csv", index=False, float_format="%.17g")
    pairs = []
    historical["pair_key"] = historical.condition.str.replace(r"_F[01]_", "_F*_", regex=True)
    for (seed, key), g in historical.groupby(["seed", "pair_key"]):
        if len(g) != 2:
            raise ContractError("historical F0/F1 cost pair incomplete")
        a, b = (g[g.condition.str.contains("_F" + str(f) + "_")].iloc[0] for f in (0, 1))
        pairs.append({"seed": int(seed), "condition_pair": key, "F0_candidate_block_events": int(a.candidate_block_evaluations),
                      "F1_candidate_block_events": int(b.candidate_block_evaluations),
                      "equal_evaluation_budget": bool(a.candidate_block_evaluations == b.candidate_block_evaluations),
                      "same_recorded_simulator_metrics_payload": a.candidate_metrics_sha256 == b.candidate_metrics_sha256,
                      "F0_archive_size": int(a.archive_size), "F1_archive_size": int(b.archive_size),
                      "total_computational_cost_equal": "UNVERIFIED_MISSING_PHASE_CPU_WALL_RAM_EVIDENCE"})
    pd.DataFrame(pairs).to_csv(out / "PAIRED_F0_F1_COMPUTE_FAIRNESS.csv", index=False)
    if metric_frame is None:
        candidate = args.out_root / "02_METRICS_AND_PARETO/FULL_F0_F1_METRIC_RESCORING.csv"
        metric_frame = pd.read_csv(candidate) if candidate.exists() else None
    benchmark = []
    if metric_frame is not None:
        good = metric_frame[metric_frame.result.eq("SUCCESS_NEW_SIMULATED_TRAJECTORY")]
        for label, front in (("F0", f0), ("F1", f1)):
            subset = good[good.candidate_id.isin(front.candidate_id)]
            for phase in ("simulation", "legacy_metrics", "v2_metrics", "v3_metrics"):
                benchmark.append({"archive": label, "phase": phase, "events": len(subset),
                                  "wall_seconds_sum": float(subset[phase + "_wall_seconds"].sum()),
                                  "cpu_seconds_sum": float(subset[phase + "_cpu_seconds"].sum()),
                                  "process_lifetime_peak_RAM_bytes": int(subset.peak_process_lifetime_rss_bytes.max()),
                                  "scope": "NEW_FIXED_ARCHIVE_REPLAY_STAGE_COST_NOT_OPTIMIZER_SEARCH_COST",
                                  "shared_F0_subset_reused_from_F1": True})
    pd.DataFrame(benchmark).to_csv(out / "PAIRED_ENGINEERING_STAGE_BENCHMARK.csv", index=False, float_format="%.17g")
    status = {"historical_cells": len(historical), "paired_F0_F1_cells": len(pairs),
              "all_pairs_evaluation_budget_equal": all(r["equal_evaluation_budget"] for r in pairs),
              "pairs_same_metrics_payload": sum(r["same_recorded_simulator_metrics_payload"] for r in pairs),
              "total_compute_fairness_demonstrated": False, "missing_historical_costs": ["total CPU", "end-to-end wall", "phase peak RAM", "optimizer", "calibration", "archive construction", "selection"],
              "new_benchmark_rows": len(benchmark), "independent_performance_superiority_demonstrated": False}
    write_json(out / "COMPUTE_FAIRNESS_RECEIPT.json", status)
    (out / "COMPUTE_FAIRNESS_AUDIT_TR.md").write_text("# Hesaplama adaleti\n\n"
        f"{len(historical)} tarihsel hücre ve{len(pairs)} eşli F0/F1 bütçesi incelendi.12600 simülatör değerlendirmesi eşitliği toplam hesap maliyetinin eşitliğini göstermez.\n\n"
        "mean_cpu_ms adı yanıltıcıdır: simülatör perf_counter ile controller.step duvar zamanı ölçer. Bu alan*n_ticks toplamı yalnız kaydedilmiş controller adım süresi proxy'sidir; gerçek CPU veya optimizer/calibration/arşiv/selection/toplam wall değildir. Eksik maliyetler CSV'de boş bırakıldı.\n\n"
        "Yeni benchmark aynı yeni trajectory üzerinde legacy/v2/v3 hesapları ile simülasyon CPU/wall zamanını ölçer. F0'ın72 olayı F1'in944 olayının alt kümesidir; ortak iş tekrar ücretlendirilmez. Bu benchmark arşiv tarama maliyetidir, yeni optimizer karşılaştırması değildir. Süreler bu donanıma/iş yüküne koşulludur; eşzamanlı süreçler wall zamanı etkileyebilir. RAM süreç ömür boyu zirvesidir.\n\n"
        "C/F/A ana ve etkileşim analizleri ayrı tarihsel keşif çıktılarıyla çapraz bağlanır. Optimizer seedleri bağımsız fiziksel saha veya veri kümesi değildir. Bağımsız üstünlük ve eşit toplam maliyet iddiası desteklenmedi.\n\n"
        "```json\n" + json.dumps(status, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("all", "rescore", "replay", "compute"), default="all")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ContractError("positive batch size required")
    loaded, source = load_inputs(args.project_root.resolve()), source_identity()
    metric_frame = None
    if args.mode in {"all", "rescore"}:
        metric_frame, _ = metric_rescore(args, loaded, source)
    if args.mode in {"all", "replay"}:
        checked_replay(args, loaded, source)
    if args.mode in {"all", "compute"}:
        compute_evidence(args, loaded, metric_frame)
    print(json.dumps({"status": "ENGINEERING_COMPLETED_WITH_EXPLICIT_SCIENTIFIC_LIMITS", "mode": args.mode,
                      "base_commit": source["base_commit"], "source_sha256": source["source_manifest_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
