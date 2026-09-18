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
