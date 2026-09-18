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
    SITE_SENSITIVITY_VARIANTS,
    build_opencem_sensitivity_site,
)
from crmt_edge_ems.replay import MultiSiteReplayEvaluator
from crmt_edge_ems.risk import RiskConfig
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_internal_test import load_locked_selection
from opencem_qa import load_verified_csvs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _risk() -> RiskConfig:
    return RiskConfig(
        q=float(CRMT_HYPERPARAMETERS["risk_q"]),
        tail_weight=float(CRMT_HYPERPARAMETERS["tail_weight"]),
    )


def verify_primary_internal_test(
    primary_internal_dir: Path,
    *,
    selection_dir: Path,
    expected_manifest_sha256: str,
) -> dict:
    summary_path = primary_internal_dir / "internal_test_run_summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError("primary internal-test run summary is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("stage") != "ONE_SHOT_INTERNAL_TEST":
        raise RuntimeError("primary internal-test artifact has unexpected stage")
    selection_lock_path = selection_dir / "selection_lock.json"
    selected_path = selection_dir / "selected_candidates.csv"
    if not selection_lock_path.is_file() or not selected_path.is_file():
        raise FileNotFoundError("selection evidence is incomplete")
    if summary.get("selection_lock_sha256") != _sha256(selection_lock_path):
        raise RuntimeError("primary internal test used a different selection lock")
    selection_lock = json.loads(
        selection_lock_path.read_text(encoding="utf-8")
    )
    if (
        summary.get("selected_candidates_sha256")
        != selection_lock.get("selected_candidates_sha256")
    ):
        raise RuntimeError(
            "primary internal test used a different selected-candidate CSV"
        )
    if (
        summary.get("data_context", {}).get("manifest_sha256")
        != expected_manifest_sha256
    ):
        raise RuntimeError("primary internal test used a different block manifest")
    if int(summary.get("seed")) != int(selection_lock.get("seed")):
        raise RuntimeError("primary internal-test seed differs from selection seed")
    return summary


def _sites_for_variant(variant_id: str):
    return {
        1: build_opencem_sensitivity_site(1, variant_id),
        2: build_opencem_sensitivity_site(2, variant_id),
    }


def evaluate_variant(
    selected: pd.DataFrame,
    blocks,
    *,
    variant_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    evaluator = MultiSiteReplayEvaluator(
        _sites_for_variant(variant_id),
        method_id=f"SENSITIVITY_{variant_id}",
    )
    risk = _risk()
    metric_frames = []
    summary_rows = []
    for row in selected.itertuples(index=False):
        params = {
            name: float(getattr(row, name))
            for name in PARAM_NAMES
        }
        metrics = evaluator.evaluate(
            params,
            blocks,
            candidate_id=f"{row.method}:{row.candidate_id}",
        )
        if len(metrics) != INTERNAL_TEST_BLOCK_COUNT:
            raise RuntimeError(
                "sensitivity evaluation did not use all frozen internal-test blocks"
            )
        metrics.insert(0, "variant_id", variant_id)
        metrics.insert(1, "method", str(row.method))
        metrics.insert(2, "candidate_id", str(row.candidate_id))
        metric_frames.append(metrics)
        agg = evaluator.aggregate(metrics, risk)
        summary_rows.append(
            {
                "variant_id": variant_id,
                "method": str(row.method),
                "candidate_id": str(row.candidate_id),
                **{k: float(v) for k, v in agg.items()},
            }
        )
    return (
        pd.concat(metric_frames, ignore_index=True),
        pd.DataFrame(summary_rows),
    )


def execute_sensitivity_suite(
    paths: list[Path],
    *,
    block_lock: dict,
    selection_dir: Path,
    primary_internal_dir: Path,
    output_dir: Path,
) -> dict:
    expected_manifest_sha = str(block_lock["canonical_csv_sha256"])
    selected, selection_lock = load_locked_selection(
        selection_dir,
        expected_manifest_sha256=expected_manifest_sha,
    )
    primary_summary = verify_primary_internal_test(
        primary_internal_dir,
        selection_dir=selection_dir,
        expected_manifest_sha256=expected_manifest_sha,
    )
    blocks, context = build_locked_split_blocks(
        paths,
        lock=block_lock,
        split_name="internal_test",
    )
    if len(blocks) != INTERNAL_TEST_BLOCK_COUNT:
        raise RuntimeError("frozen internal-test block count mismatch")

    metric_parts = []
    summary_parts = []
    variant_ids = [v.variant_id for v in SITE_SENSITIVITY_VARIANTS]
    for variant_id in variant_ids:
        metrics, summary = evaluate_variant(
            selected,
            blocks,
            variant_id=variant_id,
        )
        metric_parts.append(metrics)
        summary_parts.append(summary)

    all_metrics = pd.concat(metric_parts, ignore_index=True)
    all_summary = pd.concat(summary_parts, ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "sensitivity_block_metrics.csv"
    summary_path = output_dir / "sensitivity_risk_summary.csv"
    all_metrics.to_csv(metrics_path, index=False, lineterminator="\n")
    all_summary.to_csv(summary_path, index=False, lineterminator="\n")

    run_summary = {
        "stage": "PREDECLARED_SITE_TEMPORAL_SENSITIVITY",
        "claim_boundary": (
            "Sensitivity analysis of already validation-frozen candidates. "
            "No retuning, reselection, or protocol change is authorized."
        ),
        "seed": int(selection_lock["seed"]),
        "variant_ids": variant_ids,
        "selection_lock_sha256": _sha256(
            selection_dir / "selection_lock.json"
        ),
        "selected_candidates_sha256": selection_lock[
            "selected_candidates_sha256"
        ],
        "primary_internal_test_summary_sha256": _sha256(
            primary_internal_dir / "internal_test_run_summary.json"
        ),
        "primary_internal_test_stage": primary_summary["stage"],
        "data_context": context,
        "risk": {
            "q": float(CRMT_HYPERPARAMETERS["risk_q"]),
            "tail_weight": float(CRMT_HYPERPARAMETERS["tail_weight"]),
            "objectives": list(_risk().objectives),
        },
        "files_sha256": {
            "sensitivity_block_metrics.csv": _sha256(metrics_path),
            "sensitivity_risk_summary.csv": _sha256(summary_path),
        },
    }
    (output_dir / "sensitivity_run_summary.json").write_text(
        json.dumps(run_summary, indent=2),
        encoding="utf-8",
    )
    return run_summary


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Run all predeclared OpenCEM site/temporal sensitivities on "
            "validation-frozen candidates"
        )
    )
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--selection-dir", type=Path, required=True)
    p.add_argument("--primary-internal-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(
        args.raw_root,
        args.verification_csv,
    )
    block_lock = json.loads(
        args.block_lock_json.read_text(encoding="utf-8")
    )
    result = execute_sensitivity_suite(
        paths,
        block_lock=block_lock,
        selection_dir=args.selection_dir,
        primary_internal_dir=args.primary_internal_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
