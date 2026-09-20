from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tools.evidence_roots import (
    OOD_BLOCK_COUNT,
    OOD_EXPECTED_ROWS,
    OOD_PACKAGE_SHA256,
    OOD_REPLAY_MANIFEST_ROWS,
    OOD_REPLAY_MANIFEST_SHA256,
    OOD_TARGET_SITE_IDS,
    SEEDS,
    _load_json,
    _resolve_unique_dir,
    _sha256,
    compute_evidence_root,
)

INDEX_NAME = "OPSD_OOD_MASTER_INDEX_v1.csv"
LOCK_NAME = "OPSD_OOD_MASTER_LOCK_v1.json"
SHA_NAME = "OPSD_OOD_MASTER_LOCK_v1.sha256"


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "seed",
        "run_summary_sha256",
        "selection_lock_sha256",
        "selected_candidates_sha256",
        "primary_internal_test_summary_sha256",
        "ood_block_metrics_sha256",
        "ood_stratum_risk_summary_sha256",
        "ood_macro_risk_summary_sha256",
        "ood_pooled_risk_summary_sha256",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def freeze_ood(root: Path, output_dir: Path, source_run_id: int) -> dict:
    root = Path(root)
    output_dir = Path(output_dir)
    audit = compute_evidence_root("ood", root)
    if int(audit["records"]) != len(SEEDS):
        raise RuntimeError(f"expected 30 OOD records, got {audit['records']}")

    rows: list[dict] = []
    for seed in SEEDS:
        directory = _resolve_unique_dir(
            root,
            f"opsd_ood_seed{seed}",
            ("ood_run_summary.json",),
        )
        summary_path = directory / "ood_run_summary.json"
        summary = _load_json(summary_path)
        files = summary["files_sha256"]
        rows.append(
            {
                "seed": seed,
                "run_summary_sha256": _sha256(summary_path),
                "selection_lock_sha256": summary["selection_lock_sha256"],
                "selected_candidates_sha256": summary["selected_candidates_sha256"],
                "primary_internal_test_summary_sha256": summary[
                    "primary_internal_test_summary_sha256"
                ],
                "ood_block_metrics_sha256": files["ood_block_metrics.csv"],
                "ood_stratum_risk_summary_sha256": files[
                    "ood_stratum_risk_summary.csv"
                ],
                "ood_macro_risk_summary_sha256": files[
                    "ood_macro_risk_summary.csv"
                ],
                "ood_pooled_risk_summary_sha256": files[
                    "ood_pooled_risk_summary.csv"
                ],
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / INDEX_NAME
    _write_csv(index_path, rows)
    index_sha = _sha256(index_path)

    lock = {
        "stage": "OPSD_EXTERNAL_OOD_MASTER_LOCK",
        "version": 1,
        "source_run_id": int(source_run_id),
        "ood_root_sha256": audit["root_sha256"],
        "records": int(audit["records"]),
        "seed_start": min(SEEDS),
        "seed_end": max(SEEDS),
        "seed_count": len(SEEDS),
        "opsd_package_sha256": OOD_PACKAGE_SHA256,
        "opsd_replay_manifest_sha256": OOD_REPLAY_MANIFEST_SHA256,
        "opsd_replay_manifest_rows": OOD_REPLAY_MANIFEST_ROWS,
        "target_site_ids": list(OOD_TARGET_SITE_IDS),
        "ood_block_count": OOD_BLOCK_COUNT,
        "expected_rows_per_seed": OOD_EXPECTED_ROWS,
        "index_file": INDEX_NAME,
        "index_sha256": index_sha,
        "claim_boundary": (
            "Cryptographic external-OOD evidence freeze only; external "
            "generalization claims require the OOD statistical report."
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
    return {**lock, "master_lock_sha256": lock_sha}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze audited 30-seed OPSD OOD evidence"
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True, type=int)
    args = parser.parse_args()
    result = freeze_ood(args.root, args.output_dir, args.source_run_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
