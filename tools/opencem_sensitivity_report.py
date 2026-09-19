from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from crmt_edge_ems.protocol import (
    METHOD_IDS,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    SITE_SENSITIVITY_VARIANTS,
    STATISTICAL_ALPHA,
    STATISTICAL_BOOTSTRAP_DRAWS,
    STATISTICAL_BOOTSTRAP_SEED,
)
from crmt_edge_ems.risk import DEFAULT_OBJECTIVES
from crmt_edge_ems.statistics import (
    holm_adjust,
    paired_bootstrap_median_difference,
    paired_rank_biserial,
)
from opencem_internal_test import _resolve_selection_dir
from opencem_sensitivity_suite import (
    _resolve_primary_internal_dir,
    verify_primary_internal_test,
)


VARIANT_IDS = tuple(v.variant_id for v in SITE_SENSITIVITY_VARIANTS)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_sensitivity_dir(root: Path, *, seed: int) -> Path:
    name = f"sensitivity_seed{int(seed)}"
    required = (
        "sensitivity_run_summary.json",
        "sensitivity_risk_summary.csv",
    )
    direct = root / name
    if all((direct / f).is_file() for f in required):
        return direct
    matches = sorted(
        p for p in root.rglob(name)
        if p.is_dir() and all((p / f).is_file() for f in required)
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one sensitivity directory {name!r}, found {len(matches)}"
        )
    return matches[0]


