from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crmt_edge_ems.protocol import PROTOCOL_VERSION
from opencem_confirmatory_batch import _seed_range
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_internal_test import _resolve_selection_dir
from opencem_qa import load_verified_csvs
from opencem_sensitivity_suite import (
    _resolve_primary_internal_dir,
    execute_sensitivity_suite_on_blocks,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_sensitivity_batch(
    paths: list[Path],
    *,
    block_lock: dict,
    selection_root: Path,
    primary_internal_root: Path,
    output_root: Path,
    seed_start: int,
    seed_end: int,
) -> dict:
    seeds = _seed_range(seed_start, seed_end)
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="internal_test"
    )
    evidence = []
    for seed in seeds:
        selection_dir = _resolve_selection_dir(
            selection_root, seed=seed
        )
        primary_dir = _resolve_primary_internal_dir(
            primary_internal_root, seed=seed
        )
        out_dir = output_root / f"sensitivity_seed{seed}"
        summary = execute_sensitivity_suite_on_blocks(
            blocks,
            context=context,
            expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
            selection_dir=selection_dir,
            primary_internal_dir=primary_dir,
            output_dir=out_dir,
        )
        if int(summary["seed"]) != int(seed):
            raise RuntimeError(
                f"sensitivity seed mismatch: {summary['seed']} != {seed}"
            )
        evidence.append({
            "seed": int(seed),
            "sensitivity_run_summary_sha256": _sha256(
                out_dir / "sensitivity_run_summary.json"
            ),
            "selected_candidates_sha256": summary[
                "selected_candidates_sha256"
            ],
        })

    manifest = {
        "stage": "PREDECLARED_SITE_TEMPORAL_SENSITIVITY_BATCH",
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "data_context": context,
        "sensitivity_evidence": evidence,
        "claim_boundary": (
            "Batch wrapper only; all six predeclared variants are evaluated "
            "after selection and primary internal-test evidence are frozen."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"sensitivity_batch_manifest_{seeds[0]}_{seeds[-1]}.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run all predeclared sensitivities for a contiguous seed shard"
    )
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--selection-root", type=Path, required=True)
    p.add_argument("--primary-internal-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_sensitivity_batch(
        paths,
        block_lock=lock,
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
