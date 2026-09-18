from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from crmt_edge_ems.protocol import (
    ABLATION_IDS,
    ABLATION_SETTINGS,
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    CRMT_CANDIDATE_POOL_SIZE,
    CRMT_HYPERPARAMETERS,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
)
from crmt_edge_ems.risk import RiskConfig
from opencem_confirmatory_train import (
    _crmt_archive_frame,
    _crmt_metrics_frame,
    _write_csv,
    build_locked_train_blocks,
    run_crmt,
)
from opencem_qa import load_verified_csvs


def execute_ablation_train_on_blocks(
    ablation_id: str,
    seed: int,
    blocks,
    *,
    context: dict,
    output_dir: Path,
    budget: int = CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    candidate_pool_size: int = CRMT_CANDIDATE_POOL_SIZE,
    hyperparameters: dict | None = None,
) -> dict:
    ablation_id = str(ablation_id).upper()
    seed = int(seed)
    if ablation_id not in ABLATION_IDS:
        raise ValueError(f"ablation_id must be one of {ABLATION_IDS}")
    if seed not in OPTIMIZER_SEEDS:
        raise ValueError("seed is outside the frozen optimizer seed registry")

    setting = dict(ABLATION_SETTINGS[ablation_id])
    hp = dict(CRMT_HYPERPARAMETERS if hyperparameters is None else hyperparameters)
    risk = RiskConfig(
        q=float(hp["risk_q"]),
        tail_weight=float(setting["risk_tail_weight"]),
    )
    result, candidates, evaluator, ledger = run_crmt(
        seed,
        blocks,
        budget=int(budget),
        candidate_pool_size=int(candidate_pool_size),
        hyperparameters=hp,
        allocation_mode=str(setting["allocation_mode"]),
        archive_mode=str(setting["archive_mode"]),
        risk_override=risk,
    )
    if ledger.used != int(budget):
        raise RuntimeError("ablation did not exhaust the exact controller-block budget")

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    files["candidate_metrics.csv"] = _write_csv(
        _crmt_metrics_frame(result),
        output_dir / "candidate_metrics.csv",
    )
    files["optimizer_front.csv"] = _write_csv(
        _crmt_archive_frame(result, candidates, evaluator, risk),
        output_dir / "optimizer_front.csv",
    )
    files["ledger.csv"] = _write_csv(
        ledger.to_frame(),
        output_dir / "ledger.csv",
    )

    summary = {
        "stage": "CRMT_ABLATION_TRAIN_ONLY",
        "claim_boundary": (
            "Ablation TRAIN evidence only. No validation/internal-test/OOD result."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "ablation_id": ablation_id,
        "seed": seed,
        "controller_block_budget": int(budget),
        "ledger_used": int(ledger.used),
        "candidate_pool_size": int(candidate_pool_size),
        "changed_axis": setting,
        "fixed_crmt_hyperparameters": hp,
        "risk": {
            "q": float(risk.q),
            "tail_weight": float(risk.tail_weight),
            "objectives": list(risk.objectives),
        },
        "data_context": dict(context),
        "archive_size": int(len(result.archive_ids)),
        "git_sha": os.environ.get("GITHUB_SHA"),
        "files_sha256": files,
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def execute_ablation_train(
    ablation_id: str,
    seed: int,
    paths: list[Path],
    *,
    lock: dict,
    output_dir: Path,
    budget: int = CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    candidate_pool_size: int = CRMT_CANDIDATE_POOL_SIZE,
    hyperparameters: dict | None = None,
) -> dict:
    blocks, context = build_locked_train_blocks(paths, lock=lock)
    return execute_ablation_train_on_blocks(
        ablation_id,
        seed,
        blocks,
        context=context,
        output_dir=output_dir,
        budget=budget,
        candidate_pool_size=candidate_pool_size,
        hyperparameters=hyperparameters,
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run one isolated CRMT ablation on frozen OpenCEM TRAIN blocks"
    )
    p.add_argument("--ablation", required=True, choices=list(ABLATION_IDS))
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_ablation_train(
        args.ablation,
        args.seed,
        paths,
        lock=lock,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
