import numpy as np
import pandas as pd
import pytest

from jer_microgrid.config import SiteConfig
from crmt_edge_ems.budget import EvaluationBudgetExceeded, EvaluationLedger
from crmt_edge_ems.parameter_space import fixed_controller_parameters
from crmt_edge_ems.replay import ReplayBlock, ReplayEvaluator


def _profile(n=180):
    ts = pd.date_range('2026-01-05', periods=n, freq='1min', tz='UTC')
    x = np.linspace(0, 4*np.pi, n)
    return pd.DataFrame({
        'timestamp': ts,
        'base_kw': 42.0 + 8.0*np.sin(x),
        'peak_flag': np.zeros(n, dtype=int),
    })


def test_evaluation_ledger_atomic_budget_and_audit_table():
    ledger = EvaluationLedger(3)
    e = ledger.reserve('MOPSO', 'c1', ['d1', 'd2'])
    assert len(e) == 2 and ledger.used == 2 and ledger.remaining == 1
    with pytest.raises(EvaluationBudgetExceeded):
        ledger.reserve('MOPSO', 'c2', ['d3', 'd4'])
    # Failed atomic reservation must not consume a partial unit.
    assert ledger.used == 2
    ledger.reserve('MOPSO', 'c2', ['d3'])
    ledger.assert_exact()
    f = ledger.to_frame()
    assert list(f['ordinal']) == [1, 2, 3]
    assert set(f['unit']) == {'controller_block_evaluation'}


def test_replay_evaluator_charges_exactly_one_unit_per_candidate_block():
    site = SiteConfig()
    ledger = EvaluationLedger(2)
    ev = ReplayEvaluator(site, ledger=ledger, method_id='CRMT')
    blocks = [
        ReplayBlock('day1', _profile(), source='unit', split='train'),
        ReplayBlock('day2', _profile(), source='unit', split='train'),
    ]
    out = ev.evaluate(fixed_controller_parameters(site), blocks, candidate_id='fixed')
    assert len(out) == 2
    assert ledger.used == 2
    assert set(out['block_id']) == {'day1', 'day2'}
    assert set(out['split']) == {'train'}


def test_replay_block_rejects_hidden_profile_assumptions():
    site = SiteConfig()
    ev = ReplayEvaluator(site)
    p = _profile().drop(columns='peak_flag')
    with pytest.raises(KeyError):
        ev.evaluate(fixed_controller_parameters(site), [ReplayBlock('bad', p)], candidate_id='x')


def test_crmt_study_and_ledger_share_the_same_budget_unit():
    from crmt_edge_ems.evaluator import LedgeredSyntheticEvaluator, ScenarioBlock
    from crmt_edge_ems.generator import sobol_candidates
    from crmt_edge_ems.study import CRMTStudy

    budget = 12
    ledger = EvaluationLedger(budget)
    evaluator = LedgeredSyntheticEvaluator(ledger=ledger, method_id='CRMT')
    candidates = {f'c{i}': p for i, p in enumerate(sobol_candidates(3, seed=5))}
    blocks = [ScenarioBlock('mixed', i) for i in range(8)]
    result = CRMTStudy(evaluator, initial_blocks=2, allocation_batch=2, n_boot=200).run(
        candidates, blocks, max_evaluations=budget
    )
    assert result.budget_used == budget
    assert ledger.used == budget
    ledger.assert_exact()
    assert set(ledger.to_frame()['candidate_id']).issubset(set(candidates))


def test_opencem_strict_site_model_requires_explicit_assumptions_and_uses_readme_energy():
    from crmt_edge_ems.site_model import (
        OPENCEM_BATTERY_NOMINAL_KWH,
        OPENCEM_BATTERY_MAX_OUTPUT_KW,
        OPENCEM_BATTERY_MAX_CHARGE_KW_NOMINAL,
        OpenCEMSubsystemAssumptions,
        build_opencem_subsystem_site,
    )
    a = OpenCEMSubsystemAssumptions(
        eta_ch=0.95,
        eta_dis=0.95,
        soc_min=0.2,
        soc_max=0.8,
        soc_init=0.5,
        command_ramp_kw_per_min=2.0,
        import_cap_kw=4.0,
        export_cap_kw=3.0,
    )
    site = build_opencem_subsystem_site(a, cadence_minutes=2)
    assert np.isclose(OPENCEM_BATTERY_NOMINAL_KWH, 10.24)
    assert OPENCEM_BATTERY_MAX_OUTPUT_KW == 6.0
    assert np.isclose(OPENCEM_BATTERY_MAX_CHARGE_KW_NOMINAL, 7.68)
    assert np.isclose(site.e_nom_kwh, 10.24)
    assert site.p_dis_max == 6.0
    assert np.isclose(site.p_ch_max, 7.68)
    assert site.p_imp_peakcap == site.p_imp_offcap == 4.0
    assert site.p_exp_peakcap == site.p_exp_offcap == 3.0
    assert np.isclose(site.ts_hours, 2.0 / 60.0)
    assert site.r_max_kw_per_tick == 4.0
    assert site.t_min_ticks == 2
    assert site.w_f == 3
    assert site.horizon_k == 5
    assert site.d_lim == 16.0
    assert np.isclose(site.fbrl_ema_beta_override, 0.4375)
    assert site.proposed_cap_fix_hold_ticks_override == 2
    assert site.proposed_prep_hold_ticks_override == 3
    assert site.proposed_near_cap_window_ticks_override == 2
    assert np.isclose(site.proposed_hold_decay_override, 0.36)


