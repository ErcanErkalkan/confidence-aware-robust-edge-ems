"""Scientific contract regressions; fixtures are synthetic engineering inputs."""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations
import math

import numpy as np
import pytest

from crmt_edge_ems.contracts import ContractError, digest
from crmt_edge_ems.r19_feasibility import design_grid, geometry
from crmt_edge_ems.r19_primary import (
    DECLARED_AUDIT_POLICY, UNDECLARED_AUDIT_POLICY,
    aggregate_seed_differences, audit_fidelity, select_shortlists,
)


def _reseal(selection):
    raw = deepcopy(selection)
    raw.pop("selection_sha256", None)
    raw["selection_sha256"] = digest(raw)
    return raw


@pytest.fixture(scope="module")
def inputs():
    ids = [f"c{i:03d}" for i in range(256)]
    observations = {
        cid: {
            f"d{b:02d}": [float(i)] * 4
            for b in range(50 if i < 56 else 49)
        }
        for i, cid in enumerate(ids)
    }
    ledger = [(c, b) for c, rows in observations.items() for b in rows]
    archives = {"F0": ids[:20], "F1": ids[1:21]}
    declared = [f"a{b:02d}" for b in range(10)]
    selection = select_shortlists(
        ids, observations, ledger, ledger, archives,
        audit_block_ids=declared, require_declared_audit=True,
    )
    audit = {
        cid: {bid: [float(i)] * 4 for bid in declared}
        for i, cid in enumerate(ids)
    }
    return ids, observations, ledger, archives, declared, selection, audit


def test_sharp_threshold_has_no_absolute_tolerance():
    assert not geometry(256, practical_effect_threshold=1e-15).effect_geometrically_possible
    assert geometry(200).effect_geometrically_possible
    above = math.nextafter(0.05, math.inf)
    assert not geometry(200, practical_effect_threshold=above).effect_geometrically_possible
    assert not geometry(201).effect_geometrically_possible


def test_exhaustive_small_pool_hit_bounds_and_attainability():
    # Exhaustive property check over every legal subset, not implementation mirrors.
    for n in range(1, 11):
        for k in range(1, n + 1):
            shortlists = tuple(combinations(range(n), k))
            for p in range(1, n + 1):
                hits = [sum(cid < p for cid in shortlist) for shortlist in shortlists]
                observed_width = max(hits) - min(hits)
                g = geometry(p, pool_size=n, shortlist_size=k)
                assert min(hits) == g.min_true_pareto_hits
                assert max(hits) == g.max_true_pareto_hits
                assert g.sharp_max_abs_delta_miss == float(Fraction(observed_width, p))
                if observed_width == 0:
                    assert not geometry(
                        p, pool_size=n, shortlist_size=k,
                        practical_effect_threshold=1e-15,
                    ).effect_geometrically_possible


def test_seeded_geometry_properties_and_complete_grid():
    rng = np.random.default_rng(20261028)
    for _ in range(250):
        n = int(rng.integers(2, 300))
        k = int(rng.integers(1, n))
        p = int(rng.integers(1, n + 1))
        g = geometry(p, pool_size=n, shortlist_size=k)
        complement = geometry(p, pool_size=n, shortlist_size=n-k)
        assert g.sharp_max_abs_delta_miss == complement.sharp_max_abs_delta_miss
        assert 0 <= g.sharp_max_abs_delta_miss <= 1
        assert geometry(p, pool_size=n, shortlist_size=n).sharp_max_abs_delta_miss == 0
    grid = design_grid(pool_size=17, shortlist_size=3)
    assert [row["pareto_size"] for row in grid] == list(range(1, 18))


@pytest.mark.parametrize("kwargs", [
    {"pareto_size": True},
    {"pareto_size": 2.5},
    {"pareto_size": 0},
    {"pareto_size": 257},
    {"pareto_size": 10, "shortlist_size": False},
    {"pareto_size": 10, "shortlist_size": 257},
    {"pareto_size": 10, "pool_size": 256.0},
    {"pareto_size": 10, "practical_effect_threshold": True},
    {"pareto_size": 10, "practical_effect_threshold": float("inf")},
    {"pareto_size": 10, "practical_effect_threshold": 0},
])
def test_geometry_rejects_invalid_scientific_inputs(kwargs):
    with pytest.raises(ContractError):
        geometry(**kwargs)


