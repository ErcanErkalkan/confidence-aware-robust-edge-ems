from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crmt_edge_ems.protocol import ABLATION_IDS, PROTOCOL_VERSION
from opencem_ablation_validation import execute_ablation_validation_on_blocks
from opencem_confirmatory_batch import _seed_range
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_qa import load_verified_csvs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_ablation_validation_batch(
    ablation_id: str,
    paths: list[Path],
    *,
    block_lock: dict,
    ablation_train_root: Path,
    primary_selection_root: Path,
    output_root: Path,
    seed_start: int,
    seed_end: int,
) -> dict:
    ablation_id = str(ablation_id).upper()
    if ablation_id not in ABLATION_IDS:
        raise ValueError(f"ablation_id must be one of {ABLATION_IDS}")
    seeds = _seed_range(seed_start, seed_end)
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="validation"
    )

    evidence = []
    for seed in seeds:
        out_dir = output_root / f"{ablation_id}_validation_seed{seed}"
        lock = execute_ablation_validation_on_blocks(
            ablation_id,
            seed,
            blocks,
            context=context,
            expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
            ablation_train_root=ablation_train_root,
            primary_selection_root=primary_selection_root,
            output_dir=out_dir,
        )
        evidence.append(
            {
                "seed": int(seed),
                "ablation_selection_lock_sha256": _sha256(
                    out_dir / "ablation_selection_lock.json"
                ),
                "selected_ablation_candidate_sha256": lock[
                    "selected_ablation_candidate_sha256"
                ],
            }
        )

    manifest = {
        "stage": "CRMT_ABLATION_VALIDATION_BATCH",
        "protocol_version": PROTOCOL_VERSION,
        "ablation_id": ablation_id,
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "data_context": context,
        "validation_evidence": evidence,
        "claim_boundary": (
            "Batch wrapper only; every ablation candidate is selected on frozen "
            "validation blocks using the primary validation normalization lock."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / (
        f"ablation_validation_batch_manifest_{ablation_id}_"
        f"{seeds[0]}_{seeds[-1]}.json"
    )
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run held-out validation selection for one ablation seed shard"
    )
    p.add_argument("--ablation", required=True, choices=list(ABLATION_IDS))
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--ablation-train-root", type=Path, required=True)
    p.add_argument("--primary-selection-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    block_lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_ablation_validation_batch(
        args.ablation,
        paths,
        block_lock=block_lock,
        ablation_train_root=args.ablation_train_root,
        primary_selection_root=args.primary_selection_root,
        output_root=args.output_root,
        seed_start=args.seed_start,
        seed_end=args.seed_end,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
