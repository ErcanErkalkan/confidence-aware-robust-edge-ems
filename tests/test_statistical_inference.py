import numpy as np
import pytest
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.statistical_validation import gaussian_paired_power,paired_inference

def test_power_null_and_monotonicity():
    assert gaussian_paired_power(30,effect=0,paired_sd=.1)==pytest.approx(.05)
    assert gaussian_paired_power(100,effect=.05,paired_sd=.1)>gaussian_paired_power(30,effect=.05,paired_sd=.1)
    assert gaussian_paired_power(30,effect=.05,paired_sd=.1)>gaussian_paired_power(30,effect=.02,paired_sd=.1)

def test_signflip_not_assumed_from_zero_mean():
    r=paired_inference([-.5,0,.25,.25]); assert r['signflip_pvalue'] is None
    with pytest.raises(ContractError): paired_inference([-.5,0,.25,.25],signflip_assumption='ZERO_MEAN')

def test_exact_signflip_and_t_alternative():
    r=paired_inference([.1,.2,.3],signflip_assumption='INDEPENDENT_SYMMETRIC_DIFFERENCES')
    assert r['signflip_pvalue']==.25 and r['t_test_pvalue'] is not None
    assert r['bounded_mean_ci'][0]<=r['mean_delta']<=r['bounded_mean_ci'][1]

@pytest.mark.parametrize('d',[[],[0],[np.nan,0],[2,0],[-1,np.inf]])
def test_inference_rejects_missing_or_invalid_seeds(d):
    with pytest.raises(ContractError): paired_inference(d)