@pytest.mark.parametrize("fault", [
    "short", "long", "full_pool", "duplicate", "unknown_candidate",
    "wrong_arms", "outside_natural", "count_below_k", "count_above_pool", "wrong_b",
    "backfill", "locked", "incomplete_pool", "normalization_shape",
    "invalid_input_hash", "contradictory_policy", "boolean_schema",
])
def test_hash_valid_malformed_selection_is_rejected(inputs, fault):
    ids, _, _, _, _, original, audit = inputs
    s = deepcopy(original)
    if fault == "short":
        s["selected"]["F1"] = ids[:9]
    elif fault == "long":
        s["selected"]["F1"] = ids[:11]
    elif fault == "full_pool":
        s["selected"]["F1"] = list(ids)
    elif fault == "duplicate":
        s["selected"]["F1"][1] = s["selected"]["F1"][0]
    elif fault == "unknown_candidate":
        s["selected"]["F1"][0] = "alien"
    elif fault == "wrong_arms":
        s["selected"]["F2"] = s["selected"].pop("F1")
    elif fault == "outside_natural":
        s["selected"]["F1"][0] = "c255"
    elif fault == "count_below_k":
        s["natural_counts"]["F1"] = 9
    elif fault == "count_above_pool":
        s["natural_counts"]["F1"] = 257
    elif fault == "wrong_b":
        s["B"] = 9
    elif fault == "backfill":
        s["backfill"] = True
    elif fault == "locked":
        s["locked"] = True
    elif fault == "incomplete_pool":
        s["candidate_ids"] = ids[:255]
    elif fault == "normalization_shape":
        s["normalization_span"] = [1, 1, 1]
    elif fault == "invalid_input_hash":
        s["discovery_inputs_sha256"] = "not-a-hash"
    elif fault == "contradictory_policy":
        s["audit_support_policy"] = UNDECLARED_AUDIT_POLICY
    elif fault == "boolean_schema":
        s["schema_version"] = True
    with pytest.raises(ContractError):
        audit_fidelity(_reseal(s), audit, require_declared_audit=True)


@pytest.mark.parametrize("fault", ["missing_all", "extra_all", "missing_one", "replacement_all"])
def test_exact_declared_audit_support_rejects_missing_or_extra_runs(inputs, fault):
    _, _, _, _, declared, selection, original = inputs
    audit = deepcopy(original)
    if fault == "missing_all":
        for rows in audit.values():
            rows.pop(declared[-1])
    elif fault == "extra_all":
        for rows in audit.values():
            rows["extra"] = [0.0] * 4
    elif fault == "missing_one":
        audit["c000"].pop(declared[-1])
    elif fault == "replacement_all":
        for rows in audit.values():
            rows["replacement"] = rows.pop(declared[-1])
    with pytest.raises(ContractError, match="support"):
        audit_fidelity(selection, audit, require_declared_audit=True)


def test_declared_audit_positive_path_is_exact_k_and_deterministic(inputs):
    _, _, _, _, declared, selection, audit = inputs
    first = audit_fidelity(selection, audit, require_declared_audit=True)
    second = audit_fidelity(selection, audit, require_declared_audit=True)
    assert first == second
    assert first["audit_events"] == 256 * len(declared)
    assert first["audit_support_policy"] == DECLARED_AUDIT_POLICY
    assert first["reference_ids"] == ["c000"]
    assert first["true_pareto_hits"] == {"F0": 1, "F1": 0}
    assert first["delta_miss"] == 1
    assert first["status"] == "EXPLORATORY_NOT_CONFIRMATORY"


def test_missing_manifest_is_rejected_before_discovery_scores(inputs):
    ids, original, ledger, archives, _, _, _ = inputs
    observations = deepcopy(original)
    observations["c000"]["d00"] = [float("nan")] * 4
    with pytest.raises(ContractError, match="AUDIT manifest required"):
        select_shortlists(
            ids, observations, ledger, ledger, archives, require_declared_audit=True,
        )


def test_version_one_selection_remains_exploratory_and_strict_mode_rejects_it(inputs):
    _, _, _, _, _, original, audit = inputs
    legacy = deepcopy(original)
    legacy["schema_version"] = 1
    legacy.pop("audit_block_ids")
    legacy.pop("audit_support_policy")
    legacy.pop("natural_archive_ids")
    legacy = _reseal(legacy)
    result = audit_fidelity(legacy, audit)
    assert result["audit_support_policy"] == UNDECLARED_AUDIT_POLICY
    with pytest.raises(ContractError, match="AUDIT manifest required"):
        audit_fidelity(legacy, audit, require_declared_audit=True)


@pytest.mark.parametrize("manifest", [
    [], ["same"] * 8, ["a"] * 9, [f"a{i}" for i in range(7)],
    ["d00"] + [f"a{i}" for i in range(8)],
])
def test_invalid_declared_manifest_rejected_before_selection(inputs, manifest):
    ids, observations, ledger, archives, _, _, _ = inputs
    with pytest.raises(ContractError):
        select_shortlists(
            ids, observations, ledger, ledger, archives,
            audit_block_ids=manifest, require_declared_audit=True,
        )


def test_complete_seed_manifest_and_missing_failure_policy():
    planned = tuple(range(2001, 2031))
    rows = [
        {"seed": s, "status": "EXPLORATORY_NOT_CONFIRMATORY", "delta_miss": -0.01}
        for s in reversed(planned)
    ]
    result = aggregate_seed_differences(rows, planned)
    assert result["n_seeds"] == 30
    for bad in (rows[:-1], rows[:-1]+[rows[0]], rows+[rows[0]]):
        with pytest.raises(ContractError, match="missing"):
            aggregate_seed_differences(bad, planned)
    failed = deepcopy(rows)
    failed[0]["status"] = "FAILED"
    with pytest.raises(ContractError, match="incomplete"):
        aggregate_seed_differences(failed, planned)
    malformed = deepcopy(rows)
    malformed[0].pop("seed")
    with pytest.raises(ContractError):
        aggregate_seed_differences(malformed, planned)
