import importlib.util
from pathlib import Path
import pytest
from scipy.stats import binom
from crmt_edge_ems.contracts import ContractError


def module():
    p=Path(__file__).resolve().parents[1]/"experiments/r19_primary/design_sensitivity_20261028.py"
    spec=importlib.util.spec_from_file_location("r19_design_sensitivity_under_test",p)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_two_point_power_matches_independent_binomial_tail():
    result=module().exact_extreme_two_point_power(30,bound=.1,effect=.05)
    assert result["improvement_probability"] == pytest.approx(.75)
    assert result["realized_null_alpha"] <= .05
    assert result["power"] == pytest.approx(binom.sf(result["success_count_cutoff"]-1,30,.75))
    assert result["paired_sd"] == pytest.approx((.1**2-.05**2)**.5)


def test_impossible_effect_and_zero_range_never_receive_power():
    m=module()
    assert m.exact_extreme_two_point_power(30,bound=.04,effect=.05) is None
    assert m.exact_extreme_two_point_power(30,bound=0.,effect=.05) is None
    assert m.bounded_mean_sufficient_n(bound=0.) is None
    with pytest.raises(ContractError):
        m.exact_extreme_two_point_power(True,bound=.1)


def test_distribution_free_sufficient_size_scales_quadratically_with_bound():
    m=module()
    n=m.bounded_mean_sufficient_n(bound=.2)
    quarter=m.bounded_mean_sufficient_n(bound=.1)
    assert 4*quarter-3 <= n <= 4*quarter
