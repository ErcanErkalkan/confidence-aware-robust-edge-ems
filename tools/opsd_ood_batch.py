from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from opencem_confirmatory_batch import _seed_range
from opencem_internal_test import _resolve_selection_dir
from opencem_sensitivity_suite import _resolve_primary_internal_dir
from opsd_ood_evaluate import (
    build_locked_ood_blocks,
    execute_ood_on_blocks,
    load_locked_opsd_frame,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_ood_batch(
    zip_path: Path,
    *,
    artifact_lock: dict,
    base_inventory_lock: dict,
    full_replay_lock: dict,
    opencem_block_lock: dict,
    selection_root: Path,
    primary_internal_root: Path,
    output_root: Path,
    seed_start: int,
    seed_end: int,
) -> dict:
    seeds = _seed_range(seed_start, seed_end)
    frame, observed = load_locked_opsd_frame(
        zip_path, artifact_lock=artifact_lock
    )
    if observed["sha256"] != str(full_replay_lock["package_sha256"]):
        raise RuntimeError("OPSD package hash disagrees with replay lock")

    blocks, meta, context = build_locked_ood_blocks(
        frame,
        base_inventory_lock=base_inventory_lock,
        full_replay_lock=full_replay_lock,
    )
    expected_open = str(
        opencem_block_lock["canonical_csv_sha256"]
    )

    evidence = []
    for seed in seeds:
        selection_dir = _resolve_selection_dir(
            selection_root, seed=seed
        )
        internal_dir = _resolve_primary_internal_dir(
            primary_internal_root, seed=seed
        )
        out_dir = output_root / f"opsd_ood_seed{seed}"
        summary = execute_ood_on_blocks(
            blocks,
            meta,
            context=context,
            selection_dir=selection_dir,
            primary_internal_dir=internal_dir,
            expected_opencem_manifest_sha=expected_open,
            output_dir=out_dir,
        )
        if int(summary["seed"]) != int(seed):
            raise RuntimeError("OOD seed/evidence mismatch")
        evidence.append(
            {
                "seed": int(seed),
                "ood_run_summary_sha256": _sha256(
                    out_dir / "ood_run_summary.json"
                ),
                "selected_candidates_sha256": summary[
                    "selected_candidates_sha256"
                ],
            }
        )

    manifest = {
        "stage": "EXTERNAL_OOD_OPSD_BATCH",
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "source_context": context,
        "run_evidence": evidence,
        "claim_boundary": (
            "Batch wrapper only; frozen selections, OPSD inventories and "
            "OpenCEM site models are unchanged."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / (
        f"opsd_ood_batch_manifest_{seeds[0]}_{seeds[-1]}.json"
    )
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run OPSD external OOD for a contiguous frozen seed shard"
    )
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--zip", dest="zip_path", type=Path, required=True)
    p.add_argument("--artifact-lock-json", type=Path, required=True)
    p.add_argument("--base-inventory-lock-json", type=Path, required=True)
    p.add_argument("--full-replay-lock-json", type=Path, required=True)
    p.add_argument("--opencem-block-lock-json", type=Path, required=True)
    p.add_argument("--selection-root", type=Path, required=True)
    p.add_argument("--primary-internal-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    locks = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in (
            args.artifact_lock_json,
            args.base_inventory_lock_json,
            args.full_replay_lock_json,
            args.opencem_block_lock_json,
        )
    ]
    result = execute_ood_batch(
        args.zip_path,
        artifact_lock=locks[0],
        base_inventory_lock=locks[1],
        full_replay_lock=locks[2],
        opencem_block_lock=locks[3],
        selection_root=args.selection_root,
        primary_internal_root=args.primary_internal_root,
        output_root=args.output_root,
        seed_start=args.seed_start,
        seed_end=args.seed_end,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
