from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crmt_edge_ems.protocol import OPTIMIZER_SEEDS, PROTOCOL_VERSION
from opencem_confirmatory_batch import _seed_range
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_qa import load_verified_csvs
from opencem_validation_select import execute_validation_selection_on_blocks


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_validation_batch(
    paths: list[Path],
    *,
    block_lock: dict,
    train_run_root: Path,
    output_root: Path,
    seed_start: int,
    seed_end: int,
) -> dict:
    seeds = _seed_range(seed_start, seed_end)
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="validation"
    )
    evidence = []
    for seed in seeds:
        out_dir = output_root / f"validation_selection_seed{seed}"
        lock = execute_validation_selection_on_blocks(
            seed,
            blocks,
            context=context,
            expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
            train_run_root=train_run_root,
            output_dir=out_dir,
        )
        lock_path = out_dir / "selection_lock.json"
        evidence.append({
            "seed": int(seed),
            "selection_lock_sha256": _sha256(lock_path),
            "selected_candidates_sha256": lock["selected_candidates_sha256"],
        })

    manifest = {
        "stage": "VALIDATION_SELECTION_BATCH",
        "protocol_version": PROTOCOL_VERSION,
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "data_context": context,
        "source_train_root": str(train_run_root),
        "selection_evidence": evidence,
        "claim_boundary": (
            "Batch wrapper only; selection remains validation-only and "
            "internal-test data are not accessed."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"validation_batch_manifest_{seeds[0]}_{seeds[-1]}.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run frozen validation selection for a contiguous seed shard"
    )
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--train-run-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_validation_batch(
        paths,
        block_lock=lock,
        train_run_root=args.train_run_root,
        output_root=args.output_root,
        seed_start=args.seed_start,
        seed_end=args.seed_end,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
