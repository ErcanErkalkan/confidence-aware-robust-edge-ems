from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from crmt_edge_ems.parameter_space import PARAM_NAMES
from crmt_edge_ems.protocol import (
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    CRMT_HYPERPARAMETERS,
    METHOD_IDS,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    SELECTION_RULE_ID,
    VALIDATION_BLOCK_COUNT,
)
from crmt_edge_ems.replay import MultiSiteReplayEvaluator
from crmt_edge_ems.risk import RiskConfig
from crmt_edge_ems.selection import score_validation_candidates, select_one_per_method
from crmt_edge_ems.site_model import build_primary_opencem_site
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_qa import load_verified_csvs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _risk() -> RiskConfig:
    return RiskConfig(
        q=float(CRMT_HYPERPARAMETERS["risk_q"]),
        tail_weight=float(CRMT_HYPERPARAMETERS["tail_weight"]),
    )


def _sites():
    return {1: build_primary_opencem_site(1), 2: build_primary_opencem_site(2)}


def _read_train_front(
    run_dir: Path,
    *,
    method: str,
    seed: int,
    expected_manifest_sha256: str,
) -> tuple[pd.DataFrame, dict]:
    summary_path = run_dir / "run_summary.json"
    front_path = run_dir / "optimizer_front.csv"
    if not summary_path.is_file() or not front_path.is_file():
        raise FileNotFoundError(f"missing TRAIN artifact files in {run_dir}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("stage") != "TRAIN_OPTIMIZATION_ONLY":
        raise RuntimeError(f"{run_dir}: unexpected stage")
    if summary.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError(f"{run_dir}: protocol version mismatch")
    if str(summary.get("method")) != method:
        raise RuntimeError(f"{run_dir}: method mismatch")
    if int(summary.get("seed")) != int(seed):
        raise RuntimeError(f"{run_dir}: seed mismatch")
    if int(summary.get("controller_block_budget")) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
        raise RuntimeError(f"{run_dir}: budget mismatch")
    if int(summary.get("ledger_used")) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
        raise RuntimeError(f"{run_dir}: non-exact TRAIN ledger")
    if summary.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha256:
        raise RuntimeError(f"{run_dir}: block-manifest mismatch")
    expected_front_hash = summary.get("files_sha256", {}).get("optimizer_front.csv")
    if not expected_front_hash or _sha256(front_path) != expected_front_hash:
        raise RuntimeError(f"{run_dir}: optimizer_front.csv hash mismatch")

    front = pd.read_csv(front_path)
    if front.empty:
        raise RuntimeError(f"{run_dir}: empty optimizer front")
    id_col = "front_id" if "front_id" in front.columns else "candidate_id"
    if id_col not in front.columns:
        raise KeyError(f"{run_dir}: no candidate identifier column")
    missing_params = [p for p in PARAM_NAMES if p not in front.columns]
    if missing_params:
        raise KeyError(f"{run_dir}: missing parameter columns {missing_params}")
    clean = front[[id_col, *PARAM_NAMES]].copy()
    clean = clean.rename(columns={id_col: "candidate_id"})
    clean.insert(0, "method", method)
    if clean[["method", "candidate_id"]].duplicated().any():
        raise RuntimeError(f"{run_dir}: duplicate front candidate IDs")
    return clean, {
        "run_summary_sha256": _sha256(summary_path),
        "optimizer_front_sha256": _sha256(front_path),
    }


def _evaluate_front(
    front: pd.DataFrame,
    validation_blocks,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    evaluator = MultiSiteReplayEvaluator(
        _sites(), method_id="VALIDATION_SELECTION"
    )
    risk = _risk()
    score_rows = []
    metric_frames = []
    for row in front.itertuples(index=False):
        params = {name: float(getattr(row, name)) for name in PARAM_NAMES}
        metrics = evaluator.evaluate(
            params,
            validation_blocks,
            candidate_id=f"{row.method}:{row.candidate_id}",
        )
        if len(metrics) != VALIDATION_BLOCK_COUNT:
            raise RuntimeError("validation block count changed during evaluation")
        metrics.insert(0, "candidate_id", str(row.candidate_id))
        metrics.insert(0, "method", str(row.method))
        metric_frames.append(metrics)
        agg = evaluator.aggregate(metrics, risk)
        score = {
            "method": str(row.method),
            "candidate_id": str(row.candidate_id),
            **params,
            **{k: float(v) for k, v in agg.items()},
        }
        score_rows.append(score)
    return pd.DataFrame(score_rows), pd.concat(metric_frames, ignore_index=True)


def _write_csv(df: pd.DataFrame, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")
    return _sha256(path)


def execute_validation_selection(
    seed: int,
    paths: list[Path],
    *,
    lock: dict,
    train_run_root: Path,
    output_dir: Path,
) -> dict:
    seed = int(seed)
    if seed not in OPTIMIZER_SEEDS:
        raise ValueError("seed is outside the frozen optimizer seed registry")
    validation_blocks, context = build_locked_split_blocks(
        paths, lock=lock, split_name="validation"
    )
    if len(validation_blocks) != VALIDATION_BLOCK_COUNT:
        raise RuntimeError("frozen validation block count mismatch")
    expected_manifest_sha = str(lock["canonical_csv_sha256"])

    fronts = []
    train_sources = {}
    for method in METHOD_IDS:
        run_dir = train_run_root / f"{method}_seed{seed}"
        front, evidence = _read_train_front(
            run_dir,
            method=method,
            seed=seed,
            expected_manifest_sha256=expected_manifest_sha,
        )
        fronts.append(front)
        train_sources[method] = evidence
    common_front = pd.concat(fronts, ignore_index=True)

    raw_scores, block_metrics = _evaluate_front(
        common_front, validation_blocks
    )
    scored, references = score_validation_candidates(
        raw_scores, objectives=_risk().objectives
    )
    selected = select_one_per_method(scored)
    if set(selected["method"]) != set(METHOD_IDS) or len(selected) != len(METHOD_IDS):
        raise RuntimeError("selection did not produce exactly one candidate per method")

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    files["validation_candidate_scores.csv"] = _write_csv(
        scored, output_dir / "validation_candidate_scores.csv"
    )
    files["validation_block_metrics.csv"] = _write_csv(
        block_metrics, output_dir / "validation_block_metrics.csv"
    )
    files["selected_candidates.csv"] = _write_csv(
        selected, output_dir / "selected_candidates.csv"
    )

    selection_lock = {
        "stage": "VALIDATION_SELECTION_LOCK",
        "claim_boundary": (
            "Candidate selection uses TRAIN optimizer fronts and frozen validation "
            "blocks only. Internal-test data are not used."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "selection_rule_id": SELECTION_RULE_ID,
        "seed": seed,
        "method_ids": list(METHOD_IDS),
        "data_context": context,
        "risk": {
            "q": float(CRMT_HYPERPARAMETERS["risk_q"]),
            "tail_weight": float(CRMT_HYPERPARAMETERS["tail_weight"]),
            "objectives": list(_risk().objectives),
        },
        "normalization_reference": references,
        "train_sources": train_sources,
        "files_sha256": files,
        "selected_candidates_sha256": files["selected_candidates.csv"],
    }
    lock_path = output_dir / "selection_lock.json"
    lock_path.write_text(json.dumps(selection_lock, indent=2), encoding="utf-8")
    return selection_lock


def main() -> int:
    p = argparse.ArgumentParser(
        description="Evaluate TRAIN fronts on validation and freeze one candidate per method"
    )
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--train-run-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_validation_selection(
        args.seed,
        paths,
        lock=lock,
        train_run_root=args.train_run_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
