from __future__ import annotations
import json,math,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from day_certifier import certifier,empirical_risk,empirical_risk_original_reference,prove_coverage_bound,check_originals,CertificateBlocked
from run_r22 import make_panel,front,one_run,experiment,historical_day_audit,TAIL_MEAN


def iid(n=100,seed=12):return make_panel('iid_easy_'+str(n),n,seed)

def test_blobs_are_exact_real_crmt():assert check_originals()

def test_risk_function_matches_frozen_on_daily():
    a,_=iid();d=a.mean(axis=2)
    np.testing.assert_allclose(empirical_risk(d),empirical_risk_original_reference(d),atol=1e-12)

def test_true_tail_mean_analytic():
    assert .08<TAIL_MEAN<.10
    a,truth=iid(100,23)
    assert truth.shape==(5,4)
    assert front(truth)=={0,1,2}

def test_4000_easy_actual_certificate_selects_exactly_three():
    a,truth=iid(4000,99)
    r=certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')
    assert r['status']=='CERTIFIED_SELECTION_CONDITIONAL_IID'
    assert set(r['retained_indices'])==front(truth)=={0,1,2}
    assert r['n_retained']==3

def test_200_easy_abstains():
    a,_=iid(200,99);r=certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')
    assert r['status']=='ABSTAIN_CAPACITY_UNCERTAINTY'
    assert len(r['retained_indices'])==5

def test_near_4000_abstains():
    a,truth=make_panel('iid_near_4000',4000,9)
    r=certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')
    assert r['status']=='ABSTAIN_CAPACITY_UNCERTAINTY'
    assert set(front(truth))=={0,1,2}

def test_serial_is_blocked_even_if_no_visible_anomaly():
    a,_=make_panel('serial_easy_200',200,10)
    r=certifier(a,independence_evidence='KNOWN_SERIAL_NOT_IID')
    assert r['status']=='BLOCKED_IID_DAY_EVIDENCE_UNVERIFIED'
    assert 'certified_domination_pairs' not in r

def test_real_unverified_is_blocked():
    a,_=iid()
    r=certifier(a,independence_evidence='REAL_SEEN_TRAIN_NO_PROOF')
    assert r['status'].startswith('BLOCKED_')

def test_missing_day_subsystem_fails_closed():
    a,_=iid();a[0,3,1,2]=np.nan
    with pytest.raises(CertificateBlocked,match='MISSING'):certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')

def test_out_of_support_fails_and_does_not_clip():
    a,_=iid();a[0,3,0,2]=4.001
    with pytest.raises(CertificateBlocked,match='OUT_OF_SUPPORT'):certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')

def test_no_false_support_tightening():
    a,_=iid()
    with pytest.raises(CertificateBlocked,match='OUT_OF_SUPPORT'):
        certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS',upper=(1,1,1,1))

def test_bad_support_config():
    a,_=iid()
    with pytest.raises(CertificateBlocked,match='SUPPORT_INVALID'):certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS',lower=(5,)*4,upper=(4,)*4)

def test_no_missing_candidate():
    a,_=iid()
    with pytest.raises(CertificateBlocked,match='CANDIDATE_IDS'):certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS',candidate_ids=('x',)*5)

def test_bad_day_count_rejected():
    a,_=iid()
    with pytest.raises(CertificateBlocked,match='DAY_GRID'):certifier(a[:,:99],independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')

def test_not_pooling_2n_measurements():
    a,_=iid(100)
    r=certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS')
    assert r['effective_n_independent_units']==100
    assert r['n_subsystems_per_day']==2
    expected=math.sqrt(math.log(2*5*4/.05)/(2*100))
    assert r['cdf_sup_radius']==pytest.approx(expected)

def test_bounds_shrink_with_increased_day_n():
    z=prove_coverage_bound(100,5,(0,)*4,(4,)*4)
    y=prove_coverage_bound(4000,5,(0,)*4,(4,)*4)
    assert y['risk_halfwidths'][0]<z['risk_halfwidths'][0]
    assert z['m']==20 and y['delta']==.05

def test_global_bound_counts_candidate_objectives():
    v=prove_coverage_bound(100,10,(0,)*4,(4,)*4)
    assert v['m']==40 and v['dkw_sup_radius']>0

def test_assumption_evidence_not_inferred_from_data():
    a,_=iid();r=certifier(a,independence_evidence='UNVERIFIED',capacity=3)
    assert r['status']=='BLOCKED_IID_DAY_EVIDENCE_UNVERIFIED'

def test_no_capacity_auto_pruning():
    a,_=iid(200);r=certifier(a,independence_evidence='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS',capacity=3)
    assert r['n_retained']>r['capacity'] and len(r['retained_indices'])==r['n_retained']

def test_paired_inverters_are_arbitrarily_correlated():
    a,_=iid();d=a.mean(axis=2)
    np.testing.assert_allclose(a[:,:,0,:]+a[:,:,1,:],2*d)

def test_two_repetition_all_scenarios():
    e=experiment(2)
    assert len(e['records'])==14 and len(e['summary'])==7
    assert sum(x['n_blocked'] for x in e['summary'])==6
    assert all(x['false_removal_rate']==0 for x in e['summary'] if x['n_measured'])

def test_real_train_sources_are_immutable():
    r=historical_day_audit()
    assert [x['seed'] for x in r['rows']]==[1001,1004,1005]
    assert all(x['train_records']==12600 and x['candidate_count']==256 for x in r['rows'])
    assert all(not x['iid_day_assumption_supported'] for x in r['rows'])

def test_real_train_different_days_per_candidate():
    r=historical_day_audit()
    assert [x['min_days_per_candidate'] for x in r['rows']]==[9,5,5]
    assert all(x['max_days_per_candidate']==106 for x in r['rows'])

def test_no_real_pvalue_or_new_test_claim():
    r=historical_day_audit()
    assert r['source']=='HISTORICALLY_EXPOSED_OPEN_CEM_TRAIN_ONLY'
    assert all('NOT_NEW_TEST' in x['status'] for x in r['rows'])

def test_corrupted_original_blob_blocks(tmp_path):
    p=tmp_path;p.joinpath('risk.py').write_text('mutated')
    with pytest.raises(CertificateBlocked,match='SOURCE_BLOB_MISMATCH'):check_originals(p)

def test_zero_false_in_60_reps_not_zero_upper():
    from run_r22 import wilson_upper
    assert 0.05<wilson_upper(0,60)<.07

def test_day_requirement_256_easy_and_near():
    from day_certifier import required_iid_days_for_pareto_margin
    assert required_iid_days_for_pareto_margin(1.95,256,4)==3220
    assert required_iid_days_for_pareto_margin(.18,256,4)==377620

def test_bad_day_requirement_fails():
    from day_certifier import required_iid_days_for_pareto_margin
    with pytest.raises(CertificateBlocked,match='SAMPLE_SIZE_PARAMETERS'):
        required_iid_days_for_pareto_margin(-1,256,4)

def test_saved_420_records_recompute_consistently():
    from verify_outputs import verify
    assert verify()['experiment_records']==420

def test_original_source_ledger_cannot_be_called_new_test():
    from verify_outputs import verify
    assert verify()['source_train_seeds']==[1001,1004,1005]
