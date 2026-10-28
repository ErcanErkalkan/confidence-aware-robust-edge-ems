"""R19 empirical shortlist fidelity, separately versioned strict implementation.

No AUDIT outcomes are read during selection. An optional sealed AUDIT manifest
supports exact missing-run checks; prospective backends must require it.
This module never grants scientific authorization. Historical locked=false
protocol files and historical implementations remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .contracts import (
    ContractError, digest, finite_array, identifiers, integer, pareto_mask,
    strict_risk,
)
from .r19_feasibility import geometry

PROTOCOL_ID = "CRMT-R19-STRICT-v1-DRAFT"
SELECTION_SCHEMA_VERSION = 2
DECLARED_AUDIT_POLICY = "SEALED_PREDECLARED_EXACT_SUPPORT"
UNDECLARED_AUDIT_POLICY = "UNDECLARED_EXPLORATORY_SUPPORT_ONLY"
_ARMS = {"F0", "F1"}


@dataclass(frozen=True)
class PrimaryDesign:
    c: int = 1
    a: int = 1
    b: int = 10
    k: int = 10
    candidate_count: int = 256
    discovery_events: int = 12600
    backfill: bool = False
    locked: bool = False

    def __post_init__(self):
        names = ("c", "a", "b", "k", "candidate_count", "discovery_events")
        for name in names:
            integer(getattr(self, name), name, 1)
        if (
            tuple(getattr(self, name) for name in names)
            != (1, 1, 10, 10, 256, 12600)
            or self.backfill is not False or self.locked is not False
        ):
            raise ContractError(
                "R19 fixed C1/A1 B=K10 256/12600 no-backfill unlocked draft required"
            )


def _id_array(value, name, *, allow_empty=False):
    if not isinstance(value, (list, tuple)):
        raise ContractError(f"{name}: ID array required")
    return identifiers(value, name, allow_empty=allow_empty)


def _sha256(value, name):
    if (
        not isinstance(value, str) or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ContractError(f"{name}: lowercase SHA-256 required")


def _audit_manifest(value, discovery_blocks, *, required):
    if not isinstance(required, bool):
        raise ContractError("require_declared_audit must be boolean")
    if value is None:
        if required:
            raise ContractError("sealed predeclared AUDIT manifest required")
        return None
    blocks = _id_array(value, "declared AUDIT blocks")
    if len(blocks) < 8:
        raise ContractError("declared AUDIT support requires at least eight blocks")
    if set(blocks) & set(discovery_blocks):
        raise ContractError("AUDIT blocks overlap DISCOVERY")
    return tuple(sorted(blocks))


def paired_ledger(
    ledger0, ledger1, candidate_ids, discovery_blocks, *, expected=12600,
):
    ids = set(identifiers(candidate_ids, "candidates"))
    blocks = set(identifiers(discovery_blocks, "discovery blocks"))
    expected = integer(expected, "expected events", 1)

    def parse(raw):
        if not isinstance(raw, (list, tuple)):
            raise ContractError("ledger must be an event array")
        rows = []
        for row in raw:
            if (
                not isinstance(row, (tuple, list)) or len(row) != 2
                or not isinstance(row[0], str) or not isinstance(row[1], str)
                or row[0] not in ids or row[1] not in blocks
            ):
                raise ContractError("ledger has invalid candidate/block event")
            rows.append(tuple(row))
        if len(rows) != expected or len(set(rows)) != len(rows):
            raise ContractError("ledger count/duplicate violation")
        if {c for c, _ in rows} != ids:
            raise ContractError("ledger does not cover candidate pool")
        return frozenset(rows)

    l0, l1 = parse(ledger0), parse(ledger1)
    if l0 != l1:
        raise ContractError("F0/F1 discovery ledgers differ")
    return l0


def select_shortlists(
    candidate_ids, discovery_observations, ledger0, ledger1, archives, *,
    design=PrimaryDesign(), audit_block_ids=None, require_declared_audit=False,
):
    """Select exact K10 lists using DISCOVERY only.

    Declared AUDIT IDs contain no outcomes. Supplying them seals the exact
    expected support; require_declared_audit=True makes omission an error.
    Undeclared legacy-style calls remain explicitly exploratory only.
    """
    if not isinstance(design, PrimaryDesign):
        raise ContractError("PrimaryDesign required")
    # Recheck the fixed scientific constants, even if a caller bypassed frozen
    # dataclass assignment restrictions.
    PrimaryDesign(**{
        name: getattr(design, name)
        for name in PrimaryDesign.__dataclass_fields__
    })
    ids = identifiers(candidate_ids, "candidates")
    if (
        len(ids) != design.candidate_count
        or not isinstance(discovery_observations, dict)
        or set(discovery_observations) != set(ids)
        or not isinstance(archives, dict) or set(archives) != _ARMS
    ):
        raise ContractError("R19 pool/observation/archive schema mismatch")
    block_union = set()
    for cid in ids:
        rows = discovery_observations[cid]
        if not isinstance(rows, dict):
            raise ContractError("DISCOVERY observations must map block IDs to metrics")
        block_union.update(identifiers(rows, f"DISCOVERY blocks for {cid}"))
    blocks = tuple(sorted(block_union))
    declared_audit = _audit_manifest(
        audit_block_ids, blocks, required=require_declared_audit,
    )
    events = paired_ledger(
        ledger0, ledger1, ids, blocks, expected=design.discovery_events,
    )
    natural_by_arm = {
        arm: set(_id_array(archives[arm], arm + " natural archive", allow_empty=True))
        for arm in ("F0", "F1")
    }
    if any(not members <= set(ids) for members in natural_by_arm.values()):
        raise ContractError("archive contains unknown candidate")
    counts = {arm: len(natural_by_arm[arm]) for arm in ("F0", "F1")}

    scores = []
    for cid in ids:
        rows = discovery_observations[cid]
        if set(rows) != {b for c, b in events if c == cid}:
            raise ContractError("observations differ from executed ledger")
        scores.append(strict_risk([rows[b] for b in sorted(rows)]))
    matrix = np.stack(scores)
    with np.errstate(over="ignore", invalid="ignore"):
        lo = matrix.min(axis=0)
        span = matrix.max(axis=0) - lo
    if not np.isfinite(span).all():
        raise ContractError("normalization overflow")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        norm = np.divide(matrix - lo, span, out=np.zeros_like(matrix), where=span > 0)
    if not np.isfinite(norm).all():
        raise ContractError("normalization overflow")
    order = sorted(
        range(len(ids)),
        key=lambda i: (float(norm[i].max()), float(norm[i].sum()), ids[i]),
    )
    picks = {}
    for arm in ("F0", "F1"):
        if counts[arm] < design.b:
            return {
                "schema_version": SELECTION_SCHEMA_VERSION,
                "protocol_id": PROTOCOL_ID, "status": "BLOCKED_CAPACITY",
                "arm": arm, "natural_count": counts[arm],
                "natural_counts": counts, "required": design.b, "backfill": False,
            }
        picks[arm] = [ids[i] for i in order if ids[i] in natural_by_arm[arm]][:design.b]
    payload = {
        "schema_version": SELECTION_SCHEMA_VERSION, "protocol_id": PROTOCOL_ID,
        "status": "EXPLORATORY_SELECTION_ONLY", "candidate_ids": list(ids),
        "selected": picks, "natural_counts": counts,
        "natural_archive_ids": {arm: sorted(natural_by_arm[arm]) for arm in ("F0", "F1")},
        "B": 10, "backfill": False,
        "discovery_ledger_sha256": digest(sorted(events)),
        "discovery_inputs_sha256": digest(discovery_observations),
        "discovery_block_ids": list(blocks),
        "normalization_min": lo.tolist(), "normalization_span": span.tolist(),
        "locked": False,
        "audit_block_ids": list(declared_audit) if declared_audit is not None else None,
        "audit_support_policy": (
            DECLARED_AUDIT_POLICY if declared_audit is not None else UNDECLARED_AUDIT_POLICY
        ),
    }
    payload["selection_sha256"] = digest(payload)
    return payload


def _validate_selection(selection, *, require_declared_audit):
    if not isinstance(selection, dict):
        raise ContractError("invalid selection lock")
    raw = dict(selection)
    seal = raw.pop("selection_sha256", None)
    try:
        valid_digest = seal == digest(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractError("invalid selection lock") from exc
    if not valid_digest:
        raise ContractError("invalid selection lock")
    _sha256(seal, "selection lock")
    base_fields = {
        "schema_version", "protocol_id", "status", "candidate_ids", "selected",
        "natural_counts", "B", "backfill", "discovery_ledger_sha256",
        "discovery_inputs_sha256", "discovery_block_ids", "normalization_min",
        "normalization_span", "locked",
    }
    version = integer(raw.get("schema_version"), "selection schema_version", 1)
    if version == 1:
        expected_fields = base_fields
    elif version == SELECTION_SCHEMA_VERSION:
        expected_fields = base_fields | {
            "audit_block_ids", "audit_support_policy", "natural_archive_ids",
        }
    else:
        raise ContractError("unsupported selection schema version")
    if set(raw) != expected_fields:
        raise ContractError("selection schema mismatch")
    if (
        raw["status"] != "EXPLORATORY_SELECTION_ONLY"
        or raw["protocol_id"] != PROTOCOL_ID
        or raw["backfill"] is not False or raw["locked"] is not False
        or integer(raw["B"], "selection B", 1) != 10
    ):
        raise ContractError("selection must preserve unlocked B=K10 no-backfill contract")
    ids = _id_array(raw["candidate_ids"], "selection candidates")
    if len(ids) != 256:
        raise ContractError("selection must contain all 256 candidates")
    discovery = _id_array(raw["discovery_block_ids"], "selection DISCOVERY blocks")
    _sha256(raw["discovery_ledger_sha256"], "DISCOVERY ledger")
    _sha256(raw["discovery_inputs_sha256"], "DISCOVERY inputs")
    lo = finite_array(raw["normalization_min"], "normalization min", ndim=1)
    span = finite_array(raw["normalization_span"], "normalization span", ndim=1)
    if lo.shape != (4,) or span.shape != (4,) or np.any(span < 0):
        raise ContractError("four finite nonnegative normalization spans required")
    if not isinstance(raw["selected"], dict) or set(raw["selected"]) != _ARMS:
        raise ContractError("selection requires exactly F0/F1 shortlists")
    if not isinstance(raw["natural_counts"], dict) or set(raw["natural_counts"]) != _ARMS:
        raise ContractError("selection requires exactly F0/F1 natural counts")
    if version == SELECTION_SCHEMA_VERSION and (
        not isinstance(raw["natural_archive_ids"], dict)
        or set(raw["natural_archive_ids"]) != _ARMS
    ):
        raise ContractError("selection requires exactly F0/F1 natural archive memberships")
    for arm in ("F0", "F1"):
        picks = _id_array(raw["selected"][arm], arm + " selected IDs")
        if len(picks) != 10 or not set(picks) <= set(ids):
            raise ContractError("each selected shortlist must contain exactly 10 known distinct candidates")
        count = integer(raw["natural_counts"][arm], arm + " natural count", 10)
        if count > len(ids):
            raise ContractError("natural archive count exceeds candidate pool")
        if version == SELECTION_SCHEMA_VERSION:
            natural = _id_array(raw["natural_archive_ids"][arm], arm + " natural archive IDs")
            if (
                len(natural) != count or not set(natural) <= set(ids)
                or not set(picks) <= set(natural)
            ):
                raise ContractError("shortlist must preserve declared natural archive membership and no backfill")
    declared = _audit_manifest(
        raw.get("audit_block_ids"), discovery, required=require_declared_audit,
    )
    expected_policy = (
        DECLARED_AUDIT_POLICY if declared is not None else UNDECLARED_AUDIT_POLICY
    )
    if version == SELECTION_SCHEMA_VERSION and raw["audit_support_policy"] != expected_policy:
        raise ContractError("selection AUDIT policy contradicts sealed manifest")
    return ids, discovery, declared, seal


def audit_fidelity(selection, audit_observations, *, require_declared_audit=False):
    """Exploratory math only. Real AUDIT execution also requires external gates.

    All selection invariants are checked after digest verification: rehashing a
    malformed K10 selection never makes it valid. A declared AUDIT manifest is
    always exact; the strict backend must also reject undeclared support.
    """
    ids, discovery, declared, seal = _validate_selection(
        selection, require_declared_audit=require_declared_audit,
    )
    if not isinstance(audit_observations, dict) or set(audit_observations) != set(ids):
        raise ContractError("AUDIT must evaluate all candidates")
    if not isinstance(audit_observations[ids[0]], dict):
        raise ContractError("AUDIT observations must map block IDs to metrics")
    observed = identifiers(audit_observations[ids[0]], "AUDIT blocks")
    blocks = declared if declared is not None else tuple(sorted(observed))
    if len(blocks) < 8 or set(blocks) & set(discovery):
        raise ContractError("AUDIT insufficient/overlapping discovery blocks")
    scores = []
    for cid in ids:
        rows = audit_observations[cid]
        if not isinstance(rows, dict) or set(rows) != set(blocks):
            raise ContractError("unequal or missing/extra declared AUDIT support")
        scores.append(strict_risk([rows[b] for b in blocks]))
    reference = {cid for cid, keep in zip(ids, pareto_mask(scores)) if keep}
    if not reference:
        raise ContractError("finite AUDIT Pareto reference cannot be empty")
    hits = {
        arm: len(reference & set(selection["selected"][arm]))
        for arm in ("F0", "F1")
    }
    p = len(reference)
    miss = {arm: (p - hits[arm]) / p for arm in ("F0", "F1")}
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID, "status": "EXPLORATORY_NOT_CONFIRMATORY",
        "selection_sha256": seal, "reference_ids": sorted(reference),
        "reference_nondominated_n": p, "true_pareto_hits": hits,
        "audit_sha256": digest(audit_observations), "miss_rate": miss,
        "delta_miss": (hits["F0"] - hits["F1"]) / p,
        "audit_events": len(ids) * len(blocks), "audit_block_ids": list(blocks),
        "audit_support_policy": (
            DECLARED_AUDIT_POLICY if declared is not None else UNDECLARED_AUDIT_POLICY
        ),
        "sharp_max_abs_delta_miss": geometry(p).sharp_max_abs_delta_miss,
    }


def aggregate_seed_differences(results, planned_seeds):
    seeds = tuple(integer(s, "seed") for s in planned_seeds)
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ContractError("unique planned seeds required")
    if not isinstance(results, (list, tuple)):
        raise ContractError("seed results must be an array")
    actual = []
    for row in results:
        if not isinstance(row, dict):
            raise ContractError("invalid seed result")
        actual.append(integer(row.get("seed"), "result seed"))
    if (
        len(results) != len(seeds) or len(set(actual)) != len(actual)
        or set(actual) != set(seeds)
    ):
        raise ContractError("failed/missing/duplicate seeds cannot be omitted")
    if any(row.get("status") != "EXPLORATORY_NOT_CONFIRMATORY" for row in results):
        raise ContractError("incomplete seed result")
    d = finite_array(
        [row.get("delta_miss") for row in sorted(results, key=lambda row: row["seed"])],
        "seed differences", ndim=1,
    )
    if np.any(np.abs(d) > 1):
        raise ContractError("MissRate differences must be in [-1,1]")
    return {
        "status": "EXPLORATORY_NOT_CONFIRMATORY", "n_seeds": len(seeds),
        "mean_delta_miss": float(d.mean()), "deltas": d.tolist(),
    }
