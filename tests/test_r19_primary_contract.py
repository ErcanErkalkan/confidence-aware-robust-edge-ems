import copy
import numpy as np
import pytest
from crmt_edge_ems.contracts import ContractError,strict_risk
from crmt_edge_ems.r19_primary import PrimaryDesign,select_shortlists,audit_fidelity,aggregate_seed_differences

def fixture():
    ids=[f'c{i:03d}' for i in range(256)]
    # 56*50 + 200*49 = 12600 fixed shared discovery events.
    observations={cid:{f'd{b:02d}':[float(i)]*4 for b in range(50 if i<56 else 49)} for i,cid in enumerate(ids)}
    ledger=[(c,b) for c,rows in observations.items() for b in rows]
    archives={'F0':ids[:20],'F1':ids[1:21]}
    return ids,observations,ledger,archives

def test_r19_fixed_contract_ranking_and_no_audit_during_selection():
    ids,obs,ledger,archives=fixture()
    selection=select_shortlists(ids,obs,ledger,list(reversed(ledger)),archives)
    assert selection['selected']['F0']==ids[:10]
    assert selection['selected']['F1']==ids[1:11]
    assert selection['B']==10 and selection['locked'] is False
    audit={c:{f'a{b}':[float(i)]*4 for b in range(8)} for i,c in enumerate(ids)}
    result=audit_fidelity(selection,audit)
    assert result['reference_ids']==['c000']
    assert result['miss_rate']=={'F0':0.0,'F1':1.0} and result['delta_miss']==1

def test_discovery_ties_resolve_lexical_id():
    ids,obs,ledger,archives=fixture()
    for rows in obs.values():
        for b in rows: rows[b]=[1.0]*4
    s=select_shortlists(list(reversed(ids)),obs,ledger,ledger,archives)
    assert s['selected']['F0']==ids[:10]

@pytest.mark.parametrize('change',[{'b':9},{'k':20},{'locked':True},{'c':True},{'backfill':True},{'discovery_events':12600.0}])
def test_preserve_primary_estimand(change):
    with pytest.raises(ContractError): PrimaryDesign(**change)

def test_capacity_blocked_no_backfill():
    ids,obs,ledger,archives=fixture(); archives['F0']=ids[:9]
    assert select_shortlists(ids,obs,ledger,ledger,archives)['status']=='BLOCKED_CAPACITY'

@pytest.mark.parametrize('fault',['different_ledger','duplicate','missing_observation','unknown_archive','nonfinite','audit_in_discovery'])
def test_r19_negative_paths(fault):
    ids,obs,ledger,archives=fixture(); l1=copy.deepcopy(ledger)
    if fault=='different_ledger': l1[0]=('c000','d49'); l1[49]=('c000','d00'); l1[50]=('c001','d00'); l1[99]=('c001','d01')
    if fault=='duplicate': l1[0]=l1[1]
    if fault=='missing_observation': del obs['c000']['d00']
    if fault=='unknown_archive': archives['F0'].append('alien')
    if fault=='nonfinite': obs['c000']['d00'][0]=float('nan')
    if fault=='audit_in_discovery': obs['c000']['AUDIT_FORBIDDEN']=[0.0]*4
    with pytest.raises(ContractError): select_shortlists(ids,obs,ledger,l1,archives)

def test_audit_tamper_overlap_and_missing_seed_rejected():
    ids,obs,ledger,archives=fixture(); s=select_shortlists(ids,obs,ledger,ledger,archives)
    audit={c:{f'd{b:02d}':[0.0]*4 for b in range(8)} for c in ids}
    with pytest.raises(ContractError,match='overlapping'): audit_fidelity(s,audit)
    s['selected']['F0'][0]='c255'
    with pytest.raises(ContractError,match='lock'): audit_fidelity(s,audit)
    with pytest.raises(ContractError,match='missing'): aggregate_seed_differences([{'seed':2001}],range(2001,2031))

@pytest.mark.parametrize('bad',[np.nan,np.inf,-np.inf])
def test_strict_risk_never_drops_nonfinite(bad):
    x=np.ones((12,4));x[0,0]=bad
    with pytest.raises(ContractError): strict_risk(x)

def test_risk_matches_original_finite_functional():
    from crmt_edge_ems.risk import risk_calibrated_score
    x=np.arange(40,dtype=float).reshape(10,4)
    assert np.allclose(strict_risk(x),[risk_calibrated_score(x[:,i]) for i in range(4)])