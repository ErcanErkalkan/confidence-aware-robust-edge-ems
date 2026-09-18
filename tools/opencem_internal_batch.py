from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crmt_edge_ems.protocol import PROTOCOL_VERSION
from opencem_confirmatory_batch import _seed_range
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_internal_test import (
    _resolve_selection_dir,
    execute_internal_test_on_blocks,
)
from opencem_qa import load_verified_csvs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_internal_batch(
    paths: list[Path],
    *,
    block_lock: dict,
    selection_root: Path,
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
        out_dir = output_root / f"internal_test_seed{seed}"
        summary = execute_internal_test_on_blocks(
            blocks,
            context=context,
            expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
            selection_dir=selection_dir,
            output_dir=out_dir,
        )
        if int(summary["seed"]) != int(seed):
            raise RuntimeError(
                f"selection/internal-test seed mismatch: {summary['seed']} != {seed}"
            )
        summary_path = out_dir / "internal_test_run_summary.json"
        evidence.append({
            "seed": int(seed),
            "internal_test_run_summary_sha256": _sha256(summary_path),
            "selected_candidates_sha256": summary["selected_candidates_sha256"],
        })

    manifest = {
        "stage": "ONE_SHOT_INTERNAL_TEST_BATCH",
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "data_context": context,
        "internal_test_evidence": evidence,
        "claim_boundary": (
            "Batch wrapper only; each seed evaluates an already hash-frozen "
            "validation selection exactly once on the internal-test split."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"internal_batch_manifest_{seeds[0]}_{seeds[-1]}.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run one-shot internal test for a contiguous frozen seed shard"
    )
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--selection-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_internal_batch(
        paths,
        block_lock=lock,
        selection_root=args.selection_root,
        output_root=args.output_root,
        seed_start=args.seed_start,
        seed_end=args.seed_end,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
