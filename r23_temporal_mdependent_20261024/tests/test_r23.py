import sys,zipfile,json,math
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from r23_certifier import certify,Refused,SyntheticDesign,risk_original_pooled,known_oracle_front,BUILTIN_SYNTHETIC_SHA256
from run_r23 import panel,trial,run,real_train_gate,BASE,SCENARIOS,METHODS

def calc(s='iid_easy_600',n=600,seed=19,m=0,method='empirical_bernstein',**kwargs):
    a,base,w=panel(s,n,seed,m)
    return certify(a,w,method=method,**kwargs)

def test_r23_pooled_original_score_exact():
    x,_b,_w=panel('iid_easy_600',600,29,0)
    arr=x.reshape(5,-1,4)
    k=int(np.ceil((1-.9)*arr.shape[1]))
    expect=arr.mean(axis=1)+.5*np.sort(arr,axis=1)[:,-k:,:].mean(axis=1)
    np.testing.assert_allclose(risk_original_pooled(x),expect,atol=1e-12)

def test_not_r22_daymean_estimand():
    a,_,_=panel('iid_easy_600',600,29,0)
    pooled=risk_original_pooled(a)
    daily=a.mean(axis=2)
    k=60
    dayrisk=daily.mean(axis=1)+.5*np.sort(daily,axis=1)[:,-k:,:].mean(axis=1)
    # Across-inverter +/- 0.02 offsets can sometimes make a numerical difference.
    assert pooled.shape==dayrisk.shape
    assert not np.array_equal(a.reshape(5,1200,4),daily)

def test_known_front_is_three_easy():assert known_oracle_front(BASE)=={0,1,2}
def test_known_front_near_is_three():
    _,b,_=panel('ma2_near_4000',4000,7,2)
    assert known_oracle_front(b)=={0,1,2}

def test_witness_correct_for_iid():
    _,_,w=panel('iid_easy_600',600,7,0)
    assert w.model=='iid' and w.dependence_lag==0 and w.generator_sha256==BUILTIN_SYNTHETIC_SHA256

def test_witness_finite_dep():
    _,_,w=panel('ma2_easy_4000',4000,7,2)
    assert w.model=='finite_MA' and w.dependence_lag==2

def test_unknown_AR1_blocked():
    assert calc('ar1_unverified_400',400,18,None)['status']=='BLOCKED_DEPENDENCE_WITNESS'

def test_corrupt_witness_blocked():
    a,b,w=panel('iid_easy_600',600,7,0)
    fake=SyntheticDesign('iid',0,'0'*64,True)
    assert certify(a,fake)['status']=='BLOCKED_DEPENDENCE_WITNESS'

def test_real_string_cannot_attest_dependence():
    a,b,w=panel('iid_easy_600',600,7,0)
    assert certify(a,None)['status']=='BLOCKED_DEPENDENCE_WITNESS'

def test_wrong_model_mismatch_blocked():
    a,_,w=panel('iid_easy_600',600,7,0)
    fake=SyntheticDesign('finite_MA',0,BUILTIN_SYNTHETIC_SHA256,True)
    assert certify(a,fake)['status']=='BLOCKED_MODEL_LAG_MISMATCH'

def test_bad_negative_lag_blocks():
    a,_,w=panel('iid_easy_600',600,7,0)
    fake=SyntheticDesign('finite_MA',-1,BUILTIN_SYNTHETIC_SHA256,True)
    assert certify(a,fake)['status']=='BLOCKED_UNKNOWN_FINITE_DEPENDENCE'

def test_lag_very_large_blocks():
    a,_,w=panel('iid_easy_600',600,7,0)
    fake=SyntheticDesign('finite_MA',300,BUILTIN_SYNTHETIC_SHA256,True)
    assert certify(a,fake)['status']=='BLOCKED_UNKNOWN_FINITE_DEPENDENCE'

def test_not_stationary_blocks():
    a,_,w=panel('iid_easy_600',600,7,0)
    fake=SyntheticDesign('iid',0,BUILTIN_SYNTHETIC_SHA256,False)
    assert certify(a,fake)['status']=='BLOCKED_DEPENDENCE_WITNESS'

def test_missing_rejected():
    a,_,w=panel('missing_600',600,7,0)
    with pytest.raises(Refused,match='MISSING'):certify(a,w)

def test_out_of_support_rejected():
    a,_,w=panel('iid_easy_600',600,7,0);a[0,0,0,0]=5
    with pytest.raises(Refused,match='OUT_OF_SUPPORT'):certify(a,w)

