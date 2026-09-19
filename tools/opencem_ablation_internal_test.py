from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from crmt_edge_ems.parameter_space import PARAM_NAMES
from crmt_edge_ems.protocol import (
    ABLATION_IDS,
    INTERNAL_TEST_BLOCK_COUNT,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
)
from crmt_edge_ems.replay import MultiSiteReplayEvaluator
from crmt_edge_ems.site_model import build_primary_opencem_site
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_qa import load_verified_csvs
from opencem_validation_select import _risk


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sites():
    return {1: build_primary_opencem_site(1), 2: build_primary_opencem_site(2)}


def _resolve_ablation_selection_dir(
    root: Path,
    *,
    ablation_id: str,
    seed: int,
) -> Path:
    name = f"{ablation_id}_validation_seed{int(seed)}"
    direct = root / name
    if (direct / "ablation_selection_lock.json").is_file() and (
        direct / "selected_ablation_candidate.csv"
    ).is_file():
        return direct
    matches = sorted(
        p for p in root.rglob(name)
        if p.is_dir()
        and (p / "ablation_selection_lock.json").is_file()
        and (p / "selected_ablation_candidate.csv").is_file()
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one ablation selection directory {name!r}, found {len(matches)}"
        )
    return matches[0]


def load_ablation_selection(
    selection_dir: Path,
    *,
    ablation_id: str,
    seed: int,
    expected_manifest_sha: str,
) -> tuple[pd.DataFrame, dict]:
    lock_path = selection_dir / "ablation_selection_lock.json"
    selected_path = selection_dir / "selected_ablation_candidate.csv"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("stage") != "CRMT_ABLATION_VALIDATION_SELECTION_LOCK":
        raise RuntimeError("invalid ablation selection stage")
    if lock.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError("ablation selection protocol mismatch")
    if str(lock.get("ablation_id")) != ablation_id:
        raise RuntimeError("ablation selection ID mismatch")
    if int(lock.get("seed")) != int(seed):
        raise RuntimeError("ablation selection seed mismatch")
    if lock.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha:
        raise RuntimeError("ablation selection manifest mismatch")
    if _sha256(selected_path) != lock.get(
        "selected_ablation_candidate_sha256"
    ):
        raise RuntimeError("selected ablation candidate hash mismatch")
    selected = pd.read_csv(selected_path)
    missing = [p for p in PARAM_NAMES if p not in selected.columns]
    if missing:
        raise KeyError(f"selected ablation candidate missing params {missing}")
    if len(selected) != 1 or selected.iloc[0]["method"] != ablation_id:
        raise RuntimeError("ablation selection must contain one matching row")
    return selected, lock


def execute_ablation_internal_on_blocks(
    ablation_id: str,
    seed: int,
    blocks,
    *,
    context: dict,
    expected_manifest_sha: str,
    selection_dir: Path,
    output_dir: Path,
) -> dict:
    ablation_id = str(ablation_id).upper()
    seed = int(seed)
    if ablation_id not in ABLATION_IDS:
        raise ValueError(f"ablation_id must be one of {ABLATION_IDS}")
    if seed not in OPTIMIZER_SEEDS:
        raise ValueError("seed outside frozen registry")
    if len(blocks) != INTERNAL_TEST_BLOCK_COUNT:
        raise RuntimeError("internal-test block count mismatch")

    selected, lock = load_ablation_selection(
        selection_dir,
        ablation_id=ablation_id,
        seed=seed,
        expected_manifest_sha=expected_manifest_sha,
    )
    row = next(selected.itertuples(index=False))
    params = {name: float(getattr(row, name)) for name in PARAM_NAMES}
    evaluator = MultiSiteReplayEvaluator(
        _sites(), method_id=f"ABLATION_INTERNAL_{ablation_id}"
    )
    metrics = evaluator.evaluate(
        params,
        blocks,
        candidate_id=f"{ablation_id}:{row.candidate_id}",
    )
    if len(metrics) != INTERNAL_TEST_BLOCK_COUNT:
        raise RuntimeError("ablation internal-test block count changed")
    metrics.insert(0, "candidate_id", str(row.candidate_id))
    metrics.insert(0, "method", ablation_id)
    agg = evaluator.aggregate(metrics, _risk())
    summary_frame = pd.DataFrame(
        [{
            "method": ablation_id,
            "candidate_id": str(row.candidate_id),
            **{k: float(v) for k, v in agg.items()},
        }]
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "ablation_internal_block_metrics.csv"
    risk_path = output_dir / "ablation_internal_risk_summary.csv"
    metrics.to_csv(metrics_path, index=False, lineterminator="\n")
    summary_frame.to_csv(risk_path, index=False, lineterminator="\n")

    run_summary = {
        "stage": "CRMT_ABLATION_ONE_SHOT_INTERNAL_TEST",
        "claim_boundary": (
            "One-shot internal-test evaluation of validation-frozen ablation "
            "candidate under the primary held-out risk functional. No retuning."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "ablation_id": ablation_id,
        "seed": seed,
        "ablation_selection_lock_sha256": _sha256(
            selection_dir / "ablation_selection_lock.json"
        ),
        "selected_ablation_candidate_sha256": lock[
            "selected_ablation_candidate_sha256"
        ],
        "data_context": dict(context),
        "heldout_risk": {
            "q": float(_risk().q),
            "tail_weight": float(_risk().tail_weight),
            "objectives": list(_risk().objectives),
        },
        "files_sha256": {
            "ablation_internal_block_metrics.csv": _sha256(metrics_path),
            "ablation_internal_risk_summary.csv": _sha256(risk_path),
        },
    }
    (output_dir / "ablation_internal_run_summary.json").write_text(
        json.dumps(run_summary, indent=2), encoding="utf-8"
    )
    return run_summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="One-shot internal test of a validation-frozen CRMT ablation"
    )
    p.add_argument("--ablation", required=True, choices=list(ABLATION_IDS))
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--selection-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    block_lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="internal_test"
    )
    result = execute_ablation_internal_on_blocks(
        args.ablation,
        args.seed,
        blocks,
        context=context,
        expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
        selection_dir=args.selection_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
