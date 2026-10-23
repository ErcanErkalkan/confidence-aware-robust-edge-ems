"""CRMT R9 *draft* deterministic, budget-matched TRAIN archive comparison.

Not a prospective preregistration; deliberately contains no TEST evaluator.
Every input must have an independently verified TRAIN provenance before scientific use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

POLICY_VERSION = "r9-train-equal-capacity-backfill-v0.1-DRAFT"
OBJECTIVE_COUNT = 4


class PolicyBlocked(ValueError):
    """Fail-closed when capacity, budget, provenance label or scores are invalid."""


def _ids(value: Any, *, what: str) -> list[str]:
    if not isinstance(value, list):
        raise PolicyBlocked(f"{what} must be a list")
    if not all(isinstance(x, str) and x.strip() == x for x in value):
        raise PolicyBlocked(f"{what} entries must be nonempty, trimmed strings")
    if not value or not all(value) or len(value) != len(set(value)):
        raise PolicyBlocked(f"{what} has duplicate or empty candidate IDs")
    return value


def _rank_train_scores(raw: Any) -> list[str]:
    if not isinstance(raw, Mapping) or not raw:
        raise PolicyBlocked("train_scores must be a nonempty candidate -> 4 objectives mapping")
    candidate_ids = list(raw)
    if not all(isinstance(x, str) and x for x in candidate_ids):
        raise PolicyBlocked("train_scores candidate IDs must be nonempty strings")
    if any(x != x.strip() for x in candidate_ids):
        raise PolicyBlocked("train_scores candidate IDs must be trimmed")
    values = {}
    for cid, vec in raw.items():
        if not isinstance(vec, (list, tuple)) or len(vec) != OBJECTIVE_COUNT:
            raise PolicyBlocked(f"{cid}: expected exactly four minimization objectives")
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vec):
            raise PolicyBlocked(f"{cid}: nonfinite/nonnumeric objective")
        values[cid] = tuple(float(v) for v in vec)
    lower = [min(v[j] for v in values.values()) for j in range(OBJECTIVE_COUNT)]
    upper = [max(v[j] for v in values.values()) for j in range(OBJECTIVE_COUNT)]

    def score(cid: str) -> tuple[float, float, str]:
        norm = [
            0.0 if upper[j] - lower[j] <= 1e-12 else (values[cid][j] - lower[j]) / (upper[j] - lower[j])
            for j in range(OBJECTIVE_COUNT)
        ]
        # TRAIN-only Chebyshev -> L1 -> lexical stable tie-break.
        return max(norm), sum(norm), cid

    return sorted(values, key=score)


def _signature(raw: Any, *, label: str, expected: int, allowed: set[str]) -> tuple[str, list[tuple[str, str]]]:
    if not isinstance(raw, list) or len(raw) != expected:
        raise PolicyBlocked(f"{label} must contain exactly {expected} controller-block events")
    pairs: list[tuple[str, str]] = []
    for i, event in enumerate(raw):
        if not isinstance(event, dict) or set(event) != {"candidate_id", "block_id"}:
            raise PolicyBlocked(f"{label}[{i}] must have exactly candidate_id, block_id")
        cid, bid = event["candidate_id"], event["block_id"]
        if not isinstance(cid, str) or cid not in allowed or not isinstance(bid, str) or not bid or bid != bid.strip():
            raise PolicyBlocked(f"{label}[{i}] invalid candidate or block identity")
        pairs.append((cid, bid))
    if len(pairs) != len(set(pairs)):
        raise PolicyBlocked(f"{label} has duplicate candidate-block evaluations")
    # Sorting removes irrelevant recorder order; compare actual evaluated pairs.
    canon = sorted(pairs)
    fingerprint = hashlib.sha256(json.dumps(canon, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    return fingerprint, canon


def _select(archive: list[str], ranking: list[str], *, capacity: int, k: int) -> dict[str, Any]:
    retained = set(archive)
    eligible = [cid for cid in ranking if cid in retained]
    effective = eligible[:capacity]
    backfill = [cid for cid in ranking if cid not in retained][:capacity - len(effective)]
    # Backfilled entries are explicitly new shared-policy memory, NOT the native archive.
    bounded = effective + backfill
    if len(bounded) != capacity or len(set(bounded)) != capacity:
        raise PolicyBlocked("could not form exactly capacity unique candidates")
    pos = {cid: index for index, cid in enumerate(ranking)}
    selected = sorted(bounded, key=pos.__getitem__)[:k]
    return {
        "original_archive_size": len(archive),
        "post_prune_native_count": len(effective),
        "pruned_native_count": len(archive) - len(effective),
        "backfill_count": len(backfill),
        "backfill_ids": backfill,
        "bounded_archive_ids": sorted(bounded, key=pos.__getitem__),
        "selected_k_ids": selected,
    }


def build_draft_pair(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reject TEST/VAL inputs; compare two *identical* TRAIN evaluation ledgers.

    Caller is responsible for independent data/commit provenance validation.
    This function NEVER evaluates an EMS and NEVER reads a TEST outcome.
    """
    if not isinstance(payload, Mapping):
        raise PolicyBlocked("input must be a JSON object")
    allowed_fields = {"source_role", "capacity", "k", "expected_evaluations", "train_scores", "f0_archive", "f1_archive", "f0_evaluations", "f1_evaluations"}
    extras = set(payload) - allowed_fields
    if extras:
        raise PolicyBlocked(f"unrecognized input fields rejected, including any TEST data: {sorted(extras)}")
    missing = allowed_fields - set(payload)
    if missing:
        raise PolicyBlocked(f"missing required fields: {sorted(missing)}")
    if payload.get("source_role") != "TRAIN":
        raise PolicyBlocked("source_role must be TRAIN; VAL/TEST and unknown sources are prohibited")
    for key in ("capacity", "k", "expected_evaluations"):
        x = payload.get(key)
        if isinstance(x, bool) or not isinstance(x, int) or x < 1:
            raise PolicyBlocked(f"{key} must be an explicit positive integer")
    capacity, k, expected = (payload[z] for z in ("capacity", "k", "expected_evaluations"))
    if k > capacity:
        raise PolicyBlocked("k exceeds common capacity")
    ranking = _rank_train_scores(payload.get("train_scores"))
    if len(ranking) < capacity:
        raise PolicyBlocked("candidate pool is smaller than common capacity")
    allowed = set(ranking)
    a = _ids(payload.get("f0_archive"), what="f0_archive")
    b = _ids(payload.get("f1_archive"), what="f1_archive")
    if not set(a).issubset(allowed) or not set(b).issubset(allowed):
        raise PolicyBlocked("archive ID is absent from common TRAIN scored pool")
    fp0, sig0 = _signature(payload.get("f0_evaluations"), label="f0_evaluations", expected=expected, allowed=allowed)
    fp1, sig1 = _signature(payload.get("f1_evaluations"), label="f1_evaluations", expected=expected, allowed=allowed)
    if sig0 != sig1:
        raise PolicyBlocked("F0/F1 do not have identical TRAIN candidate-block evaluations")
    result = {
        "status": "OFFLINE_DRAFT_ONLY_NOT_PREREGISTERED_NOT_INDEPENDENT_TEST",
        "policy_version": POLICY_VERSION,
        "source_role": "TRAIN",
        "capacity": capacity,
        "k": k,
        "candidate_pool_size": len(ranking),
        "f0_evaluations": expected,
        "f1_evaluations": expected,
        "common_evaluation_sha256": fp0,
        "input_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest(),
        "train_ranked_ids": ranking,
        "f0": _select(a, ranking, capacity=capacity, k=k),
        "f1": _select(b, ranking, capacity=capacity, k=k),
        "caveat": "Backfill creates new bounded candidate memory; historical native archives and TEST performance are unchanged.",
    }
    result["same_final_k_ids"] = result["f0"]["selected_k_ids"] == result["f1"]["selected_k_ids"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="R9 draft TRAIN-only paired equal-capacity policy (no TEST)")
    parser.add_argument("--input-json", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args()
    if args.input_json.resolve() == args.output_json.resolve():
        parser.error("input and output paths cannot be the same")
    try:
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
        output = build_draft_pair(payload)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"R9_POLICY_BLOCKED: {exc}\n")
    print("R9 TRAIN-only draft policy completed; prospective TEST remains NO-GO")


if __name__ == "__main__":
    main()