def _load_seed(
    seed: int,
    *,
    primary_selection_root: Path,
    primary_internal_root: Path,
    sensitivity_root: Path,
    expected_manifest_sha: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    selection_dir = _resolve_selection_dir(primary_selection_root, seed=seed)
    primary_dir = _resolve_primary_internal_dir(primary_internal_root, seed=seed)
    primary_summary = verify_primary_internal_test(
        primary_dir,
        selection_dir=selection_dir,
        expected_manifest_sha256=expected_manifest_sha,
    )
    primary_risk_path = primary_dir / "internal_test_risk_summary.csv"
    if _sha256(primary_risk_path) != primary_summary.get(
        "files_sha256", {}
    ).get("internal_test_risk_summary.csv"):
        raise RuntimeError(f"seed {seed}: primary internal risk hash mismatch")
    primary = pd.read_csv(primary_risk_path)
    if (
        len(primary) != len(METHOD_IDS)
        or set(primary["method"]) != set(METHOD_IDS)
        or primary["method"].duplicated().any()
    ):
        raise RuntimeError(f"seed {seed}: primary method registry mismatch")

    sensitivity_dir = _resolve_sensitivity_dir(sensitivity_root, seed=seed)
    summary_path = sensitivity_dir / "sensitivity_run_summary.json"
    risk_path = sensitivity_dir / "sensitivity_risk_summary.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("stage") != "PREDECLARED_SITE_TEMPORAL_SENSITIVITY":
        raise RuntimeError(f"seed {seed}: invalid sensitivity stage")
    if int(summary.get("seed")) != int(seed):
        raise RuntimeError(f"seed {seed}: sensitivity seed mismatch")
    if tuple(summary.get("variant_ids", [])) != VARIANT_IDS:
        raise RuntimeError(f"seed {seed}: sensitivity variant registry drift")
    if summary.get("selection_lock_sha256") != _sha256(
        selection_dir / "selection_lock.json"
    ):
        raise RuntimeError(f"seed {seed}: sensitivity selection-lock mismatch")
    if summary.get("primary_internal_test_summary_sha256") != _sha256(
        primary_dir / "internal_test_run_summary.json"
    ):
        raise RuntimeError(f"seed {seed}: sensitivity primary-internal mismatch")
    if summary.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha:
        raise RuntimeError(f"seed {seed}: sensitivity manifest mismatch")
    if _sha256(risk_path) != summary.get("files_sha256", {}).get(
        "sensitivity_risk_summary.csv"
    ):
        raise RuntimeError(f"seed {seed}: sensitivity risk-summary hash mismatch")

    sensitivity = pd.read_csv(risk_path)
    expected_rows = len(VARIANT_IDS) * len(METHOD_IDS)
    if len(sensitivity) != expected_rows:
        raise RuntimeError(f"seed {seed}: sensitivity row-count mismatch")
    if set(sensitivity["variant_id"]) != set(VARIANT_IDS):
        raise RuntimeError(f"seed {seed}: sensitivity variant set mismatch")
    for variant in VARIANT_IDS:
        part = sensitivity[sensitivity["variant_id"] == variant]
        if (
            len(part) != len(METHOD_IDS)
            or set(part["method"]) != set(METHOD_IDS)
            or part["method"].duplicated().any()
        ):
            raise RuntimeError(
                f"seed {seed}: incomplete method set for sensitivity {variant}"
            )

    primary.insert(0, "seed", int(seed))
    sensitivity.insert(0, "seed", int(seed))
    evidence = {
        "seed": int(seed),
        "selection_lock_sha256": _sha256(selection_dir / "selection_lock.json"),
        "primary_internal_summary_sha256": _sha256(
            primary_dir / "internal_test_run_summary.json"
        ),
        "primary_internal_risk_sha256": _sha256(primary_risk_path),
        "sensitivity_run_summary_sha256": _sha256(summary_path),
        "sensitivity_risk_summary_sha256": _sha256(risk_path),
    }
    return primary, sensitivity, evidence


def sensitivity_contrast_table(
    primary: pd.DataFrame,
    sensitivity: pd.DataFrame,
    *,
    n_boot: int,
    bootstrap_seed: int,
    alpha: float,
) -> pd.DataFrame:
    rows = []
    family_counter = 0
    for method in METHOD_IDS:
        pmethod = primary[primary["method"] == method].set_index("seed")
        for objective in DEFAULT_OBJECTIVES:
            family_rows = []
            raw_p = []
            base = pd.to_numeric(
                pmethod[objective], errors="raise"
            )
            for variant_index, variant in enumerate(VARIANT_IDS):
                smethod = sensitivity[
                    (sensitivity["method"] == method)
                    & (sensitivity["variant_id"] == variant)
                ].set_index("seed")
                common = base.index.intersection(smethod.index)
                if len(common) != len(base) or len(common) != len(smethod):
                    raise RuntimeError(
                        f"incomplete paired sensitivity design for {method}/{objective}/{variant}"
                    )
                a = pd.to_numeric(
                    smethod.loc[common, objective], errors="raise"
                ).to_numpy(dtype=float)
                b = base.loc[common].to_numpy(dtype=float)
                if not np.isfinite(a).all() or not np.isfinite(b).all():
                    raise ValueError("non-finite sensitivity comparison values")
                diff = a - b
                if np.allclose(diff, 0.0):
                    statistic, p_value = 0.0, 1.0
                else:
                    result = wilcoxon(
                        a,
                        b,
                        zero_method="wilcox",
                        alternative="two-sided",
                        method="auto",
                    )
                    statistic = float(result.statistic)
                    p_value = float(result.pvalue)
                effect = paired_rank_biserial(a, b)
                med, lo, hi = paired_bootstrap_median_difference(
                    a,
                    b,
                    n_boot=n_boot,
                    seed=(
                        int(bootstrap_seed)
                        + 10_000 * family_counter
                        + variant_index
                    ),
                    alpha=alpha,
                )
                family_rows.append(
                    {
                        "method": method,
                        "objective": objective,
                        "variant_id": variant,
                        "comparison": "sensitivity_minus_primary",
                        "metric_direction": "minimize",
                        "n_seeds": int(len(a)),
                        "wilcoxon_statistic": statistic,
                        "p_value_raw": p_value,
                        "rank_biserial_sensitivity_minus_primary": effect,
                        "median_difference_sensitivity_minus_primary": med,
                        "median_difference_ci_low": lo,
                        "median_difference_ci_high": hi,
                    }
                )
                raw_p.append(p_value)
            adjusted = holm_adjust(raw_p)
            for row, adj in zip(family_rows, adjusted):
                row["p_value_holm_within_method_objective"] = float(adj)
                row["alpha"] = float(alpha)
                rows.append(row)
            family_counter += 1
    return pd.DataFrame(rows)


def build_sensitivity_report(
    *,
    primary_selection_root: Path,
    primary_internal_root: Path,
    sensitivity_root: Path,
    block_lock: dict,
    output_dir: Path,
    seeds: Iterable[int] = OPTIMIZER_SEEDS,
) -> dict:
    seed_list = tuple(int(s) for s in seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    expected_manifest_sha = str(block_lock["canonical_csv_sha256"])

    primary_parts = []
    sensitivity_parts = []
    evidence = []
    for seed in seed_list:
        primary, sensitivity, ev = _load_seed(
            seed,
            primary_selection_root=primary_selection_root,
            primary_internal_root=primary_internal_root,
            sensitivity_root=sensitivity_root,
            expected_manifest_sha=expected_manifest_sha,
        )
        primary_parts.append(primary)
        sensitivity_parts.append(sensitivity)
        evidence.append(ev)

    primary = pd.concat(primary_parts, ignore_index=True)
    sensitivity = pd.concat(sensitivity_parts, ignore_index=True)
    contrasts = sensitivity_contrast_table(
        primary,
        sensitivity,
        n_boot=STATISTICAL_BOOTSTRAP_DRAWS,
        bootstrap_seed=STATISTICAL_BOOTSTRAP_SEED + 400_000,
        alpha=STATISTICAL_ALPHA,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "sensitivity_primary_seed_metrics.csv": primary,
        "sensitivity_variant_seed_metrics.csv": sensitivity,
        "sensitivity_paired_contrasts.csv": contrasts,
    }
    hashes = {}
    for name, frame in tables.items():
        path = output_dir / name
        frame.to_csv(path, index=False, lineterminator="\n")
        hashes[name] = _sha256(path)

    summary = {
        "stage": "SITE_TEMPORAL_SENSITIVITY_STATISTICAL_REPORT",
        "claim_boundary": (
            "Paired seed-level robustness contrasts of predeclared sensitivity "
            "variants against the frozen primary internal-test condition."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seed_list),
        "methods": list(METHOD_IDS),
        "objectives": list(DEFAULT_OBJECTIVES),
        "variant_ids": list(VARIANT_IDS),
        "statistical_protocol": {
            "inferential_unit": "optimizer_seed",
            "comparison": "sensitivity_minus_primary",
            "pairwise_test": "two-sided Wilcoxon signed-rank",
            "multiplicity": (
                "Holm across six variants separately within each method×objective family"
            ),
            "effect_size": "paired rank-biserial",
            "paired_bootstrap_draws": STATISTICAL_BOOTSTRAP_DRAWS,
            "paired_bootstrap_seed": STATISTICAL_BOOTSTRAP_SEED + 400_000,
            "alpha": STATISTICAL_ALPHA,
        },
        "source_evidence": evidence,
        "files_sha256": hashes,
    }
    (output_dir / "sensitivity_analysis_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build paired statistics for predeclared site/temporal sensitivities"
    )
    p.add_argument("--primary-selection-root", type=Path, required=True)
    p.add_argument("--primary-internal-root", type=Path, required=True)
    p.add_argument("--sensitivity-root", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    block_lock = json.loads(
        args.block_lock_json.read_text(encoding="utf-8")
    )
    summary = build_sensitivity_report(
        primary_selection_root=args.primary_selection_root,
        primary_internal_root=args.primary_internal_root,
        sensitivity_root=args.sensitivity_root,
        block_lock=block_lock,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
