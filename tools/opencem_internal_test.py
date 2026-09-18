from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from crmt_edge_ems.parameter_space import PARAM_NAMES
from crmt_edge_ems.protocol import (
    CRMT_HYPERPARAMETERS,
    INTERNAL_TEST_BLOCK_COUNT,
    METHOD_IDS,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    SELECTION_RULE_ID,
)
from crmt_edge_ems.replay import MultiSiteReplayEvaluator
from crmt_edge_ems.risk import RiskConfig
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


def load_locked_selection(
    selection_dir: Path,
    *,
    expected_manifest_sha256: str,
) -> tuple[pd.DataFrame, dict]:
    lock_path = selection_dir / "selection_lock.json"
    selected_path = selection_dir / "selected_candidates.csv"
    if not lock_path.is_file() or not selected_path.is_file():
        raise FileNotFoundError("selection lock or selected candidate CSV missing")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("stage") != "VALIDATION_SELECTION_LOCK":
        raise RuntimeError("unexpected selection-lock stage")
    if lock.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError("selection protocol version mismatch")
    if lock.get("selection_rule_id") != SELECTION_RULE_ID:
        raise RuntimeError("selection rule mismatch")
    if lock.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha256:
        raise RuntimeError("selection block-manifest mismatch")
    expected = lock.get("selected_candidates_sha256")
    if not expected or _sha256(selected_path) != expected:
        raise RuntimeError("selected_candidates.csv hash mismatch")

    selected = pd.read_csv(selected_path)
    required = {"method", "candidate_id", *PARAM_NAMES}
    missing = sorted(required - set(selected.columns))
    if missing:
        raise KeyError(f"selected candidate table missing columns: {missing}")
    if len(selected) != len(METHOD_IDS) or set(selected["method"]) != set(METHOD_IDS):
        raise RuntimeError("selection must contain exactly one row per frozen method")
    if selected["method"].duplicated().any():
        raise RuntimeError("duplicate method in selection")
    seed = int(lock["seed"])
    if seed not in OPTIMIZER_SEEDS:
        raise RuntimeError("selection seed is outside frozen registry")
    return selected, lock


def _resolve_selection_dir(selection_root: Path, *, seed: int) -> Path:
    """Locate exactly one hash-locked validation selection bundle for a seed."""
    name = f"validation_selection_seed{int(seed)}"
    direct = selection_root / name
    if (direct / "selection_lock.json").is_file() and (direct / "selected_candidates.csv").is_file():
        return direct
    matches = sorted(
        p for p in selection_root.rglob(name)
        if p.is_dir()
        and (p / "selection_lock.json").is_file()
        and (p / "selected_candidates.csv").is_file()
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one selection directory {name!r}, found {len(matches)}"
        )
    return matches[0]


def execute_internal_test_on_blocks(
    blocks,
    *,
    context: dict,
    expected_manifest_sha: str,
    selection_dir: Path,
    output_dir: Path,
) -> dict:
    selected, selection_lock = load_locked_selection(
        selection_dir,
        expected_manifest_sha256=expected_manifest_sha,
    )
    if len(blocks) != INTERNAL_TEST_BLOCK_COUNT:
        raise RuntimeError("frozen internal-test block count mismatch")

    evaluator = MultiSiteReplayEvaluator(
        _sites(), method_id="ONE_SHOT_INTERNAL_TEST"
    )
    risk = _risk()
    metric_frames = []
    summary_rows = []
    for row in selected.itertuples(index=False):
        params = {name: float(getattr(row, name)) for name in PARAM_NAMES}
        metrics = evaluator.evaluate(
            params,
            blocks,
            candidate_id=f"{row.method}:{row.candidate_id}",
        )
        if len(metrics) != INTERNAL_TEST_BLOCK_COUNT:
            raise RuntimeError("internal-test block count changed during evaluation")
        metrics.insert(0, "candidate_id", str(row.candidate_id))
        metrics.insert(0, "method", str(row.method))
        metric_frames.append(metrics)
        agg = evaluator.aggregate(metrics, risk)
        summary_rows.append(
            {
                "method": str(row.method),
                "candidate_id": str(row.candidate_id),
                **{k: float(v) for k, v in agg.items()},
            }
        )

    block_metrics = pd.concat(metric_frames, ignore_index=True)
    risk_summary = pd.DataFrame(summary_rows).sort_values("method").reset_index(drop=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    block_path = output_dir / "internal_test_block_metrics.csv"
    summary_path = output_dir / "internal_test_risk_summary.csv"
    block_metrics.to_csv(block_path, index=False, lineterminator="\n")
    risk_summary.to_csv(summary_path, index=False, lineterminator="\n")

    run_summary = {
        "stage": "ONE_SHOT_INTERNAL_TEST",
        "claim_boundary": (
            "These results evaluate candidates already frozen by validation. "
            "No retuning or reselection is authorized from internal-test outcomes."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "selection_rule_id": SELECTION_RULE_ID,
        "seed": int(selection_lock["seed"]),
        "selection_lock_sha256": _sha256(selection_dir / "selection_lock.json"),
        "selected_candidates_sha256": selection_lock["selected_candidates_sha256"],
        "data_context": dict(context),
        "risk": {
            "q": float(CRMT_HYPERPARAMETERS["risk_q"]),
            "tail_weight": float(CRMT_HYPERPARAMETERS["tail_weight"]),
            "objectives": list(risk.objectives),
        },
        "files_sha256": {
            "internal_test_block_metrics.csv": _sha256(block_path),
            "internal_test_risk_summary.csv": _sha256(summary_path),
        },
    }
    out = output_dir / "internal_test_run_summary.json"
    out.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    return run_summary


def execute_internal_test(
    paths: list[Path],
    *,
    block_lock: dict,
    selection_dir: Path,
    output_dir: Path,
) -> dict:
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="internal_test"
    )
    return execute_internal_test_on_blocks(
        blocks,
        context=context,
        expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
        selection_dir=selection_dir,
        output_dir=output_dir,
    )


def main() -> int:
    p = argparse.ArgumentParser(
        description="Evaluate hash-locked validation selections once on internal test"
    )
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--selection-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    block_lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_internal_test(
        paths,
        block_lock=block_lock,
        selection_dir=args.selection_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
