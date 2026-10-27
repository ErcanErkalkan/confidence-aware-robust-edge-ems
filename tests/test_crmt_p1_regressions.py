import math
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.safety import SafetyBlocked, SafetyLimits, simulate_checked
from crmt_edge_ems.r19_feasibility import geometry, design_grid
from jer_microgrid.config import SiteConfig
from jer_microgrid.metrics import compute_metrics


def limits(site=None, *, max_switches=10):
    s=site or SiteConfig()
    return SafetyLimits(soc_min=s.soc_min,soc_max=s.soc_max,
        charge_kw=s.p_ch_max,discharge_kw=s.p_dis_max,energy_kwh=s.e_nom_kwh,
        eta_charge=s.eta_ch,eta_discharge=s.eta_dis,dt_hours=s.ts_hours,
        import_kw=40,export_kw=40,ramp_kw_per_min=20,max_switches=max_switches,
        step_timeout_seconds=10)


def profile(n=3):
    return pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=n,freq='min',tz='UTC'),
                         'base_kw':[10.]*n,'peak_flag':[0]*n})

class Modes:
    def __init__(self,modes): self.modes=modes
    def reset(self): pass
    def step(self,t,*args): return 0.0,{'mode':self.modes[t],'rg_state':'MID'}


def test_mode_flips_match_existing_metric_and_switch_veto():
    site=SiteConfig()
    assert 'SWITCH_LIMIT' in str(pytest.raises(SafetyBlocked,simulate_checked,
        profile(),Modes(['PS','RG','PS']),site,limits(site,max_switches=1)).value)
    result=simulate_checked(profile(),Modes(['PS','RG','PS']),site,limits(site,max_switches=2))
    assert result.meta['switches']==2
    assert result.meta['switch_policy']=='MODE_TRANSITIONS_MATCH_FLIP_PER_DAY'
    # The research metric uses mode transitions / duration in days.
    metric=compute_metrics(result.series,site)['flip_per_day']
    assert math.isclose(metric,2/(3*site.ts_hours/24))


def test_constant_mode_does_not_trigger_veto():
    site=SiteConfig()
    result=simulate_checked(profile(),Modes(['PS','PS','PS']),site,limits(site,max_switches=0))
    assert result.meta['switches']==0


def test_battery_site_limits_cannot_be_weaker_in_veto():
    site=SiteConfig(soc_min=.35,soc_max=.75)
    bad=replace(limits(site),soc_min=.2)
    with pytest.raises(SafetyBlocked,match='SITE_LIMIT_MISMATCH'):
        simulate_checked(profile(2),Modes(['RG','RG']),site,bad)
    bad2=replace(limits(site),discharge_kw=site.p_dis_max+1)
    with pytest.raises(SafetyBlocked,match='SITE_LIMIT_MISMATCH'):
        simulate_checked(profile(2),Modes(['RG','RG']),site,bad2)


def test_mode_without_valid_metadata_fails_closed():
    site=SiteConfig()
    with pytest.raises(SafetyBlocked,match='INVALID_CONTROLLER_MODE'):
        simulate_checked(profile(2),Modes([None,'PS']),site,limits(site))

@pytest.mark.parametrize('p,expected',[ (1,1.),(10,1.),(200,.05),(201,10/201),
                                       (246,10/246),(247,9/247),(255,1/255),(256,0.) ])
def test_exact_sharp_delta_bound(p,expected):
    g=geometry(p)
    assert math.isclose(g.sharp_max_abs_delta_miss,expected,rel_tol=0,abs_tol=1e-14)
    assert g.effect_geometrically_possible == (p<=200)


def test_bound_is_attainable_by_two_legitimate_k10_sets():
    n=256;k=10
    for p in range(1,n+1):
        ref=set(range(p));outside=set(range(p,n))
        all_hits=list(ref)[:min(k,p)]
        best=set((all_hits+list(outside))[:k])
        worst=set((list(outside)+list(ref))[:k])
        assert len(best)==len(worst)==k
        actual=abs(len(best&ref)-len(worst&ref))/p
        assert math.isclose(actual,geometry(p).sharp_max_abs_delta_miss,abs_tol=1e-14)


def test_geometry_invalid_configs_rejected():
    for kw in ({'pareto_size':0},{'pareto_size':257},{'pareto_size':256,'shortlist_size':257},
               {'pareto_size':20,'practical_effect_threshold':float('nan')},
               {'pareto_size':20,'practical_effect_threshold':0}):
        with pytest.raises(ContractError): geometry(**kw)