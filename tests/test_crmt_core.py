from __future__ import annotations

import numpy as np

from crmt_edge_ems.allocation import select_for_more_evaluation
from crmt_edge_ems.archive import CandidateRecord
from crmt_edge_ems.dominance import confidence_dominance, pareto_dominates
from crmt_edge_ems.generator import sobol_candidates
from crmt_edge_ems.parameter_space import build_tuned_controller, fixed_controller_parameters, validate_physical
from crmt_edge_ems.risk import empirical_cvar, risk_calibrated_score
from jer_microgrid.config import SiteConfig, SyntheticConfig
from jer_microgrid.controllers import compute_hard_bounds
from jer_microgrid.simulation import simulate_controller
from jer_microgrid.synth import generate_profile


def test_fixed_parameters_are_feasible():
    p = fixed_controller_parameters()
    ok, errors = validate_physical(p)
    assert ok, errors


def test_sobol_candidates_are_feasible_and_deterministic():
    a = sobol_candidates(8, seed=17)
    b = sobol_candidates(8, seed=17)
    assert a == b
    assert all(validate_physical(p)[0] for p in a)


def test_tuned_controller_respects_hard_bounds():
    site = SiteConfig()
    synth = SyntheticConfig(hours=2, scenario_names=["load_step"])
    params = sobol_candidates(1, seed=3)[0]
    profile = generate_profile(11, "load_step", site, synth)
    result = simulate_controller(profile, build_tuned_controller(site, params), site)
    for _, row in result.series.iterrows():
        pmin, pmax = compute_hard_bounds(float(row["soc"]), site)
        assert float(row["cmd_kw"]) >= pmin - 1e-9
        assert float(row["cmd_kw"]) <= pmax + 1e-9


def test_cvar_uses_worst_tail_and_risk_is_not_below_mean():
    x = np.arange(1.0, 11.0)
    assert empirical_cvar(x, q=0.8) == 9.5
    assert risk_calibrated_score(x, q=0.8, tail_weight=0.5) >= np.mean(x)


def test_confidence_dominance_detects_clear_paired_improvement():
    rng = np.random.default_rng(4)
    b = rng.normal(loc=10.0, scale=0.2, size=(30, 4))
    a = b - 1.0
    d = confidence_dominance(a, b, n_boot=800, seed=9)
    assert d.relation == -1


def test_confidence_dominance_refuses_single_block_claim():
    a = np.array([[1.0, 1.0]])
    b = np.array([[2.0, 2.0]])
    assert confidence_dominance(a, b, n_boot=800).relation == 0


def test_pareto_relation():
    assert pareto_dominates(np.array([1.0, 2.0]), np.array([1.0, 3.0]))
    assert not pareto_dominates(np.array([1.0, 4.0]), np.array([2.0, 3.0]))


def test_allocator_prioritizes_frontier_or_uncertain_candidates():
    records = {
        "a": CandidateRecord("a", {}, np.array([[1.0, 1.0], [1.1, 1.1]]), np.array([1.05, 1.05]), ("x", "y")),
        "b": CandidateRecord("b", {}, np.array([[2.0, 2.0], [2.0, 2.0]]), np.array([2.0, 2.0]), ("x", "y")),
        "c": CandidateRecord("c", {}, np.array([[0.8, 1.4], [1.2, 0.8]]), np.array([1.0, 1.1]), ("x", "y")),
    }
    selected = select_for_more_evaluation(records, 2)
    assert "b" not in selected


def test_confidence_risk_dominance_uses_risk_functional():
    from crmt_edge_ems.dominance import confidence_risk_dominance
    from crmt_edge_ems.risk import RiskConfig
    # A has uniformly smaller losses, including the worst-tail observation.
    a = np.array([[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [2, 2, 2, 2]], dtype=float)
    b = np.array([[3, 3, 3, 3], [3, 3, 3, 3], [3, 3, 3, 3], [6, 6, 6, 6]], dtype=float)
    d = confidence_risk_dominance(a, b, risk=RiskConfig(q=0.75, tail_weight=0.5), n_boot=500, seed=7)
    assert d.relation == -1


def test_normalized_power_parameters_scale_with_site():
    from jer_microgrid.config import SiteConfig
    from crmt_edge_ems.parameter_space import build_tuned_controller, fixed_controller_parameters
    s1 = SiteConfig(p_ch_max=50, p_dis_max=50, p_imp_peakcap=40, p_imp_offcap=40, p_exp_peakcap=40, p_exp_offcap=40)
    s2 = SiteConfig(p_ch_max=100, p_dis_max=100, p_imp_peakcap=80, p_imp_offcap=80, p_exp_peakcap=80, p_exp_offcap=80)
    p = fixed_controller_parameters(s1)
    c1 = build_tuned_controller(s1, p)
    c2 = build_tuned_controller(s2, p)
    assert c2.prep_power_cap_kw == 2 * c1.prep_power_cap_kw
    assert c2.near_cap_forecast_buffer_kw == 2 * c1.near_cap_forecast_buffer_kw
