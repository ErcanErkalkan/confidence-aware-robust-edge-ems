from dataclasses import replace

import numpy as np
import pytest

from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.metrics_v3 import CapacityPolicy, capacity_accounting, compute_metrics_v3, METRICS_VERSION
from crmt_edge_ems.metrics_v2 import compute_metrics_v2
from test_future_metrics_v2 import simulation


def test_numeric_only_import_and_export_are_not_real_exceedances():
    cap = np.ones(5)
    grid = np.array([1.0, np.nextafter(1.0, 2.0), -np.nextafter(1.0, 2.0), 1.01, -1.01])
    result = capacity_accounting(grid, cap, cap)
    assert result["legacy_violation"].tolist() == [False, True, True, True, True]
    assert result["violation"].tolist() == [False, False, False, True, True]


def test_exact_tolerance_boundary_and_zero_caps():
    # Dyadic tolerance makes the exact boundary independently representable.
    policy = CapacityPolicy(atol_kw=2 ** -20)
    edge = policy.tolerance_kw
    grid = np.array([0.0, edge, -edge, np.nextafter(edge, np.inf), -np.nextafter(edge, np.inf)])
    assert capacity_accounting(grid, np.zeros(5), np.zeros(5), policy=policy)["violation"].tolist() == [False, False, False, True, True]


def test_explicit_scale_and_resolution_are_separate():
    p = CapacityPolicy(atol_kw=0, rtol=1e-6, reference_scale_kw=100, measurement_resolution_kw=.1)
    x = capacity_accounting([1.001], [1.0], [1.0], policy=p)
    assert x["tolerance_kw"] == pytest.approx(.0001)
    assert x["violation"].item()  # Resolution does not erase a breach.
    assert x["measurement_boundary_unresolved"].item()
    assert p.identity != replace(p, measurement_resolution_kw=None).identity


@pytest.mark.parametrize("kwargs", [{"atol_kw": -1}, {"rtol": float("nan")}, {"reference_scale_kw": 0},
                                   {"measurement_resolution_kw": 0}, {"atol_kw": True}])
def test_invalid_policy_rejected(kwargs):
    with pytest.raises(ContractError):
        CapacityPolicy(**kwargs)


@pytest.mark.parametrize("grid,imp,exp", [([0], [-1], [1]), ([0], [1], [-1]), ([float("nan")], [1], [1]),
                                         ([0, 0], [1], [1]), ([0], [True], [1]), ([], [], [])])
def test_capacity_data_fail_closed(grid, imp, exp):
    with pytest.raises(ContractError):
        capacity_accounting(grid, imp, exp)


def test_versioned_metric_preserves_v2_rainflow_and_historical_inputs():
    series, site = simulation()
    before = series.copy(deep=True)
    v2 = compute_metrics_v2(series, site)
    v3 = compute_metrics_v3(series, site)
    assert v3["metrics_version"] == METRICS_VERSION
    assert v3["lfp_cycle_loss_pct"] == v2["lfp_cycle_loss_pct"]
    assert v3["efcrf"] == v2["efcrf"]
    assert not v3["measurement_resolution_known"]
    assert series.equals(before)