def test_train_only_grid_cap_rule_uses_directional_quantiles_and_rejects_sparse_direction():
    from crmt_edge_ems.site_model import calibrate_train_grid_caps
    a = pd.DataFrame({'base_kw': np.r_[np.arange(1, 201), -np.arange(1, 201)]})
    c = calibrate_train_grid_caps([a], import_quantile=0.9, export_quantile=0.8, min_samples_each_direction=100)
    assert c.n_import_samples == 200 and c.n_export_samples == 200
    assert np.isclose(c.import_cap_kw, np.quantile(np.arange(1, 201), 0.9))
    assert np.isclose(c.export_cap_kw, np.quantile(np.arange(1, 201), 0.8))
    with pytest.raises(ValueError):
        calibrate_train_grid_caps([pd.DataFrame({'base_kw': np.arange(1, 500)})])


def test_primary_opencem_site_factory_is_frozen_and_inverter_specific():
    from crmt_edge_ems.site_model import (
        PRIMARY_COMMAND_RAMP_KW_PER_MIN,
        PRIMARY_OPENCEM_CADENCE_MINUTES,
        build_primary_opencem_site,
        primary_opencem_assumptions,
    )
    a1 = primary_opencem_assumptions(1)
    a2 = primary_opencem_assumptions(2)
    assert PRIMARY_OPENCEM_CADENCE_MINUTES == 2
    assert np.isclose(PRIMARY_COMMAND_RAMP_KW_PER_MIN, 6.84)
    assert np.isclose(a1.import_cap_kw, 0.07188675000000001)
    assert np.isclose(a1.export_cap_kw, 0.16017178571428578)
    assert np.isclose(a2.import_cap_kw, 0.5999499999999999)
    assert np.isclose(a2.export_cap_kw, 0.3675908653846169)
    s1 = build_primary_opencem_site(1)
    s2 = build_primary_opencem_site(2)
    for s in (s1, s2):
        assert np.isclose(s.e_nom_kwh, 10.24)
        assert np.isclose(s.p_dis_max, 6.0)
        assert np.isclose(s.p_ch_max, 7.68)
        assert np.isclose(s.eta_ch, 0.95)
        assert np.isclose(s.eta_dis, 0.95)
        assert np.isclose(s.soc_min, 0.10)
        assert np.isclose(s.soc_max, 1.00)
        assert np.isclose(s.soc_init, 0.50)
        assert np.isclose(s.soc_low_thresh, 0.20)
        assert np.isclose(s.soc_high_thresh, 0.80)
        assert np.isclose(s.r_max_kw_per_tick, 13.68)
        assert np.isclose(s.ts_hours, 2.0 / 60.0)
    assert not np.isclose(s1.p_imp_peakcap, s2.p_imp_peakcap)
    with pytest.raises(KeyError):
        primary_opencem_assumptions(3)


def test_predeclared_site_sensitivities_change_only_locked_model_axes():
    from crmt_edge_ems.protocol import (
        BASELINE_HYPERPARAMETERS,
        CRMT_HYPERPARAMETERS,
        SITE_SENSITIVITY_VARIANTS,
        build_opencem_sensitivity_site,
    )
    ids = {v.variant_id for v in SITE_SENSITIVITY_VARIANTS}
    assert ids == {
        "ETA_LOW_090", "ETA_IDEAL_100", "SOC_CONSERVATIVE_15_95",
        "RAMP_HALF", "RAMP_QUARTER", "TEMPORAL_FLOOR",
    }
    assert BASELINE_HYPERPARAMETERS["NSGAII"]["pop_size"] == 20
    assert BASELINE_HYPERPARAMETERS["MOPSO"]["swarm_size"] == 20
    assert BASELINE_HYPERPARAMETERS["MODE"]["pop_size"] == 20
    assert CRMT_HYPERPARAMETERS["risk_q"] == 0.90
    assert CRMT_HYPERPARAMETERS["tail_weight"] == 0.50

    low = build_opencem_sensitivity_site(1, "ETA_LOW_090")
    ideal = build_opencem_sensitivity_site(1, "ETA_IDEAL_100")
    conservative = build_opencem_sensitivity_site(1, "SOC_CONSERVATIVE_15_95")
    half = build_opencem_sensitivity_site(1, "RAMP_HALF")
    quarter = build_opencem_sensitivity_site(1, "RAMP_QUARTER")
    floor_site = build_opencem_sensitivity_site(1, "TEMPORAL_FLOOR")
    assert np.isclose(low.eta_ch, 0.90) and np.isclose(low.eta_dis, 0.90)
    assert np.isclose(ideal.eta_ch, 1.00) and np.isclose(ideal.eta_dis, 1.00)
    assert np.isclose(conservative.soc_min, 0.15) and np.isclose(conservative.soc_max, 0.95)
    assert np.isclose(half.r_max_kw_per_tick, 6.84)
    assert np.isclose(quarter.r_max_kw_per_tick, 3.42)
    assert floor_site.t_min_ticks == 1
    assert floor_site.proposed_prep_hold_ticks_override == 2
    assert floor_site.w_f == 2
    assert floor_site.horizon_k == 5


