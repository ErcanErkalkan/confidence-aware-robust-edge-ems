"""Geometry and inference assumptions are engineering checks, not new experiments."""
import math

import numpy as np
import pytest

from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.statistical_validation import (
    gaussian_paired_power, geometry_aware_power, paired_inference,
)


ASSUMPTION = "INDEPENDENT_SYMMETRIC_DIFFERENCES"


@pytest.mark.parametrize("scale", [1.0, 1e-16, 1e-100, 1e-250])
def test_exact_signflip_is_invariant_to_nonzero_scale(scale):
    result = paired_inference(
        np.asarray([0.1, 0.2, 0.3]) * scale,
        signflip_assumption=ASSUMPTION,
    )
    assert result["signflip_pvalue"] == 0.25
    reference = paired_inference([0.1, 0.2, 0.3])
    assert result["t_test_pvalue"] == pytest.approx(reference["t_test_pvalue"])
    assert result["signflip_numerical_policy"] == "MAX_ABS_SCALE_FSUM_ONE_ULP_INCLUSIVE_TIES"


def test_monte_carlo_signflip_is_seeded_and_scale_invariant():
    values = np.linspace(0.05, 1.0, 20)
    kwargs = {"signflip_assumption": ASSUMPTION, "seed": 20261028, "draws": 999}
    first = paired_inference(values, **kwargs)
    repeat = paired_inference(values, **kwargs)
    tiny = paired_inference(values * 1e-100, **kwargs)
    assert first == repeat
    assert first["signflip_pvalue"] == tiny["signflip_pvalue"]
    assert first["signflip_mode"] == "MONTE_CARLO_UNDER_DECLARED_ASSUMPTION"


def test_zero_signflip_is_one_and_assumption_is_not_inferred():
    assert paired_inference([0, 0], signflip_assumption=ASSUMPTION)["signflip_pvalue"] == 1
    assert paired_inference([0, 0])["signflip_pvalue"] is None
    for assumption in ("ZERO_MEAN", [], True):
        with pytest.raises(ContractError):
            paired_inference([0, 0], signflip_assumption=assumption)


@pytest.mark.parametrize("alpha", [True, [], "0.05", float("nan"), float("inf"), 0, 0.5])
def test_inference_rejects_non_scalar_or_invalid_alpha(alpha):
    with pytest.raises(ContractError):
        paired_inference([0.1, 0.2], alpha=alpha)


@pytest.mark.parametrize("p", [201, 246, 247, 255, 256])
def test_impossible_effect_has_no_computed_model_power(p):
    result = geometry_aware_power(
        30, pareto_size=p, effect=-0.05, paired_sd=0.01,
    )
    assert result["status"] == "GEOMETRICALLY_INFEASIBLE_PLANNING_ASSUMPTIONS"
    assert not result["mean_effect_geometrically_possible"]
    assert result["gaussian_t_power_sensitivity"] is None
    assert "MEAN_EFFECT_EXCEEDS_SHARP_GEOMETRIC_BOUND" in result["reason_codes"]


def test_boundary_effect_cannot_have_positive_population_variance():
    result = geometry_aware_power(
        30, pareto_size=200, effect=-0.05, paired_sd=0.01,
    )
    assert result["mean_effect_geometrically_possible"]
    assert not result["variance_geometrically_possible"]
    assert result["maximum_population_variance_at_effect"] == 0
    assert result["gaussian_t_power_sensitivity"] is None
    zero_sd = geometry_aware_power(
        30, pareto_size=200, effect=-0.05, paired_sd=0,
    )
    assert zero_sd["variance_geometrically_possible"]
    assert zero_sd["gaussian_t_power_sensitivity"] is None
    assert "ZERO_VARIANCE_DOES_NOT_DEFINE_PAIRED_T_POWER" in zero_sd["reason_codes"]


def test_geometry_variance_ceiling_is_enforced_without_tolerance():
    # P=100: b=.1, mean=.06 => variance ceiling=.0064 => SD <= .08.
    on_boundary = geometry_aware_power(
        30, pareto_size=100, effect=0.06, paired_sd=0.08,
    )
    assert on_boundary["variance_geometrically_possible"]
    assert on_boundary["maximum_population_variance_at_effect"] == pytest.approx(0.0064)
    above = geometry_aware_power(
        30, pareto_size=100, effect=0.06, paired_sd=math.nextafter(0.08, math.inf),
    )
    assert not above["variance_geometrically_possible"]
    assert above["gaussian_t_power_sensitivity"] is None


def test_possible_geometry_returns_explicitly_limited_model_sensitivity():
    result = geometry_aware_power(
        30, pareto_size=100, effect=-0.05, paired_sd=0.05,
    )
    assert result["status"] == "MODEL_SENSITIVITY_NOT_APPROVED_SAMPLE_SIZE"
    assert result["mean_effect_geometrically_possible"]
    assert result["variance_geometrically_possible"]
    assert result["gaussian_t_power_sensitivity"] == pytest.approx(
        gaussian_paired_power(30, effect=-0.05, paired_sd=0.05)
    )
    assert result["not_design_approval"] is True


@pytest.mark.parametrize("kwargs", [
    {"effect": True, "paired_sd": 0.1},
    {"effect": 0.05, "paired_sd": -1},
    {"effect": float("inf"), "paired_sd": 0.1},
    {"effect": 0.05, "paired_sd": float("nan")},
    {"effect": 0.05, "paired_sd": 0.1, "alpha": True},
])
def test_geometry_power_rejects_invalid_assumptions(kwargs):
    with pytest.raises(ContractError):
        geometry_aware_power(30, pareto_size=100, **kwargs)


def test_finite_extreme_power_inputs_never_return_nan():
    assert gaussian_paired_power(
        30, effect=1e308, paired_sd=1e-300,
    ) == 1
    assert gaussian_paired_power(
        30, effect=0, paired_sd=1e-300,
    ) == pytest.approx(0.05)
