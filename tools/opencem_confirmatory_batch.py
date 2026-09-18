from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from crmt_edge_ems.protocol import METHOD_IDS, OPTIMIZER_SEEDS, PROTOCOL_VERSION
from opencem_confirmatory_train import (
    build_locked_train_blocks,
    execute_confirmatory_train_on_blocks,
)
from opencem_qa import load_verified_csvs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_range(start: int, end: int) -> tuple[int, ...]:
    start = int(start)
    end = int(end)
    if start > end:
        raise ValueError("seed_start must be <= seed_end")
    seeds = tuple(s for s in OPTIMIZER_SEEDS if start <= s <= end)
    if not seeds or seeds[0] != start or seeds[-1] != end:
        raise ValueError(
            f"seed range must lie inside {OPTIMIZER_SEEDS[0]}..{OPTIMIZER_SEEDS[-1]}"
        )
    if len(seeds) != end - start + 1:
        raise ValueError("seed range is not contiguous in the frozen registry")
    return seeds


def execute_batch(
    method: str,
    paths: list[Path],
    *,
    block_lock: dict,
    output_root: Path,
    seed_start: int,
    seed_end: int,
) -> dict:
    method = str(method).upper()
    if method not in METHOD_IDS:
        raise ValueError(f"method must be one of {METHOD_IDS}")
    seeds = _seed_range(seed_start, seed_end)

    # Expensive raw-data reconstruction happens once per batch job.
    blocks, context = build_locked_train_blocks(paths, lock=block_lock)

    evidence = []
    for seed in seeds:
        run_dir = output_root / f"{method}_seed{seed}"
        summary = execute_confirmatory_train_on_blocks(
            method,
            seed,
            blocks,
            context=context,
            output_dir=run_dir,
        )
        summary_path = run_dir / "run_summary.json"
        evidence.append(
            {
                "seed": int(seed),
                "run_dir": run_dir.name,
                "run_summary_sha256": _sha256(summary_path),
                "ledger_used": int(summary["ledger_used"]),
                "optimizer_output_size": int(summary["optimizer_output_size"]),
            }
        )

    manifest = {
        "stage": "CONFIRMATORY_TRAIN_BATCH",
        "claim_boundary": (
            "Batch execution wrapper only; every child run remains TRAIN-only "
            "confirmatory optimization evidence."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "method": method,
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "data_context": context,
        "git_sha": os.environ.get("GITHUB_SHA"),
        "run_evidence": evidence,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"batch_manifest_{method}_{seeds[0]}_{seeds[-1]}.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run a contiguous frozen seed batch for one confirmatory method"
    )
    p.add_argument("--method", required=True, choices=list(METHOD_IDS))
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_batch(
        args.method,
        paths,
        block_lock=lock,
        output_root=args.output_root,
        seed_start=args.seed_start,
        seed_end=args.seed_end,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
