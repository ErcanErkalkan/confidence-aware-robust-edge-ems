from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from baseline_optimizers import BlockRiskOracle, run_mode, run_mopso, run_nsga2, run_sobol
from crmt_edge_ems.budget import EvaluationLedger
from crmt_edge_ems.generator import sobol_candidates
from crmt_edge_ems.parameter_space import PARAM_NAMES, decode_unit_vector, encode_physical
from crmt_edge_ems.protocol import (
    BASELINE_HYPERPARAMETERS,
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    CRMT_CANDIDATE_POOL_SIZE,
    CRMT_HYPERPARAMETERS,
    METHOD_IDS,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    TRAIN_BLOCK_COUNT,
)
from crmt_edge_ems.replay import MultiSiteReplayEvaluator, ReplayBlock
from crmt_edge_ems.risk import RiskConfig
from crmt_edge_ems.site_model import (
    PRIMARY_OPENCEM_CADENCE_MINUTES,
    build_primary_opencem_site,
)
from crmt_edge_ems.study import CRMTStudy
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_raw(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        header = pd.read_csv(path, nrows=0)
        cols = [c for c in KEY_COLS if c in header.columns]
        frames.append(pd.read_csv(path, usecols=cols))
    return pd.concat(frames, ignore_index=True)


def build_locked_split_blocks(
    paths: list[Path],
    *,
    lock: Mapping,
    split_name: str,
) -> tuple[list[ReplayBlock], dict[str, object]]:
    """Reconstruct/hash-verify the frozen inventory and expose one named split."""
    expected_counts = {
        "train": TRAIN_BLOCK_COUNT,
        "validation": int(lock["split_counts"]["validation"]),
        "internal_test": int(lock["split_counts"]["internal_test"]),
    }
    if split_name not in expected_counts:
        raise ValueError(f"split_name must be one of {tuple(expected_counts)}")

    cadence = int(lock["cadence_minutes"])
    if cadence != PRIMARY_OPENCEM_CADENCE_MINUTES:
        raise RuntimeError("block lock cadence disagrees with primary protocol")

    raw = _load_raw(paths)
    profiles = reconstruct_per_inverter_profiles(
        raw,
        frequency=f"{cadence}min",
        expected_inverters=(1, 2),
        min_samples_per_inverter_bin=1,
    )
    all_blocks = per_inverter_daily_blocks(
        profiles,
        expected_frequency_minutes=cadence,
        min_coverage=float(lock["min_daily_coverage"]),
    )
    manifest = complete_day_block_manifest(all_blocks, cadence_minutes=cadence)
    observed_hash = block_manifest_sha256(manifest)
    expected_hash = str(lock["canonical_csv_sha256"])
    if observed_hash != expected_hash:
        raise RuntimeError(
            f"block manifest hash mismatch: observed={observed_hash}, expected={expected_hash}"
        )
    if len(manifest) != int(lock["row_count"]):
        raise RuntimeError("block manifest row count mismatch")

    rows: list[tuple[str, int, pd.DataFrame]] = []
    for inv in (1, 2):
        assigned = assign_confirmatory_split(
            all_blocks[inv], split=DEFAULT_CONFIRMATORY_SPLIT
        )
        for date, frame in assigned[split_name].items():
            rows.append((str(date), int(inv), frame))

    rows.sort(key=lambda z: (z[0], z[1]))
    blocks = [
        ReplayBlock(
            block_id=f"opencem:inv{inv}:{date}",
            profile=frame,
            source="OpenCEM",
            split=split_name,
            site_id=inv,
        )
        for date, inv, frame in rows
    ]
    expected = int(expected_counts[split_name])
    if len(blocks) != expected:
        raise RuntimeError(
            f"{split_name} block count mismatch: {len(blocks)} != {expected}"
        )

    context = {
        "manifest_sha256": observed_hash,
        "manifest_rows": int(len(manifest)),
        "split": split_name,
        "split_block_count": int(len(blocks)),
        "block_order": "local_date_then_inverter",
        "first_block_ids": [b.block_id for b in blocks[:4]],
    }
    return blocks, context


def build_locked_train_blocks(
    paths: list[Path],
    *,
    lock: Mapping,
) -> tuple[list[ReplayBlock], dict[str, object]]:
    """Backward-compatible TRAIN-only wrapper with paired-design safeguard."""
    blocks, context = build_locked_split_blocks(
        paths, lock=lock, split_name="train"
    )
    if {str(b.site_id) for b in blocks[:4]} != {"1", "2"}:
        raise RuntimeError(
            "first four CRMT blocks do not cover both OpenCEM physical subsystems"
        )
    context["first_four_block_ids"] = [b.block_id for b in blocks[:4]]
    return blocks, context


def _risk() -> RiskConfig:
    return RiskConfig(
        q=float(CRMT_HYPERPARAMETERS["risk_q"]),
        tail_weight=float(CRMT_HYPERPARAMETERS["tail_weight"]),
    )


def _sites():
    return {
        1: build_primary_opencem_site(1),
        2: build_primary_opencem_site(2),
    }


def _baseline_runner(method: str):
    return {
        "SOBOL": run_sobol,
        "NSGAII": run_nsga2,
        "MOPSO": run_mopso,
        "MODE": run_mode,
    }[method]


def run_baseline(
    method: str,
    seed: int,
    blocks: list[ReplayBlock],
    *,
    budget: int = CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    hyperparameters: Mapping | None = None,
):
    method = str(method).upper()
    if method not in {"SOBOL", "NSGAII", "MOPSO", "MODE"}:
        raise ValueError(f"not a baseline method: {method}")

    ledger = EvaluationLedger(int(budget))
    evaluator = MultiSiteReplayEvaluator(
        _sites(), ledger=ledger, method_id=method
    )
    oracle = BlockRiskOracle(evaluator, blocks, risk=_risk())
    kwargs = dict(
        BASELINE_HYPERPARAMETERS[method]
        if hyperparameters is None
        else hyperparameters
    )
    result = _baseline_runner(method)(oracle, seed=int(seed), **kwargs)
    ledger.assert_exact()
    return result, oracle, ledger


def run_crmt(
    seed: int,
    blocks: list[ReplayBlock],
    *,
    budget: int = CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    candidate_pool_size: int = CRMT_CANDIDATE_POOL_SIZE,
    hyperparameters: Mapping | None = None,
    allocation_mode: str = "adaptive",
    archive_mode: str = "confidence",
    risk_override: RiskConfig | None = None,
):
    hp = dict(
        CRMT_HYPERPARAMETERS if hyperparameters is None else hyperparameters
    )
    ledger = EvaluationLedger(int(budget))
    evaluator = MultiSiteReplayEvaluator(
        _sites(), ledger=ledger, method_id="CRMT"
    )
    pool = sobol_candidates(int(candidate_pool_size), seed=int(seed))
    candidates = {
        f"CRMT-c{i + 1:04d}": p for i, p in enumerate(pool)
    }

    risk = risk_override or RiskConfig(
        q=float(hp["risk_q"]),
        tail_weight=float(hp["tail_weight"]),
    )
    study = CRMTStudy(
        evaluator,
        risk=risk,
        initial_blocks=int(hp["initial_blocks"]),
        allocation_batch=int(hp["allocation_batch"]),
        alpha=float(hp["alpha"]),
        n_boot=int(hp["n_boot"]),
        allocation_mode=allocation_mode,
        archive_mode=archive_mode,
    )
    result = study.run(
        candidates,
        blocks,
        max_evaluations=int(budget),
    )
    if result.budget_used != int(budget):
        raise RuntimeError(
            f"CRMT stopped before exact budget: {result.budget_used} != {budget}"
        )
    ledger.assert_exact()
    return result, candidates, evaluator, ledger


def _baseline_candidate_frame(
    oracle: BlockRiskOracle,
    objective_names: tuple[str, ...],
) -> pd.DataFrame:
    rows = []
    for record in oracle.evaluation_records:
        row = {"candidate_id": record["candidate_id"]}
        unit = np.asarray(record["unit"], dtype=float)
        row.update({f"u{i}": float(x) for i, x in enumerate(unit)})
        row.update({k: float(v) for k, v in record["params"].items()})
        row.update(
            {
                name: float(value)
                for name, value in zip(
                    objective_names,
                    np.asarray(record["objective"], dtype=float),
                )
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _front_frame(
    method: str,
    result,
    objective_names: tuple[str, ...],
) -> pd.DataFrame:
    positions = np.asarray(result.nondominated_positions, dtype=float)
    objectives = np.asarray(result.nondominated_objectives, dtype=float)
    rows = []
    for i in range(len(positions)):
        params = decode_unit_vector(positions[i])
        row = {"front_id": f"{method}-front-{i + 1:04d}"}
        row.update(
            {f"u{j}": float(v) for j, v in enumerate(positions[i])}
        )
        row.update({k: float(v) for k, v in params.items()})
        row.update(
            {
                name: float(v)
                for name, v in zip(objective_names, objectives[i])
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _crmt_metrics_frame(result) -> pd.DataFrame:
    frames = []
    for cid, df in result.candidate_metrics.items():
        part = df.copy()
        part.insert(0, "candidate_id", cid)
        frames.append(part)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _crmt_archive_frame(
    result,
    candidates,
    evaluator,
    risk: RiskConfig,
) -> pd.DataFrame:
    rows = []
    for cid in result.archive_ids:
        params = candidates[cid]
        unit = encode_physical(params)
        agg = evaluator.aggregate(result.candidate_metrics[cid], risk)
        row = {"candidate_id": cid}
        row.update({f"u{i}": float(v) for i, v in enumerate(unit)})
        row.update({k: float(v) for k, v in params.items()})
        row.update({k: float(v) for k, v in agg.items()})
        rows.append(row)
    return pd.DataFrame(rows)


def _write_csv(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")
    return _sha256(path)


def execute_confirmatory_train_on_blocks(
    method: str,
    seed: int,
    blocks: list[ReplayBlock],
    *,
    context: Mapping,
    output_dir: Path,
) -> dict:
    """Execute one frozen TRAIN optimizer run on already verified TRAIN blocks."""
    method = str(method).upper()
    seed = int(seed)
    if method not in METHOD_IDS:
        raise ValueError(f"method must be one of {METHOD_IDS}")
    if seed not in OPTIMIZER_SEEDS:
        raise ValueError(
            f"seed must be one of {OPTIMIZER_SEEDS[0]}..{OPTIMIZER_SEEDS[-1]}"
        )
    if len(blocks) != TRAIN_BLOCK_COUNT:
        raise RuntimeError(
            f"TRAIN block count mismatch: {len(blocks)} != {TRAIN_BLOCK_COUNT}"
        )
    if any(b.split != "train" for b in blocks):
        raise RuntimeError("non-TRAIN block entered confirmatory optimization")

    output_dir.mkdir(parents=True, exist_ok=True)
    objective_names = _risk().objectives
    files: dict[str, str] = {}

    if method == "CRMT":
        result, candidates, evaluator, ledger = run_crmt(seed, blocks)
        metrics = _crmt_metrics_frame(result)
        archive = _crmt_archive_frame(
            result, candidates, evaluator, _risk()
        )
        files["candidate_metrics.csv"] = _write_csv(
            metrics, output_dir / "candidate_metrics.csv"
        )
        files["optimizer_front.csv"] = _write_csv(
            archive, output_dir / "optimizer_front.csv"
        )
        result_size = int(len(archive))
        candidate_count = int(len(candidates))
    else:
        result, oracle, ledger = run_baseline(method, seed, blocks)
        candidates = _baseline_candidate_frame(
            oracle, objective_names
        )
        front = _front_frame(method, result, objective_names)
        files["candidate_evaluations.csv"] = _write_csv(
            candidates,
            output_dir / "candidate_evaluations.csv",
        )
        files["optimizer_front.csv"] = _write_csv(
            front,
            output_dir / "optimizer_front.csv",
        )
        result_size = int(len(front))
        candidate_count = int(len(candidates))

    files["ledger.csv"] = _write_csv(
        ledger.to_frame(),
        output_dir / "ledger.csv",
    )
    if ledger.used != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
        raise RuntimeError(
            "ledger does not equal frozen confirmatory controller-block budget"
        )

    summary = {
        "stage": "TRAIN_OPTIMIZATION_ONLY",
        "claim_boundary": (
            "No validation, internal-test, sensitivity, ablation, or OOD result "
            "is included in this artifact."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "method": method,
        "seed": seed,
        "controller_block_budget": CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
        "ledger_used": int(ledger.used),
        "candidate_count": candidate_count,
        "optimizer_output_size": result_size,
        "risk": {
            "q": float(CRMT_HYPERPARAMETERS["risk_q"]),
            "tail_weight": float(CRMT_HYPERPARAMETERS["tail_weight"]),
            "objectives": list(objective_names),
        },
        "data_context": dict(context),
        "git_sha": os.environ.get("GITHUB_SHA"),
        "files_sha256": files,
    }
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def execute_confirmatory_train(
    method: str,
    seed: int,
    paths: list[Path],
    *,
    lock: Mapping,
    output_dir: Path,
) -> dict:
    """Reconstruct/verify frozen TRAIN blocks, then execute one optimizer run."""
    blocks, context = build_locked_train_blocks(paths, lock=lock)
    return execute_confirmatory_train_on_blocks(
        method,
        seed,
        blocks,
        context=context,
        output_dir=output_dir,
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fail-closed OpenCEM confirmatory TRAIN optimizer"
    )
    p.add_argument("--method", required=True, choices=list(METHOD_IDS))
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(
        args.raw_root,
        args.verification_csv,
    )
    lock = json.loads(
        args.block_lock_json.read_text(encoding="utf-8")
    )
    summary = execute_confirmatory_train(
        args.method,
        args.seed,
        paths,
        lock=lock,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
