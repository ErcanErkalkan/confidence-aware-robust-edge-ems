from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.safety import SafetyLimits,SafetyBlocked,require_population,simulate_checked
from jer_microgrid.config import SiteConfig

def limits():
    return SafetyLimits(.2,.8,50,50,100,.95,.95,1/60,100,100,20,10,10)

@pytest.mark.parametrize('kw,code',[
    ({'command_kw':np.nan},'INVALID_OR_MISSING_TELEMETRY'),({'soc':.1},'SOC_OUT_OF_RANGE'),
    ({'command_kw':51},'INVERTER_POWER_LIMIT'),({'soc':.2,'command_kw':10},'SOC_TRANSITION_LIMIT'),
    ({'base_kw':200},'GRID_LIMIT'),({'command_kw':25},'COMMAND_RAMP_LIMIT'),
    ({'switches':11},'SWITCH_LIMIT'),({'elapsed_seconds':11},'STEP_TIMEOUT')])
def test_veto_failure_codes(kw,code):
    args={'soc':.5,'command_kw':0,'base_kw':0};args.update(kw)
    assert code in limits().veto(**args)

def test_invalid_limits_and_fully_rejected_population():
    with pytest.raises(ContractError): replace(limits(),eta_charge=np.nan)
    with pytest.raises(ContractError): replace(limits(),soc_min=.9)
    with pytest.raises(SafetyBlocked,match='ALL_CANDIDATES'): require_population([])

def test_real_existing_controller_integrated_with_veto():
    from crmt_edge_ems.parameter_space import build_tuned_controller,fixed_controller_parameters
    site=SiteConfig();profile=pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=8,freq='min',tz='UTC'),'base_kw':10.,'peak_flag':0})
    result=simulate_checked(profile,build_tuned_controller(site,fixed_controller_parameters()),site,limits())
    assert len(result.series)==8 and result.meta['status']=='SCENARIO_VETO_PASSED'
    assert np.isfinite(result.series[['cmd_kw','soc_next','grid_kw']]).all().all()
    from jer_microgrid.metrics import compute_metrics
    from crmt_edge_ems.contracts import OBJECTIVES
    metrics=compute_metrics(result.series,site)
    assert np.isfinite([metrics[o] for o in OBJECTIVES]).all()

def test_invalid_command_and_duplicate_telemetry_blocked():
    class Bad:
        def reset(self): pass
        def step(self,*args): return np.nan,{}
    p=pd.DataFrame({'timestamp':pd.date_range('2026-01-01',periods=2,freq='min',tz='UTC'),'base_kw':10.,'peak_flag':0})
    with pytest.raises(SafetyBlocked,match='INVALID_COMMAND'): simulate_checked(p,Bad(),SiteConfig(),limits())
    p.loc[1,'timestamp']=p.loc[0,'timestamp']
    with pytest.raises(SafetyBlocked,match='TIME_SUPPORT'): simulate_checked(p,Bad(),SiteConfig(),limits())