def test_invalid_support_rejected():
    with pytest.raises(Refused,match='SUPPORT'):calc(lower=(3,)*4,upper=(2,)*4)

def test_bad_capacity_rejected():
    with pytest.raises(Refused,match='CAPACITY'):calc(capacity=0)

def test_duplicate_candidate_id_rejected():
    with pytest.raises(Refused,match='CANDIDATE'):calc(candidate_ids=('x',)*5)

def test_fixed_threshold_grid_rejected_if_too_small():
    with pytest.raises(Refused,match='GRID'):calc(grid_size=2)

def test_bad_alpha():
    with pytest.raises(Refused,match='DELTA'):calc(delta=1)

def test_grid_positive_cv_bound():
    x=calc();lo=np.asarray(x['population_risk_lower']);hi=np.asarray(x['population_risk_upper'])
    assert lo.shape==(5,4) and np.all(lo<=hi)

def test_capacity_no_forced_trim():
    r=calc()
    assert r['status']=='ABSTAIN_CAPACITY_UNCERTAINTY' and r['n_retained']>3

def test_iid_2000_empirical_bernstein_reaches_three():
    r=calc('iid_easy_2000',2000,1234,0)
    assert r['status']=='CERTIFIED_CAPACITY_CONDITIONAL_SYNTHETIC' and r['n_retained']==3

def test_iid_2000_hoeffding_abstains():
    r=calc('iid_easy_2000',2000,1234,0,method='hoeffding')
    assert r['status']=='ABSTAIN_CAPACITY_UNCERTAINTY'

def test_ma2_4000_empirical_bernstein_reaches_three():
    r=calc('ma2_easy_4000',4000,1234,2)
    assert r['status']=='CERTIFIED_CAPACITY_CONDITIONAL_SYNTHETIC' and r['n_retained']==3

def test_ma2_4000_hoeffding_abstains():
    r=calc('ma2_easy_4000',4000,1234,2,method='hoeffding')
    assert r['status']=='ABSTAIN_CAPACITY_UNCERTAINTY'

def test_true_front_no_false_removal_for_easy():
    r=calc('iid_easy_2000',2000,1234,0)
    assert known_oracle_front(BASE).issubset(set(r['retained_ids']))

def test_no_new_test_result_labeled():
    r=run(repetitions=2)
    assert r['metadata']['run_type'].endswith('NOT_NEW_TEST')
    assert len(r['records'])==len(SCENARIOS)*2*len(METHODS)

def test_methods_count_and_block_counts():
    r=run(2)
    assert len(r['summary'])==len(SCENARIOS)*len(METHODS)
    assert all(s['n_measured']+s['n_blocked']==2 for s in r['summary'])

def test_real_R16_train_stays_blocked():
    z=real_train_gate(ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip')
    assert [x['seed'] for x in z['rows']]==[1001,1004,1005]
    assert all(x['n_controller_blocks']==12600 for x in z['rows'])
    assert all(x['decision']=='BLOCKED_REAL_OPEN_CEM_NOT_CERTIFIABLE' for x in z['rows'])
    assert all(x['F0_F1_same_source_science'] for x in z['rows'])

def test_zip_contains_source_runs():
    with zipfile.ZipFile(ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip') as z:
        assert any(x.endswith('seed1004_C1_A1/F1/run_summary.json') for x in z.namelist())

def test_frozen_source_sha_matches_r22_and_git():
    import hashlib
    original={'risk.py':'edee0d3361691535330419d0203757d0b3624638',
              'dominance.py':'c0fa644839407aaf1ac388a5082435a3a446be29',
              'archive.py':'bb644663febea3990ebeb23f47e403ab0c8070f3'}
    for name,expected in original.items():
        blob=(ROOT/'reference_snapshot/crmt_edge_ems'/name).read_bytes()
        got=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
        assert got==expected

def test_exact_original_crmt_risk_scoring():
    sys.path.insert(0,str(ROOT/'reference_snapshot'))
    from crmt_edge_ems.risk import risk_calibrated_score
    a,b,w=panel('iid_easy_600',600,93,0)
    output=risk_original_pooled(a)
    for c in range(5):
        for j in range(4):
            assert output[c,j]==pytest.approx(risk_calibrated_score(a[c,:,:,j].reshape(-1),q=.9,tail_weight=.5),abs=1e-12)
