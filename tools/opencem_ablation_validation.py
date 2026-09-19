from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from crmt_edge_ems.parameter_space import PARAM_NAMES
from crmt_edge_ems.protocol import (
    ABLATION_IDS,
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    VALIDATION_BLOCK_COUNT,
)
from crmt_edge_ems.selection import (
    score_validation_candidates_with_reference,
    select_one_per_method,
)
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_internal_test import _resolve_selection_dir
from opencem_qa import load_verified_csvs
from opencem_validation_select import _evaluate_front, _risk, _write_csv


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_ablation_train_dir(
    root: Path,
    *,
    ablation_id: str,
    seed: int,
) -> Path:
    name = f"{ablation_id}_seed{int(seed)}"
    direct = root / name
    if (direct / "run_summary.json").is_file() and (direct / "optimizer_front.csv").is_file():
        return direct
    matches = sorted(
        p for p in root.rglob(name)
        if p.is_dir()
        and (p / "run_summary.json").is_file()
        and (p / "optimizer_front.csv").is_file()
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one ablation TRAIN directory {name!r}, found {len(matches)}"
        )
    return matches[0]


def _read_ablation_front(
    run_dir: Path,
    *,
    ablation_id: str,
    seed: int,
    expected_manifest_sha: str,
) -> tuple[pd.DataFrame, dict]:
    summary_path = run_dir / "run_summary.json"
    front_path = run_dir / "optimizer_front.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("stage") != "CRMT_ABLATION_TRAIN_ONLY":
        raise RuntimeError("invalid ablation TRAIN stage")
    if summary.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError("ablation TRAIN protocol mismatch")
    if str(summary.get("ablation_id")) != ablation_id:
        raise RuntimeError("ablation TRAIN ID mismatch")
    if int(summary.get("seed")) != int(seed):
        raise RuntimeError("ablation TRAIN seed mismatch")
    if int(summary.get("controller_block_budget")) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
        raise RuntimeError("ablation TRAIN budget mismatch")
    if int(summary.get("ledger_used")) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
        raise RuntimeError("ablation TRAIN ledger mismatch")
    if summary.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha:
        raise RuntimeError("ablation TRAIN manifest mismatch")
    if _sha256(front_path) != summary.get("files_sha256", {}).get("optimizer_front.csv"):
        raise RuntimeError("ablation optimizer-front hash mismatch")

    front = pd.read_csv(front_path)
    if front.empty:
        raise RuntimeError("empty ablation optimizer front")
    missing = [p for p in PARAM_NAMES if p not in front.columns]
    if missing:
        raise KeyError(f"ablation front missing parameters: {missing}")
    if "candidate_id" not in front.columns:
        raise KeyError("ablation front missing candidate_id")
    clean = front[["candidate_id", *PARAM_NAMES]].copy()
    clean.insert(0, "method", ablation_id)
    if clean[["method", "candidate_id"]].duplicated().any():
        raise RuntimeError("duplicate ablation front candidate IDs")
    return clean, {
        "run_summary_sha256": _sha256(summary_path),
        "optimizer_front_sha256": _sha256(front_path),
    }


def execute_ablation_validation_on_blocks(
    ablation_id: str,
    seed: int,
    validation_blocks,
    *,
    context: dict,
    expected_manifest_sha: str,
    ablation_train_root: Path,
    primary_selection_root: Path,
    output_dir: Path,
) -> dict:
    ablation_id = str(ablation_id).upper()
    seed = int(seed)
    if ablation_id not in ABLATION_IDS:
        raise ValueError(f"ablation_id must be one of {ABLATION_IDS}")
    if seed not in OPTIMIZER_SEEDS:
        raise ValueError("seed outside frozen registry")
    if len(validation_blocks) != VALIDATION_BLOCK_COUNT:
        raise RuntimeError("validation block count mismatch")

    primary_dir = _resolve_selection_dir(primary_selection_root, seed=seed)
    primary_lock_path = primary_dir / "selection_lock.json"
    primary_lock = json.loads(primary_lock_path.read_text(encoding="utf-8"))
    if primary_lock.get("stage") != "VALIDATION_SELECTION_LOCK":
        raise RuntimeError("invalid primary validation selection stage")
    if primary_lock.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError("primary validation protocol mismatch")
    if int(primary_lock.get("seed")) != seed:
        raise RuntimeError("primary validation seed mismatch")
    if primary_lock.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha:
        raise RuntimeError("primary validation manifest mismatch")
    refs = primary_lock.get("normalization_reference")
    if not isinstance(refs, dict) or not refs:
        raise RuntimeError("primary validation normalization reference missing")

    train_dir = _resolve_ablation_train_dir(
        ablation_train_root,
        ablation_id=ablation_id,
        seed=seed,
    )
    front, train_evidence = _read_ablation_front(
        train_dir,
        ablation_id=ablation_id,
        seed=seed,
        expected_manifest_sha=expected_manifest_sha,
    )

    raw_scores, block_metrics = _evaluate_front(front, validation_blocks)
    scored = score_validation_candidates_with_reference(
        raw_scores,
        objectives=_risk().objectives,
        references=refs,
    )
    selected = select_one_per_method(scored)
    if len(selected) != 1 or selected.iloc[0]["method"] != ablation_id:
        raise RuntimeError("ablation validation did not select exactly one candidate")

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    files["ablation_validation_candidate_scores.csv"] = _write_csv(
        scored, output_dir / "ablation_validation_candidate_scores.csv"
    )
    files["ablation_validation_block_metrics.csv"] = _write_csv(
        block_metrics, output_dir / "ablation_validation_block_metrics.csv"
    )
    files["selected_ablation_candidate.csv"] = _write_csv(
        selected, output_dir / "selected_ablation_candidate.csv"
    )

    lock = {
        "stage": "CRMT_ABLATION_VALIDATION_SELECTION_LOCK",
        "claim_boundary": (
            "Ablation candidate selected on frozen validation blocks only. "
            "Primary validation normalization and primary held-out risk functional "
            "are reused; internal-test data are not accessed."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "ablation_id": ablation_id,
        "seed": seed,
        "data_context": dict(context),
        "primary_selection_lock_sha256": _sha256(primary_lock_path),
        "primary_normalization_reference": refs,
        "ablation_train_source": train_evidence,
        "heldout_risk": {
            "q": float(_risk().q),
            "tail_weight": float(_risk().tail_weight),
            "objectives": list(_risk().objectives),
        },
        "files_sha256": files,
        "selected_ablation_candidate_sha256": files[
            "selected_ablation_candidate.csv"
        ],
    }
    (output_dir / "ablation_selection_lock.json").write_text(
        json.dumps(lock, indent=2), encoding="utf-8"
    )
    return lock


def main() -> int:
    p = argparse.ArgumentParser(
        description="Select one CRMT ablation candidate on frozen validation blocks"
    )
    p.add_argument("--ablation", required=True, choices=list(ABLATION_IDS))
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--ablation-train-root", type=Path, required=True)
    p.add_argument("--primary-selection-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    block_lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="validation"
    )
    result = execute_ablation_validation_on_blocks(
        args.ablation,
        args.seed,
        blocks,
        context=context,
        expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
        ablation_train_root=args.ablation_train_root,
        primary_selection_root=args.primary_selection_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
