from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from crmt_edge_ems.protocol import (
    ABLATION_IDS,
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
from opencem_internal_test import _resolve_selection_dir
from opencem_sensitivity_suite import (
    _resolve_primary_internal_dir,
    verify_primary_internal_test,
)


ABLATION_COMPARISON_METHODS = ("CRMT", *ABLATION_IDS)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_ablation_internal_dir(
    root: Path,
    *,
    ablation_id: str,
    seed: int,
) -> Path:
    name = f"{ablation_id}_internal_seed{int(seed)}"
    required = (
        "ablation_internal_run_summary.json",
        "ablation_internal_risk_summary.csv",
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
            f"expected exactly one ablation internal directory {name!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def _load_primary_crmt(
    seed: int,
    *,
    primary_selection_root: Path,
    primary_internal_root: Path,
    expected_manifest_sha: str,
) -> tuple[dict, dict]:
    selection_dir = _resolve_selection_dir(primary_selection_root, seed=seed)
    internal_dir = _resolve_primary_internal_dir(
        primary_internal_root, seed=seed
    )
    summary = verify_primary_internal_test(
        internal_dir,
        selection_dir=selection_dir,
        expected_manifest_sha256=expected_manifest_sha,
    )
    risk_path = internal_dir / "internal_test_risk_summary.csv"
    frame = pd.read_csv(risk_path)
    row = frame.loc[frame["method"] == "CRMT"]
    if len(row) != 1:
        raise RuntimeError(f"seed {seed}: primary internal CRMT row missing")
    record = {
        "seed": int(seed),
        "method": "CRMT",
        **{
            objective: float(row.iloc[0][objective])
            for objective in DEFAULT_OBJECTIVES
        },
    }
    evidence = {
        "primary_selection_lock_sha256": _sha256(
            selection_dir / "selection_lock.json"
        ),
        "primary_internal_summary_sha256": _sha256(
            internal_dir / "internal_test_run_summary.json"
        ),
        "primary_internal_risk_sha256": _sha256(risk_path),
    }
    return record, evidence


def _load_ablation(
    ablation_id: str,
    seed: int,
    *,
    ablation_internal_root: Path,
    expected_manifest_sha: str,
) -> tuple[dict, dict]:
    d = _resolve_ablation_internal_dir(
        ablation_internal_root,
        ablation_id=ablation_id,
        seed=seed,
    )
    summary_path = d / "ablation_internal_run_summary.json"
    risk_path = d / "ablation_internal_risk_summary.csv"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("stage") != "CRMT_ABLATION_ONE_SHOT_INTERNAL_TEST":
        raise RuntimeError(f"{ablation_id}/{seed}: invalid internal stage")
    if summary.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError(f"{ablation_id}/{seed}: protocol mismatch")
    if str(summary.get("ablation_id")) != ablation_id:
        raise RuntimeError(f"{ablation_id}/{seed}: ablation ID mismatch")
    if int(summary.get("seed")) != int(seed):
        raise RuntimeError(f"{ablation_id}/{seed}: seed mismatch")
    if summary.get("data_context", {}).get("manifest_sha256") != expected_manifest_sha:
        raise RuntimeError(f"{ablation_id}/{seed}: manifest mismatch")
    if _sha256(risk_path) != summary.get("files_sha256", {}).get(
        "ablation_internal_risk_summary.csv"
    ):
        raise RuntimeError(f"{ablation_id}/{seed}: risk-summary hash mismatch")
    if not summary.get("ablation_selection_lock_sha256"):
        raise RuntimeError(f"{ablation_id}/{seed}: selection lock hash missing")

    frame = pd.read_csv(risk_path)
    if len(frame) != 1 or frame.iloc[0]["method"] != ablation_id:
        raise RuntimeError(
            f"{ablation_id}/{seed}: expected one held-out risk row"
        )
    record = {
        "seed": int(seed),
        "method": ablation_id,
        **{
            objective: float(frame.iloc[0][objective])
            for objective in DEFAULT_OBJECTIVES
        },
    }
    evidence = {
        "ablation_id": ablation_id,
        "ablation_internal_summary_sha256": _sha256(summary_path),
        "ablation_internal_risk_sha256": _sha256(risk_path),
        "ablation_selection_lock_sha256": summary[
            "ablation_selection_lock_sha256"
        ],
    }
    return record, evidence


def build_ablation_report(
    *,
    primary_selection_root: Path,
    primary_internal_root: Path,
    ablation_internal_root: Path,
    block_lock: dict,
    output_dir: Path,
    seeds: Iterable[int] = OPTIMIZER_SEEDS,
) -> dict:
    seed_list = tuple(int(s) for s in seeds)
    if not seed_list:
        raise ValueError("at least one seed is required")
    expected_manifest_sha = str(block_lock["canonical_csv_sha256"])

    rows = []
    evidence = []
    for seed in seed_list:
        primary_row, primary_ev = _load_primary_crmt(
            seed,
            primary_selection_root=primary_selection_root,
            primary_internal_root=primary_internal_root,
            expected_manifest_sha=expected_manifest_sha,
        )
        rows.append(primary_row)
        seed_ev = {"seed": int(seed), **primary_ev, "ablations": []}
        for ablation_id in ABLATION_IDS:
            row, ev = _load_ablation(
                ablation_id,
                seed,
                ablation_internal_root=ablation_internal_root,
                expected_manifest_sha=expected_manifest_sha,
            )
            rows.append(row)
            seed_ev["ablations"].append(ev)
        evidence.append(seed_ev)

    frame = pd.DataFrame(rows)
    expected_rows = len(seed_list) * len(ABLATION_COMPARISON_METHODS)
    if len(frame) != expected_rows:
        raise RuntimeError("ablation paired seed-method design is incomplete")

    direction = {m: "minimize" for m in DEFAULT_OBJECTIVES}
    desc = descriptive_table(frame, metrics=DEFAULT_OBJECTIVES)
    friedman = friedman_table(
        frame,
        metrics=DEFAULT_OBJECTIVES,
        methods=ABLATION_COMPARISON_METHODS,
    )
    pairwise = pairwise_paired_table(
        frame,
        metrics=DEFAULT_OBJECTIVES,
        methods=ABLATION_COMPARISON_METHODS,
        n_boot=STATISTICAL_BOOTSTRAP_DRAWS,
        bootstrap_seed=STATISTICAL_BOOTSTRAP_SEED + 300_000,
        alpha=STATISTICAL_ALPHA,
        direction=direction,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "ablation_internal_seed_metrics.csv": frame,
        "ablation_internal_descriptive.csv": desc,
        "ablation_internal_friedman.csv": friedman,
        "ablation_internal_pairwise_wilcoxon_holm.csv": pairwise,
    }
    hashes = {}
    for name, table in tables.items():
        path = output_dir / name
        table.to_csv(path, index=False, lineterminator="\n")
        hashes[name] = _sha256(path)

    summary = {
        "stage": "CRMT_ABLATION_HELDOUT_STATISTICAL_REPORT",
        "claim_boundary": (
            "Machine-generated paired held-out statistics for full CRMT and "
            "the three predeclared one-factor-at-a-time ablations."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seed_list),
        "methods": list(ABLATION_COMPARISON_METHODS),
        "objectives": list(DEFAULT_OBJECTIVES),
        "heldout_risk": {
            "q": 0.90,
            "tail_weight": 0.50,
        },
        "statistical_protocol": {
            "alpha": STATISTICAL_ALPHA,
            "paired_bootstrap_draws": STATISTICAL_BOOTSTRAP_DRAWS,
            "paired_bootstrap_seed": STATISTICAL_BOOTSTRAP_SEED + 300_000,
            "pairwise_test": "two-sided Wilcoxon signed-rank",
            "multiplicity": "Holm within each objective family",
            "omnibus": "Friedman repeated-measures",
            "effect_size": "paired rank-biserial",
            "inferential_unit": "optimizer_seed",
        },
        "source_evidence": evidence,
        "files_sha256": hashes,
    }
    (output_dir / "ablation_analysis_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Build held-out paired statistics for full CRMT and ablations"
    )
    p.add_argument("--primary-selection-root", type=Path, required=True)
    p.add_argument("--primary-internal-root", type=Path, required=True)
    p.add_argument("--ablation-internal-root", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    block_lock = json.loads(
        args.block_lock_json.read_text(encoding="utf-8")
    )
    summary = build_ablation_report(
        primary_selection_root=args.primary_selection_root,
        primary_internal_root=args.primary_internal_root,
        ablation_internal_root=args.ablation_internal_root,
        block_lock=block_lock,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
