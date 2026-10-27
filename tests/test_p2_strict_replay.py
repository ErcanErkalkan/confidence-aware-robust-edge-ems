"""Read-only engineering regressions: historical implementation left intact."""
import math
import numpy as np
import pandas as pd
import pytest
from crmt_edge_ems.contracts import ContractError, OBJECTIVES
from crmt_edge_ems.replay import ReplayBlock
from crmt_edge_ems.risk import aggregate_objectives
from crmt_edge_ems.strict_replay_v2 import StrictReplayBlock, StrictReplayEvaluator
from crmt_edge_ems.parameter_space import fixed_controller_parameters
from jer_microgrid.config import SiteConfig


def profile():
    return pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=10, freq='2min', tz='UTC'),
                         'base_kw': [5.0]*10, 'peak_flag': [0]*10})


def block(p=None, **kwargs):
    return StrictReplayBlock(block_id='B01', profile=profile() if p is None else p,
                             split='TRAIN', cadence_minutes=2, expected_ticks=10, **kwargs)


def test_fractional_peak_flag_rejected_even_though_legacy_accepts():
    p = profile(); p['peak_flag']=p['peak_flag'].astype(float); p.loc[3, 'peak_flag'] = .5
    assert ReplayBlock('legacy',p).validated_profile().loc[3,'peak_flag'] == .5
    with pytest.raises(ContractError, match='exact 0 or 1'): block(p).validated_profile()


def test_nonfinite_load_rejected_even_though_legacy_accepts():
    p=profile();p.loc[0,'base_kw']=float('inf')
    assert math.isinf(ReplayBlock('legacy',p).validated_profile().loc[0,'base_kw'])
    with pytest.raises(ContractError, match='finite'): block(p).validated_profile()


@pytest.mark.parametrize('fault', ['timestamp_naive','duplicate','gap','offgrid','NaT','extra_row', 'peak_string','peak_missing','wrong_peak','base_string', 'nonfinite_nan','nonfinite_neg_inf'])
def test_bad_profile_rejected(fault):
    p=profile()
    if fault=='timestamp_naive': p['timestamp']=p['timestamp'].dt.tz_localize(None)
    elif fault=='duplicate': p.loc[1,'timestamp']=p.loc[0,'timestamp']
    elif fault=='gap': p.loc[5:,'timestamp'] += pd.Timedelta(minutes=2)
    elif fault=='offgrid': p.loc[5,'timestamp'] += pd.Timedelta(seconds=1)
    elif fault=='NaT': p.loc[0,'timestamp']=pd.NaT
    elif fault=='extra_row': p=pd.concat([p,p.iloc[-1:]], ignore_index=True)
    elif fault=='peak_string': p['peak_flag']=p['peak_flag'].astype(str)
    elif fault=='peak_missing': p.loc[4,'peak_flag']=np.nan
    elif fault=='wrong_peak': p.loc[2,'peak_flag']=2
    elif fault=='base_string': p['base_kw']=p['base_kw'].astype(str)
    elif fault=='nonfinite_nan': p.loc[2,'base_kw']=np.nan
    elif fault=='nonfinite_neg_inf': p.loc[2,'base_kw']=-np.inf
    with pytest.raises(ContractError): block(p).validated_profile()


def test_good_profile_retains_exact_support_and_values():
    p=block().validated_profile()
    assert len(p)==10 and p['peak_flag'].dtype.kind in 'iu'
    assert p['base_kw'].eq(5).all() and p['timestamp'].dt.tz is not None


def test_strict_aggregate_rejects_any_nonfinite_objective():
    p=pd.DataFrame([{key:1.0 for key in OBJECTIVES},{key:np.nan for key in OBJECTIVES}])
    assert all(math.isclose(x,1.5) for x in aggregate_objectives(p).values())
    with pytest.raises(ContractError, match='finite'):
        StrictReplayEvaluator.aggregate(p)


def test_strict_aggregate_valid_score_exact_formula():
    p=pd.DataFrame([{key:float(i) for key in OBJECTIVES} for i in (1,2,3,4)])
    r=StrictReplayEvaluator.aggregate(p)
    assert all(math.isclose(x, 2.5+.5*4) for x in r.values())


def test_scientific_replay_must_use_strict_block():
    ev=StrictReplayEvaluator(SiteConfig(ts_hours=2/60))
    with pytest.raises(ContractError, match='StrictReplayBlock'):
        ev.evaluate(fixed_controller_parameters(),[ReplayBlock('legacy',profile())],candidate_id='test')


def test_evaluator_preflights_all_blocks_before_simulating():
    ev=StrictReplayEvaluator(SiteConfig(ts_hours=2/60))
    p=profile(); p['peak_flag']=p['peak_flag'].astype(float); p.loc[1,'peak_flag']=.5
    valid=block()
    invalid=StrictReplayBlock(block_id='B02',profile=p,cadence_minutes=2,expected_ticks=10)
    with pytest.raises(ContractError, match='exact 0 or 1'):
        ev.evaluate(fixed_controller_parameters(),[valid,invalid],candidate_id='test')


def test_one_actual_controller_replay_and_metrics():
    site=SiteConfig(ts_hours=2/60)
    ev=StrictReplayEvaluator(site)
    p=ev.evaluate(fixed_controller_parameters(site),[block()],candidate_id='test')
    assert len(p)==1 and np.isfinite(p[list(OBJECTIVES)].to_numpy()).all()
