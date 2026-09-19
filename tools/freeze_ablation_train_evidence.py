from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from tools.evidence_roots import (
    ABLATION_CONTROLLER_BLOCK_BUDGET,
    ABLATION_IDS,
    ABLATION_REQUIRED_HASHED_FILES,
    ABLATION_TRAIN_BLOCK_COUNT,
    ABLATION_TRAIN_GIT_SHA,
    ABLATION_TRAIN_MANIFEST_SHA256,
    SEEDS,
    _load_json,
    _resolve_unique_dir,
    _sha256,
    compute_evidence_root,
)


INDEX_NAME = "ABLATION_TRAIN_MASTER_INDEX_v1.csv"
LOCK_NAME = "ABLATION_TRAIN_MASTER_LOCK_v1.json"
SHA_NAME = "ABLATION_TRAIN_MASTER_LOCK_v1.sha256"


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "ablation_id",
        "seed",
        "run_summary_sha256",
        "candidate_metrics_sha256",
        "optimizer_front_sha256",
        "ledger_sha256",
        "archive_size",
        "ledger_used",
        "git_sha",
        "manifest_sha256",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def freeze_ablation_train(root: Path, output_dir: Path, source_run_id: int) -> dict:
    root = Path(root)
    output_dir = Path(output_dir)

    audit = compute_evidence_root("ablation_train", root)
    if int(audit["records"]) != len(ABLATION_IDS) * len(SEEDS):
        raise RuntimeError(f"expected 90 ablation TRAIN records, got {audit['records']}")

    rows: list[dict] = []
    for ablation in ABLATION_IDS:
        for seed in SEEDS:
            directory = _resolve_unique_dir(
                root,
                f"{ablation}_seed{seed}",
                ("run_summary.json", "optimizer_front.csv"),
            )
            summary_path = directory / "run_summary.json"
            summary = _load_json(summary_path)
            files = summary["files_sha256"]
            rows.append(
                {
                    "ablation_id": ablation,
                    "seed": seed,
                    "run_summary_sha256": _sha256(summary_path),
                    "candidate_metrics_sha256": files["candidate_metrics.csv"],
                    "optimizer_front_sha256": files["optimizer_front.csv"],
                    "ledger_sha256": files["ledger.csv"],
                    "archive_size": int(summary["archive_size"]),
                    "ledger_used": int(summary["ledger_used"]),
                    "git_sha": str(summary["git_sha"]),
                    "manifest_sha256": str(summary["data_context"]["manifest_sha256"]),
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / INDEX_NAME
    _write_csv(index_path, rows)
    index_sha = _sha256(index_path)

    lock = {
        "stage": "CRMT_ABLATION_TRAIN_MASTER_LOCK",
        "version": 1,
        "source_run_id": int(source_run_id),
        "ablation_train_root_sha256": audit["root_sha256"],
        "records": int(audit["records"]),
        "ablations": list(ABLATION_IDS),
        "seed_start": min(SEEDS),
        "seed_end": max(SEEDS),
        "seed_count": len(SEEDS),
        "controller_block_budget": ABLATION_CONTROLLER_BLOCK_BUDGET,
        "launch_git_sha": ABLATION_TRAIN_GIT_SHA,
        "opencem_manifest_sha256": ABLATION_TRAIN_MANIFEST_SHA256,
        "train_block_count": ABLATION_TRAIN_BLOCK_COUNT,
        "required_hashed_files": list(ABLATION_REQUIRED_HASHED_FILES),
        "index_file": INDEX_NAME,
        "index_sha256": index_sha,
        "claim_boundary": (
            "Cryptographic TRAIN-ablation evidence freeze only; "
            "no held-out component-contribution conclusion."
        ),
    }
    lock_path = output_dir / LOCK_NAME
    lock_path.write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lock_sha = _sha256(lock_path)
    (output_dir / SHA_NAME).write_text(
        f"{lock_sha}  {LOCK_NAME}\n",
        encoding="utf-8",
    )
    return {
        **lock,
        "master_lock_sha256": lock_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze audited 90-run CRMT ablation TRAIN evidence"
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True, type=int)
    args = parser.parse_args()
    result = freeze_ablation_train(args.root, args.output_dir, args.source_run_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
