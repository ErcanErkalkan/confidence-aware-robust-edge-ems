from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from crmt_edge_ems.protocol import (
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
    CRMT_CANDIDATE_POOL_SIZE,
    METHOD_IDS,
    OPTIMIZER_SEEDS,
    PROTOCOL_VERSION,
    TRAIN_BLOCK_COUNT,
)
from opencem_validation_select import _resolve_train_run_dir


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def audit_train_evidence(
    train_run_root: Path,
    *,
    expected_manifest_sha256: str,
) -> tuple[pd.DataFrame, dict]:
    rows = []
    for method in METHOD_IDS:
        for seed in OPTIMIZER_SEEDS:
            run_dir = _resolve_train_run_dir(
                train_run_root,
                method=method,
                seed=seed,
            )
            summary_path = run_dir / "run_summary.json"
            front_path = run_dir / "optimizer_front.csv"
            ledger_path = run_dir / "ledger.csv"
            if not all(p.is_file() for p in (summary_path, front_path, ledger_path)):
                raise FileNotFoundError(f"{method}/{seed}: incomplete TRAIN evidence")

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary.get("stage") != "TRAIN_OPTIMIZATION_ONLY":
                raise RuntimeError(f"{method}/{seed}: invalid TRAIN stage")
            if summary.get("protocol_version") != PROTOCOL_VERSION:
                raise RuntimeError(f"{method}/{seed}: protocol mismatch")
            if str(summary.get("method")) != method:
                raise RuntimeError(f"{method}/{seed}: method mismatch")
            if int(summary.get("seed")) != int(seed):
                raise RuntimeError(f"{method}/{seed}: seed mismatch")
            if int(summary.get("controller_block_budget")) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
                raise RuntimeError(f"{method}/{seed}: budget mismatch")
            if int(summary.get("ledger_used")) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
                raise RuntimeError(f"{method}/{seed}: non-exact ledger use")
            context = summary.get("data_context", {})
            if context.get("manifest_sha256") != expected_manifest_sha256:
                raise RuntimeError(f"{method}/{seed}: block-manifest mismatch")
            if int(context.get("train_block_count")) != TRAIN_BLOCK_COUNT:
                raise RuntimeError(f"{method}/{seed}: TRAIN block-count mismatch")

            files = summary.get("files_sha256", {})
            if _sha256(front_path) != files.get("optimizer_front.csv"):
                raise RuntimeError(f"{method}/{seed}: optimizer-front hash mismatch")
            if _sha256(ledger_path) != files.get("ledger.csv"):
                raise RuntimeError(f"{method}/{seed}: ledger hash mismatch")

            candidate_name = (
                "candidate_metrics.csv" if method == "CRMT"
                else "candidate_evaluations.csv"
            )
            candidate_path = run_dir / candidate_name
            if not candidate_path.is_file():
                raise FileNotFoundError(
                    f"{method}/{seed}: missing {candidate_name}"
                )
            if _sha256(candidate_path) != files.get(candidate_name):
                raise RuntimeError(
                    f"{method}/{seed}: candidate-evidence hash mismatch"
                )

            ledger = pd.read_csv(ledger_path)
            if len(ledger) != CONFIRMATORY_CONTROLLER_BLOCK_BUDGET:
                raise RuntimeError(f"{method}/{seed}: ledger row-count mismatch")
            expected_ord = np.arange(
                1, CONFIRMATORY_CONTROLLER_BLOCK_BUDGET + 1
            )
            observed_ord = pd.to_numeric(
                ledger["ordinal"], errors="coerce"
            ).to_numpy()
            if not np.array_equal(observed_ord, expected_ord):
                raise RuntimeError(f"{method}/{seed}: ledger ordinal drift")
            if set(ledger["method_id"].astype(str)) != {method}:
                raise RuntimeError(f"{method}/{seed}: ledger method drift")
            if set(ledger["unit"].astype(str)) != {
                "controller_block_evaluation"
            }:
                raise RuntimeError(f"{method}/{seed}: ledger unit drift")
            if ledger["block_id"].isna().any():
                raise RuntimeError(f"{method}/{seed}: null ledger block IDs")

            expected_candidates = (
                CRMT_CANDIDATE_POOL_SIZE if method == "CRMT" else 60
            )
            if int(summary.get("candidate_count")) != expected_candidates:
                raise RuntimeError(
                    f"{method}/{seed}: candidate-count mismatch"
                )

            rows.append(
                {
                    "method": method,
                    "seed": int(seed),
                    "run_dir": run_dir.name,
                    "run_summary_sha256": _sha256(summary_path),
                    "optimizer_front_sha256": _sha256(front_path),
                    "ledger_sha256": _sha256(ledger_path),
                    "candidate_evidence_file": candidate_name,
                    "candidate_evidence_sha256": _sha256(candidate_path),
                    "ledger_rows": int(len(ledger)),
                    "candidate_count": int(summary["candidate_count"]),
                    "source_git_sha_recorded": summary.get("git_sha"),
                }
            )

    frame = pd.DataFrame(rows)
    order = {m: i for i, m in enumerate(METHOD_IDS)}
    frame["_method_order"] = frame["method"].map(order)
    frame = (
        frame.sort_values(["_method_order", "seed"])
        .drop(columns="_method_order")
        .reset_index(drop=True)
    )
    expected_rows = len(METHOD_IDS) * len(OPTIMIZER_SEEDS)
    if len(frame) != expected_rows:
        raise RuntimeError(
            f"TRAIN evidence design incomplete: {len(frame)} != {expected_rows}"
        )
    if frame[["method", "seed"]].duplicated().any():
        raise RuntimeError("duplicate method/seed TRAIN evidence")

    digest = hashlib.sha256(_canonical_csv_bytes(frame)).hexdigest()
    report = {
        "stage": "CONFIRMATORY_TRAIN_EVIDENCE_AUDIT",
        "claim_boundary": (
            "Evidence-integrity audit only. No validation/internal-test/OOD "
            "metric or scientific comparison is computed."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "methods": list(METHOD_IDS),
        "seeds": list(OPTIMIZER_SEEDS),
        "expected_runs": expected_rows,
        "verified_runs": int(len(frame)),
        "controller_block_budget_per_run": CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
        "expected_manifest_sha256": expected_manifest_sha256,
        "evidence_index_sha256": digest,
    }
    return frame, report


def main() -> int:
    p = argparse.ArgumentParser(
        description="Fail-closed audit of all frozen TRAIN method/seed evidence"
    )
    p.add_argument("--train-run-root", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    block_lock = json.loads(
        args.block_lock_json.read_text(encoding="utf-8")
    )
    frame, report = audit_train_evidence(
        args.train_run_root,
        expected_manifest_sha256=str(
            block_lock["canonical_csv_sha256"]
        ),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "train_evidence_index.csv"
    csv_path.write_bytes(_canonical_csv_bytes(frame))
    if _sha256(csv_path) != report["evidence_index_sha256"]:
        raise RuntimeError("canonical TRAIN evidence index hash drift")
    (args.output_dir / "train_evidence_audit.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
