"""Bounded-IID theorem contracts and synthetic-driver regressions."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from crmt_edge_ems.contracts import ContractError, file_hash
from crmt_edge_ems.calibration.conservative_v2 import (
    FIXED_CANDIDATES, IID_ASSUMPTION, KNOWN_SUPPORT,
    calibrate_conservative, empirical_fractional_cvar, known_truth_metrics,
)


def calibrate(panel, **kwargs):
    x = np.asarray(panel)
    defaults = {
        "day_ids": [f"d{j}" for j in range(x.shape[0])],
        "candidate_ids": [f"c{j}" for j in range(x.shape[1])],
        "support_lower": 0.0, "support_upper": 1.0,
        "assumption": IID_ASSUMPTION,
        "candidate_policy": FIXED_CANDIDATES, "support_origin": KNOWN_SUPPORT,
    }
    defaults.update(kwargs)
    return calibrate_conservative(panel, **defaults)


def test_known_constant_support_proves_only_true_dominance():
    values = np.asarray([0.1, 0.4, 0.7])[:, None, None]
    panel = np.broadcast_to(values[None], (20, 3, 1, 4)).copy()
    support = np.broadcast_to(values, (3, 1, 4))
    result = calibrate(
        panel, support_lower=support, support_upper=support, capacity=1,
    )
    truth = 1.5*support[:, 0]
    metrics = known_truth_metrics(result, truth)
    assert result.retained.tolist() == [True, False, False]
    assert not metrics["family_risk_undercoverage"]
    assert not metrics["family_difference_undercoverage"]
    assert not metrics["false_dominance_declaration"]
    assert not metrics["false_pareto_removal"]
    assert metrics["true_pareto_retention"] == 1
    assert result.assumptions_independently_verified is False


def test_effective_sample_size_is_days_not_pooled_inverters():
    rng = np.random.default_rng(20261028)
    panel = rng.random((40, 3, 1, 4))
    one = calibrate(panel)
    seven = calibrate(np.repeat(panel, 7, axis=2))
    assert seven.support_days == one.support_days == 40
    assert seven.observations_per_candidate == 7*one.observations_per_candidate
    assert seven.marginal_family_size == 7*one.marginal_family_size
    assert seven.dkw_epsilon >= one.dkw_epsilon
    expected = min(1, np.sqrt(np.log(2*(3*7*4)/0.05)/(2*40)))
    assert seven.dkw_epsilon == pytest.approx(expected)


def test_within_day_candidate_objective_dependence_is_supported():
    rng = np.random.default_rng(20261028)
    panel = np.broadcast_to(rng.random((50, 1, 1, 1)), (50, 4, 3, 4))
    result = calibrate(panel)
    assert result.support_days == 50
    assert result.point_risk.shape == (4, 4)
    assert not result.declarations.any()


@pytest.mark.parametrize("assumption", [
    "AR1", "DEPENDENT_DAY_VECTORS", "NONSTATIONARY_DAY_VECTORS",
    "EXCHANGEABLE_ONLY", True, [], np.asarray(["IID_DAY_VECTORS"]),
])
def test_unsupported_dependence_or_assumption_flags_are_rejected(assumption):
    with pytest.raises(ContractError, match="sampling assumption"):
        calibrate(np.zeros((8, 2, 1, 4)), assumption=assumption)


def test_adaptive_candidates_and_empirical_support_are_rejected():
    panel = np.zeros((8, 2, 1, 4))
    with pytest.raises(ContractError, match="fixed before"):
        calibrate(panel, candidate_policy="ADAPTIVE_ON_CALIBRATION")
    with pytest.raises(ContractError, match="predeclared"):
        calibrate(panel, support_origin="EMPIRICAL_MINMAX")


@pytest.mark.parametrize("fault", [
    "nan", "inf", "outside", "duplicate_day", "missing_day",
    "duplicate_candidate", "bad_shape", "inverted_support",
])
def test_invalid_panel_is_never_filtered_or_clipped(fault):
    panel = np.full((8, 2, 1, 4), 0.5)
    kwargs = {}
    if fault == "nan":
        panel[0, 0, 0, 0] = np.nan
    elif fault == "inf":
        panel[0, 0, 0, 0] = np.inf
    elif fault == "outside":
        panel[0, 0, 0, 0] = 1.01
    elif fault == "duplicate_day":
        kwargs["day_ids"] = ["same"]*8
    elif fault == "missing_day":
        kwargs["day_ids"] = [f"d{i}" for i in range(7)]
    elif fault == "duplicate_candidate":
        kwargs["candidate_ids"] = ["same", "same"]
    elif fault == "bad_shape":
        panel = panel[..., :3]
    elif fault == "inverted_support":
        kwargs.update(support_lower=1.0, support_upper=0.0)
    with pytest.raises(ContractError):
        calibrate(panel, **kwargs)


def test_fractional_cvar_and_ceil_rounding_correction_are_distinct():
    values = np.asarray([0.0, 0.0, 1.0])
    assert empirical_fractional_cvar(values, q=0.5) == pytest.approx(2/3)
    panel = np.broadcast_to(values[:, None, None, None], (3, 2, 1, 4))
    result = calibrate(panel, q=0.5, tail_weight=0.5)
    assert result.ceil_tail_size == 2
    assert result.point_risk[0, 0] == pytest.approx(1/3 + 0.5*0.5)
    assert result.ceil_rounding_correction[0, 0] == pytest.approx(1/12)
    assert np.all(
        result.ceil_rounding_correction <= result.ceil_rounding_simple_upper_bound
    )


def test_exact_decimal_tail_count_and_integer_mass_need_no_rounding_correction():
    values = np.arange(10)/10
    panel = np.broadcast_to(values[:, None, None, None], (10, 2, 1, 4))
    result = calibrate(panel, q=0.7)
    assert result.ceil_tail_size == 3
    assert not result.ceil_rounding_correction.any()
    assert result.point_risk[0, 0] == pytest.approx(
        values.mean() + 0.5*values[-3:].mean()
    )


def test_rounding_error_bound_over_small_tail_geometries():
    for n in range(2, 22):
        values = np.linspace(0, 1, n)
        panel = np.broadcast_to(values[:, None, None, None], (n, 2, 1, 4))
        for q in (0, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99):
            result = calibrate(panel, q=q, tail_weight=1)
            k = result.ceil_tail_size
            exact = empirical_fractional_cvar(values, q=q)
            ceil = float(values[-k:].mean())
            gap = exact-ceil
            assert gap >= -1e-14
            assert gap <= result.ceil_rounding_correction[0, 0]+1e-14
            assert (
                result.ceil_rounding_correction[0, 0]
                <= result.ceil_rounding_simple_upper_bound[0, 0]+1e-14
            )


def test_overflow_keeps_all_true_front_and_is_not_a_capacity_solution():
    t = np.linspace(0.1, 0.9, 12)
    values = np.stack((t, 1-t, t, 1-t), axis=1)[:, None, :]
    panel = np.broadcast_to(values[None], (20, 12, 1, 4))
    result = calibrate(
        panel, support_lower=values, support_upper=values, capacity=10,
    )
    metrics = known_truth_metrics(result, 1.5*values[:, 0])
    assert result.retained.all()
    assert result.archive_overflow
    assert metrics["true_pareto_size"] == 12
    assert metrics["true_pareto_retention"] == 1
    assert metrics["selection_fidelity"] is None


def _load_driver():
    path = Path(__file__).resolve().parents[1]/"experiments/calibration/run_conservative_v2.py"
    spec = importlib.util.spec_from_file_location("cal_v2_driver_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_driver_writes_plan_before_samples_and_preserves_rejections(tmp_path, monkeypatch):
    driver = _load_driver()
    out = tmp_path/"cal-v2"
    original = driver._panel
    calls = []

    def checked_panel(*args, **kwargs):
        assert (out/"PREDECLARED_CONFIG.json").is_file()
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(driver, "_panel", checked_panel)
    result = driver.run(out, repetitions=2)
    assert len(calls) == 12
    assert result["records"] == 24
    assert result["CALIBRATION_SCIENTIFICALLY_VALIDATED"] is False
    assert result["real_data_validation"] is False
    assert sum(g["unsupported_rejections"] for g in result["groups"]) == 4
    manifest = json.loads((out/"ARTIFACT_MANIFEST_SHA256.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest.items():
        assert file_hash(out/name) == expected_hash
    with pytest.raises(FileExistsError):
        driver.run(out, repetitions=2)
