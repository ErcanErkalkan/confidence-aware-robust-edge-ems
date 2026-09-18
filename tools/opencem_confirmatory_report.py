from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from crmt_edge_ems.indicators import validation_optimizer_indicators
from crmt_edge_ems.protocol import (
    CRMT_HYPERPARAMETERS,
    METHOD_IDS,
    OPTIMIZER_HV_REFERENCE,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    STATISTICAL_ALPHA,
    STATISTICAL_BOOTSTRAP_DRAWS,
    STATISTICAL_BOOTSTRAP_SEED,
)
from crmt_edge_ems.risk import DEFAULT_OBJECTIVES
from crmt_edge_ems.statistics import (
    descriptive_table,
    friedman_table,
    pairwise_paired_table,
)


QUALITY_METRICS = ("hypervolume", "igd_plus", "additive_epsilon")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_seed_evidence(
    seed: int,
    *,
    validation_root: Path,
    internal_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    validation_dir = validation_root / f"validation_selection_seed{seed}"
    internal_dir = internal_root / f"internal_test_seed{seed}"

    selection_lock_path = validation_dir / "selection_lock.json"
    validation_scores_path = validation_dir / "validation_candidate_scores.csv"
    selected_path = validation_dir / "selected_candidates.csv"
    internal_summary_path = internal_dir / "internal_test_run_summary.json"
    internal_risk_path = internal_dir / "internal_test_risk_summary.csv"

    required = [
        selection_lock_path,
        validation_scores_path,
        selected_path,
        internal_summary_path,
        internal_risk_path,
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"seed {seed}: missing confirmatory evidence files: {missing}"
        )

    selection_lock = json.loads(
        selection_lock_path.read_text(encoding="utf-8")
    )
    internal_summary = json.loads(
        internal_summary_path.read_text(encoding="utf-8")
    )
    if selection_lock.get("stage") != "VALIDATION_SELECTION_LOCK":
        raise RuntimeError(f"seed {seed}: invalid validation-selection stage")
    if selection_lock.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError(f"seed {seed}: validation protocol mismatch")
    if int(selection_lock.get("seed")) != int(seed):
        raise RuntimeError(f"seed {seed}: validation seed mismatch")
    if (
        _sha256(validation_scores_path)
        != selection_lock.get("files_sha256", {}).get(
            "validation_candidate_scores.csv"
        )
    ):
        raise RuntimeError(
            f"seed {seed}: validation candidate score hash mismatch"
        )
    if _sha256(selected_path) != selection_lock.get(
        "selected_candidates_sha256"
    ):
        raise RuntimeError(
            f"seed {seed}: selected candidate hash mismatch"
        )

    if internal_summary.get("stage") != "ONE_SHOT_INTERNAL_TEST":
        raise RuntimeError(f"seed {seed}: invalid internal-test stage")
    if internal_summary.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError(f"seed {seed}: internal-test protocol mismatch")
    if int(internal_summary.get("seed")) != int(seed):
        raise RuntimeError(f"seed {seed}: internal-test seed mismatch")
    if (
        internal_summary.get("selection_lock_sha256")
        != _sha256(selection_lock_path)
    ):
        raise RuntimeError(
            f"seed {seed}: internal test did not use exact selection lock"
        )
    if (
        internal_summary.get("selected_candidates_sha256")
        != selection_lock.get("selected_candidates_sha256")
    ):
        raise RuntimeError(
            f"seed {seed}: internal test selected-candidate hash mismatch"
        )
    if (
        _sha256(internal_risk_path)
        != internal_summary.get("files_sha256", {}).get(
            "internal_test_risk_summary.csv"
        )
    ):
        raise RuntimeError(
            f"seed {seed}: internal risk-summary hash mismatch"
        )

    validation = pd.read_csv(validation_scores_path)
    internal = pd.read_csv(internal_risk_path)
    if set(validation["method"]) != set(METHOD_IDS):
        raise RuntimeError(f"seed {seed}: validation method set mismatch")
    if (
        len(internal) != len(METHOD_IDS)
        or set(internal["method"]) != set(METHOD_IDS)
        or internal["method"].duplicated().any()
    ):
        raise RuntimeError(
            f"seed {seed}: internal summary must contain one row per method"
        )

    validation.insert(0, "seed", int(seed))
    internal.insert(0, "seed", int(seed))
    evidence = {
        "seed": int(seed),
        "selection_lock_sha256": _sha256(selection_lock_path),
        "validation_candidate_scores_sha256": _sha256(
            validation_scores_path
        ),
        "selected_candidates_sha256": _sha256(selected_path),
        "internal_test_run_summary_sha256": _sha256(
            internal_summary_path
        ),
        "internal_test_risk_summary_sha256": _sha256(
            internal_risk_path
        ),
        "manifest_sha256": selection_lock.get(
            "data_context", {}
        ).get("manifest_sha256"),
    }
    if (
        internal_summary.get("data_context", {}).get("manifest_sha256")
        != evidence["manifest_sha256"]
    ):
        raise RuntimeError(f"seed {seed}: data-manifest hash mismatch")
    return validation, internal, evidence


def build_confirmatory_report(
    *,
    validation_root: Path,
    internal_root: Path,
    output_dir: Path,
    seeds: Iterable[int] = OPTIMIZER_SEEDS,
) -> dict:
    seed_list = tuple(int(s) for s in seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")

    validation_parts = []
    internal_parts = []
    quality_parts = []
    evidence = []

    for seed in seed_list:
        validation, internal, seed_evidence = _load_seed_evidence(
            seed,
            validation_root=validation_root,
            internal_root=internal_root,
        )
        validation_parts.append(validation)
        internal_parts.append(internal)
        indicators, refs = validation_optimizer_indicators(
            validation,
            objectives=DEFAULT_OBJECTIVES,
            hv_reference_value=OPTIMIZER_HV_REFERENCE,
        )
        indicators.insert(0, "seed", int(seed))
        quality_parts.append(indicators)
        seed_evidence["optimizer_quality_normalization"] = refs
        evidence.append(seed_evidence)

    internal_seed = pd.concat(internal_parts, ignore_index=True)
    quality_seed = pd.concat(quality_parts, ignore_index=True)

    expected_method_rows = len(seed_list) * len(METHOD_IDS)
    if len(internal_seed) != expected_method_rows:
        raise RuntimeError("internal paired seed-method design is incomplete")
    if len(quality_seed) != expected_method_rows:
        raise RuntimeError("optimizer-quality paired seed-method design is incomplete")

    internal_direction = {m: "minimize" for m in DEFAULT_OBJECTIVES}
    quality_direction = {
        "hypervolume": "maximize",
        "igd_plus": "minimize",
        "additive_epsilon": "minimize",
    }

    internal_desc = descriptive_table(
        internal_seed,
        metrics=DEFAULT_OBJECTIVES,
    )
    internal_friedman = friedman_table(
        internal_seed,
        metrics=DEFAULT_OBJECTIVES,
        methods=METHOD_IDS,
    )
    internal_pairwise = pairwise_paired_table(
        internal_seed,
        metrics=DEFAULT_OBJECTIVES,
        methods=METHOD_IDS,
        n_boot=STATISTICAL_BOOTSTRAP_DRAWS,
        bootstrap_seed=STATISTICAL_BOOTSTRAP_SEED,
        alpha=STATISTICAL_ALPHA,
        direction=internal_direction,
    )

    quality_desc = descriptive_table(
        quality_seed,
        metrics=QUALITY_METRICS,
    )
    quality_friedman = friedman_table(
        quality_seed,
        metrics=QUALITY_METRICS,
        methods=METHOD_IDS,
    )
    quality_pairwise = pairwise_paired_table(
        quality_seed,
        metrics=QUALITY_METRICS,
        methods=METHOD_IDS,
        n_boot=STATISTICAL_BOOTSTRAP_DRAWS,
        bootstrap_seed=STATISTICAL_BOOTSTRAP_SEED + 100_000,
        alpha=STATISTICAL_ALPHA,
        direction=quality_direction,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "internal_seed_metrics.csv": internal_seed,
        "internal_descriptive.csv": internal_desc,
        "internal_friedman.csv": internal_friedman,
        "internal_pairwise_wilcoxon_holm.csv": internal_pairwise,
        "optimizer_quality_seed.csv": quality_seed,
        "optimizer_quality_descriptive.csv": quality_desc,
        "optimizer_quality_friedman.csv": quality_friedman,
        "optimizer_quality_pairwise_wilcoxon_holm.csv": quality_pairwise,
    }
    hashes = {}
    for name, frame in tables.items():
        path = output_dir / name
        frame.to_csv(path, index=False, lineterminator="\n")
        hashes[name] = _sha256(path)

    summary = {
        "stage": "CONFIRMATORY_STATISTICAL_REPORT",
        "claim_boundary": (
            "Machine-generated statistical/optimizer-quality tables from "
            "hash-verified validation and one-shot internal-test evidence."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seed_list),
        "methods": list(METHOD_IDS),
        "internal_objectives": list(DEFAULT_OBJECTIVES),
        "optimizer_quality_metrics": list(QUALITY_METRICS),
        "statistical_protocol": {
            "alpha": STATISTICAL_ALPHA,
            "paired_bootstrap_draws": STATISTICAL_BOOTSTRAP_DRAWS,
            "paired_bootstrap_seed": STATISTICAL_BOOTSTRAP_SEED,
            "pairwise_test": "two-sided Wilcoxon signed-rank",
            "multiplicity": "Holm within each metric family",
            "omnibus": "Friedman repeated-measures",
            "effect_size": "paired rank-biserial",
        },
        "optimizer_quality_protocol": {
            "source": "validation-re-evaluated TRAIN-front candidates",
            "hypervolume_reference": OPTIMIZER_HV_REFERENCE,
            "reference_front": "per-seed nondominated union of normalized candidate scores",
        },
        "source_evidence": evidence,
        "files_sha256": hashes,
    }
    (output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build prelocked confirmatory statistics from frozen evidence"
    )
    p.add_argument("--validation-root", type=Path, required=True)
    p.add_argument("--internal-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    summary = build_confirmatory_report(
        validation_root=args.validation_root,
        internal_root=args.internal_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
