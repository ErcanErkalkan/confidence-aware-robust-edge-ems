import numpy as np
import pytest
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.calibration import calibrate,ground_truth_metrics

def test_calibration_known_separation_and_determinism():
    rng=np.random.default_rng(7); a=rng.normal(size=(1,32,4)); x=np.concatenate([a,a+3,a+6],axis=0)
    r=calibrate(x,n_boot=199,seed=12,capacity=1)
    s=calibrate(x,n_boot=199,seed=12,capacity=1)
    assert np.array_equal(r.retained,[True,False,False])
    assert np.array_equal(r.upper_differences,s.upper_differences)
    m=ground_truth_metrics(r,np.asarray([[0]*4,[4.5]*4,[9]*4]))
    assert m['false_removal'] is False and m['false_pair_declaration'] is False

def test_abstention_overflow_never_deletes_true_pareto():
    x=np.ones((12,12,4)); r=calibrate(x,method='abstain_v1',capacity=10)
    m=ground_truth_metrics(r,np.ones((12,4)))
    assert m['archive_overflow'] and m['archive_size']==12 and not m['false_removal'] and not m['family_undercoverage']

@pytest.mark.parametrize('bad',['nan','short','gap','unequal_width','no_chronology'])
def test_calibration_invalid_support_fails_closed(bad):
    x=np.ones((3,16,4));kwargs={}
    if bad=='nan': x[0,0,0]=np.nan
    if bad=='short': x=x[:,:3,:]
    if bad=='gap': kwargs={'chronology':[0,2]+list(range(3,17))}
    if bad=='unequal_width': x=x[:,:,:3]
    if bad=='no_chronology': kwargs={'method':'maxT_circular_block_v1','block_length':4}
    with pytest.raises(ContractError): calibrate(x,**kwargs)

def test_block_method_and_global_rng_isolation():
    np.random.seed(99); expected=np.random.random(3);np.random.seed(99)
    x=np.random.default_rng(8).normal(size=(4,16,4))
    r=calibrate(x,method='maxT_circular_block_v1',block_length=4,chronology=list(range(16)),n_boot=199)
    assert np.array_equal(np.random.random(3),expected) and r.method_id!='maxT_iid_v1'