def test_confirmatory_optimizer_budget_is_exact_and_population_aligned():
    from crmt_edge_ems.protocol import (
        ALL_METHODS_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET,
        BASELINE_FULL_CANDIDATE_CAPACITY,
        BASELINE_HYPERPARAMETERS,
        CONFIRMATORY_CONTROLLER_BLOCK_BUDGET,
        CRMT_CANDIDATE_POOL_SIZE,
        CRMT_HYPERPARAMETERS,
        FULL_TRAIN_CANDIDATE_COST,
        METHOD_IDS,
        OPTIMIZER_SEEDS,
        PER_METHOD_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET,
        TRAIN_BLOCK_COUNT,
    )
    assert TRAIN_BLOCK_COUNT == 210
    assert FULL_TRAIN_CANDIDATE_COST == 210
    assert CONFIRMATORY_CONTROLLER_BLOCK_BUDGET == 12_600
    assert CONFIRMATORY_CONTROLLER_BLOCK_BUDGET % TRAIN_BLOCK_COUNT == 0
    assert BASELINE_FULL_CANDIDATE_CAPACITY == 60
    assert BASELINE_FULL_CANDIDATE_CAPACITY % BASELINE_HYPERPARAMETERS["NSGAII"]["pop_size"] == 0
    assert BASELINE_FULL_CANDIDATE_CAPACITY % BASELINE_HYPERPARAMETERS["MOPSO"]["swarm_size"] == 0
    assert BASELINE_FULL_CANDIDATE_CAPACITY % BASELINE_HYPERPARAMETERS["MODE"]["pop_size"] == 0
    assert CRMT_CANDIDATE_POOL_SIZE == 256
    assert CRMT_HYPERPARAMETERS["initial_blocks"] * CRMT_CANDIDATE_POOL_SIZE < CONFIRMATORY_CONTROLLER_BLOCK_BUDGET
    assert len(OPTIMIZER_SEEDS) == 30
    assert PER_METHOD_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET == 378_000
    assert len(METHOD_IDS) == 5
    assert ALL_METHODS_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET == 1_890_000


def test_multisite_replay_uses_site_specific_limits_and_atomic_ledger():
    from crmt_edge_ems.replay import MultiSiteReplayEvaluator
    s1 = SiteConfig(p_ch_max=2.0, p_dis_max=2.0, p_imp_contr=4.0, p_exp_phys=4.0,
                    p_imp_peakcap=4.0, p_imp_offcap=4.0, p_exp_peakcap=4.0, p_exp_offcap=4.0)
    s2 = SiteConfig(p_ch_max=7.0, p_dis_max=6.0, p_imp_contr=8.0, p_exp_phys=8.0,
                    p_imp_peakcap=8.0, p_imp_offcap=8.0, p_exp_peakcap=8.0, p_exp_offcap=8.0)
    ledger = EvaluationLedger(2)
    ev = MultiSiteReplayEvaluator({1: s1, 2: s2}, ledger=ledger, method_id="CRMT")
    params = fixed_controller_parameters()
    blocks = [
        ReplayBlock("inv1-day", _profile(), source="unit", split="train", site_id=1),
        ReplayBlock("inv2-day", _profile(), source="unit", split="train", site_id=2),
    ]
    out = ev.evaluate(params, blocks, candidate_id="c1")
    assert ledger.used == 2
    assert set(out["site_id"]) == {"1", "2"}
    with pytest.raises(ValueError, match="missing site_id"):
        ev.evaluate(params, [ReplayBlock("bad", _profile())], candidate_id="bad")


def test_crmt_allocation_skips_exhausted_candidates_and_uses_exact_budget():
    from crmt_edge_ems.evaluator import LedgeredSyntheticEvaluator, ScenarioBlock
    from crmt_edge_ems.study import CRMTStudy
    from crmt_edge_ems.generator import sobol_candidates
    ledger = EvaluationLedger(8)
    ev = LedgeredSyntheticEvaluator(ledger=ledger, method_id="CRMT")
    candidates = {f"c{i}": p for i, p in enumerate(sobol_candidates(2, seed=9))}
    blocks = [ScenarioBlock("mixed", i) for i in range(4)]
    result = CRMTStudy(ev, initial_blocks=2, allocation_batch=1, n_boot=200).run(
        candidates, blocks, max_evaluations=8
    )
    assert result.budget_used == 8
    ledger.assert_exact()
    assert all(len(df) == 4 for df in result.candidate_metrics.values())
