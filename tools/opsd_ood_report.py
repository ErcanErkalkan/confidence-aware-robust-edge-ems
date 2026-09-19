from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from crmt_edge_ems.protocol import (
    METHOD_IDS,
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_ood_seed_dir(root: Path, *, seed: int) -> Path:
    name = f"opsd_ood_seed{int(seed)}"
    required = (
        "ood_run_summary.json",
        "ood_macro_risk_summary.csv",
        "ood_stratum_risk_summary.csv",
        "ood_pooled_risk_summary.csv",
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
            f"expected exactly one OPSD OOD evidence directory {name!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _load_seed(seed: int, *, ood_root: Path) -> tuple[pd.DataFrame, dict]:
    run_dir = _resolve_ood_seed_dir(ood_root, seed=seed)
    summary_path = run_dir / "ood_run_summary.json"
    macro_path = run_dir / "ood_macro_risk_summary.csv"
    strata_path = run_dir / "ood_stratum_risk_summary.csv"
    pooled_path = run_dir / "ood_pooled_risk_summary.csv"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("stage") != "EXTERNAL_OOD_OPSD_FROZEN_SELECTION":
        raise RuntimeError(f"seed {seed}: invalid OOD stage")
    if summary.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError(f"seed {seed}: OOD protocol mismatch")
    if int(summary.get("seed")) != int(seed):
        raise RuntimeError(f"seed {seed}: OOD seed mismatch")
    if not summary.get("selection_lock_sha256"):
        raise RuntimeError(f"seed {seed}: missing selection-lock hash")
    if not summary.get("primary_internal_test_summary_sha256"):
        raise RuntimeError(f"seed {seed}: missing primary internal-test evidence hash")

    files = summary.get("files_sha256", {})
    for name, path in (
        ("ood_macro_risk_summary.csv", macro_path),
        ("ood_stratum_risk_summary.csv", strata_path),
        ("ood_pooled_risk_summary.csv", pooled_path),
    ):
        if _sha256(path) != files.get(name):
            raise RuntimeError(f"seed {seed}: hash mismatch for {name}")

    macro = pd.read_csv(macro_path)
    if (
        len(macro) != len(METHOD_IDS)
        or set(macro["method"]) != set(METHOD_IDS)
        or macro["method"].duplicated().any()
    ):
        raise RuntimeError(
            f"seed {seed}: OOD macro summary must contain one row per method"
        )
    missing = [m for m in DEFAULT_OBJECTIVES if m not in macro.columns]
    if missing:
        raise KeyError(f"seed {seed}: OOD macro objectives missing {missing}")
    if "n_strata" not in macro.columns or not (macro["n_strata"] == 6).all():
        raise RuntimeError(f"seed {seed}: OOD macro summary is not six-stratum")
    if (
        "macro_weighting" not in macro.columns
        or not (macro["macro_weighting"] == "equal_household_x_target_site").all()
    ):
        raise RuntimeError(f"seed {seed}: OOD macro weighting drift")

    macro.insert(0, "seed", int(seed))
    evidence = {
        "seed": int(seed),
        "ood_run_summary_sha256": _sha256(summary_path),
        "ood_macro_risk_summary_sha256": _sha256(macro_path),
        "ood_stratum_risk_summary_sha256": _sha256(strata_path),
        "ood_pooled_risk_summary_sha256": _sha256(pooled_path),
        "selection_lock_sha256": summary["selection_lock_sha256"],
        "selected_candidates_sha256": summary["selected_candidates_sha256"],
        "primary_internal_test_summary_sha256": summary[
            "primary_internal_test_summary_sha256"
        ],
        "opsd_package_sha256": summary.get("source_context", {}).get(
            "package_sha256"
        ),
        "opsd_full_replay_manifest_sha256": summary.get(
            "source_context", {}
        ).get("full_replay_manifest_sha256"),
    }
    return macro, evidence


def build_opsd_ood_report(
    *,
    ood_root: Path,
    output_dir: Path,
    seeds: Iterable[int] = OPTIMIZER_SEEDS,
) -> dict:
    seed_list = tuple(int(s) for s in seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")

    parts = []
    evidence = []
    for seed in seed_list:
        macro, ev = _load_seed(seed, ood_root=ood_root)
        parts.append(macro)
        evidence.append(ev)

    seed_metrics = pd.concat(parts, ignore_index=True)
    expected = len(seed_list) * len(METHOD_IDS)
    if len(seed_metrics) != expected:
        raise RuntimeError("OOD paired seed-method design is incomplete")

    direction = {m: "minimize" for m in DEFAULT_OBJECTIVES}
    desc = descriptive_table(seed_metrics, metrics=DEFAULT_OBJECTIVES)
    friedman = friedman_table(
        seed_metrics,
        metrics=DEFAULT_OBJECTIVES,
        methods=METHOD_IDS,
    )
    pairwise = pairwise_paired_table(
        seed_metrics,
        metrics=DEFAULT_OBJECTIVES,
        methods=METHOD_IDS,
        n_boot=STATISTICAL_BOOTSTRAP_DRAWS,
        bootstrap_seed=STATISTICAL_BOOTSTRAP_SEED + 200_000,
        alpha=STATISTICAL_ALPHA,
        direction=direction,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "ood_macro_seed_metrics.csv": seed_metrics,
        "ood_macro_descriptive.csv": desc,
        "ood_macro_friedman.csv": friedman,
        "ood_macro_pairwise_wilcoxon_holm.csv": pairwise,
    }
    hashes = {}
    for name, frame in tables.items():
        path = output_dir / name
        frame.to_csv(path, index=False, lineterminator="\n")
        hashes[name] = _sha256(path)

    package_hashes = {e["opsd_package_sha256"] for e in evidence}
    replay_hashes = {e["opsd_full_replay_manifest_sha256"] for e in evidence}
    if len(package_hashes) != 1 or len(replay_hashes) != 1:
        raise RuntimeError("OPSD OOD source-lock identity differs across seeds")

    summary = {
        "stage": "OPSD_OOD_STATISTICAL_REPORT",
        "claim_boundary": (
            "Machine-generated paired statistics from hash-verified external-OOD "
            "macro summaries. Seed is the inferential replication unit; OOD "
            "blocks/strata are not treated as independent optimizer replicates."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seed_list),
        "methods": list(METHOD_IDS),
        "objectives": list(DEFAULT_OBJECTIVES),
        "primary_ood_aggregation": "equal_household_x_target_site",
        "n_primary_strata": 6,
        "statistical_protocol": {
            "alpha": STATISTICAL_ALPHA,
            "paired_bootstrap_draws": STATISTICAL_BOOTSTRAP_DRAWS,
            "paired_bootstrap_seed": STATISTICAL_BOOTSTRAP_SEED + 200_000,
            "pairwise_test": "two-sided Wilcoxon signed-rank",
            "multiplicity": "Holm within each OOD objective family",
            "omnibus": "Friedman repeated-measures",
            "effect_size": "paired rank-biserial",
            "inferential_unit": "optimizer_seed",
        },
        "opsd_package_sha256": next(iter(package_hashes)),
        "opsd_full_replay_manifest_sha256": next(iter(replay_hashes)),
        "source_evidence": evidence,
        "files_sha256": hashes,
    }
    (output_dir / "ood_analysis_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build paired statistics from frozen OPSD OOD evidence"
    )
    p.add_argument("--ood-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    summary = build_opsd_ood_report(
        ood_root=args.ood_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
