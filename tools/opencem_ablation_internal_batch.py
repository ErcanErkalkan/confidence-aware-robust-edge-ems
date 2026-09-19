from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crmt_edge_ems.protocol import ABLATION_IDS, PROTOCOL_VERSION
from opencem_ablation_internal_test import (
    _resolve_ablation_selection_dir,
    execute_ablation_internal_on_blocks,
)
from opencem_confirmatory_batch import _seed_range
from opencem_confirmatory_train import build_locked_split_blocks
from opencem_qa import load_verified_csvs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_ablation_internal_batch(
    ablation_id: str,
    paths: list[Path],
    *,
    block_lock: dict,
    ablation_selection_root: Path,
    output_root: Path,
    seed_start: int,
    seed_end: int,
) -> dict:
    ablation_id = str(ablation_id).upper()
    if ablation_id not in ABLATION_IDS:
        raise ValueError(f"ablation_id must be one of {ABLATION_IDS}")
    seeds = _seed_range(seed_start, seed_end)
    blocks, context = build_locked_split_blocks(
        paths, lock=block_lock, split_name="internal_test"
    )

    evidence = []
    for seed in seeds:
        selection_dir = _resolve_ablation_selection_dir(
            ablation_selection_root,
            ablation_id=ablation_id,
            seed=seed,
        )
        out_dir = output_root / f"{ablation_id}_internal_seed{seed}"
        summary = execute_ablation_internal_on_blocks(
            ablation_id,
            seed,
            blocks,
            context=context,
            expected_manifest_sha=str(block_lock["canonical_csv_sha256"]),
            selection_dir=selection_dir,
            output_dir=out_dir,
        )
        evidence.append(
            {
                "seed": int(seed),
                "run_summary_sha256": _sha256(
                    out_dir / "ablation_internal_run_summary.json"
                ),
                "selected_ablation_candidate_sha256": summary[
                    "selected_ablation_candidate_sha256"
                ],
            }
        )

    manifest = {
        "stage": "CRMT_ABLATION_ONE_SHOT_INTERNAL_BATCH",
        "protocol_version": PROTOCOL_VERSION,
        "ablation_id": ablation_id,
        "seeds": list(seeds),
        "n_runs": len(seeds),
        "data_context": context,
        "internal_evidence": evidence,
        "claim_boundary": (
            "Batch wrapper only; every run evaluates one validation-frozen "
            "ablation candidate exactly once on the internal-test split."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / (
        f"ablation_internal_batch_manifest_{ablation_id}_"
        f"{seeds[0]}_{seeds[-1]}.json"
    )
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run one-shot held-out CRMT ablation internal-test shard"
    )
    p.add_argument("--ablation", required=True, choices=list(ABLATION_IDS))
    p.add_argument("--seed-start", required=True, type=int)
    p.add_argument("--seed-end", required=True, type=int)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--verification-csv", type=Path, required=True)
    p.add_argument("--block-lock-json", type=Path, required=True)
    p.add_argument("--ablation-selection-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()

    paths = load_verified_csvs(args.raw_root, args.verification_csv)
    block_lock = json.loads(args.block_lock_json.read_text(encoding="utf-8"))
    result = execute_ablation_internal_batch(
        args.ablation,
        paths,
        block_lock=block_lock,
        ablation_selection_root=args.ablation_selection_root,
        output_root=args.output_root,
        seed_start=args.seed_start,
        seed_end=args.seed_end,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
