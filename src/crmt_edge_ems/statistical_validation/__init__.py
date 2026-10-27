"""Seed-level inference sensitivity; no automatic confirmatory approval."""
from __future__ import annotations
import itertools
import math
import numpy as np
from scipy import stats
from ..contracts import ContractError, finite_array, integer

def paired_inference(differences, *, alpha=0.05, signflip_assumption=None, seed=20261027, draws=9999):
    d=finite_array(differences,'paired seed differences',ndim=1)
    if len(d)<2 or np.any(np.abs(d)>1): raise ContractError('at least two seed-level MissRate differences in [-1,1] required')
    if not np.isfinite(alpha) or not 0<alpha<0.5: raise ContractError('alpha in (0,0.5) required')
    integer(seed,'seed'); integer(draws,'draws',1)
    mean=float(d.mean()); sd=float(d.std(ddof=1)); n=len(d)
    # Range width 2; independent bounded differences, common conditional dataset.
    radius=math.sqrt(2*math.log(2/alpha)/n)
    result={'schema_version':1,'status':'EXPLORATORY_SENSITIVITY','n_seeds':n,'mean_delta':mean,'paired_sd':sd,
        'bounded_mean_ci':[max(-1.0,mean-radius),min(1.0,mean+radius)],
        'bounded_ci_assumption':'Independent seed draws conditional on the fixed dataset; each difference lies in [-1,1]',
        't_test_pvalue':None,'t_mean_ci':None,'signflip_pvalue':None,
        't_assumption':'Exact only for iid Gaussian differences; otherwise an asymptotic sensitivity, not a guaranteed finite-sample test',
        'signflip_assumption':signflip_assumption,'signflip_reason':'Blocked unless symmetry or randomized paired assignment is justified'}
    if sd>0:
        t=stats.ttest_1samp(d,0,nan_policy='raise'); ci=t.confidence_interval(1-alpha)
        result.update(t_test_pvalue=float(t.pvalue),t_mean_ci=[float(ci.low),float(ci.high)])
    if signflip_assumption is not None:
        if signflip_assumption not in {'INDEPENDENT_SYMMETRIC_DIFFERENCES','RANDOMIZED_PAIRED_ASSIGNMENT'}: raise ContractError('sign-flip validity assumption is required; zero mean alone is insufficient')
        observed=abs(mean)
        if n<=16:
            extreme=sum(abs(float(np.mean(d*np.asarray(s))))>=observed-1e-14 for s in itertools.product((-1,1),repeat=n))
            p=extreme/(2**n); mode='EXACT_UNDER_DECLARED_ASSUMPTION'; mcse=None
        else:
            rng=np.random.default_rng(seed); extreme=0
            for first in range(0,draws,1024):
                signs=rng.choice((-1,1),size=(min(1024,draws-first),n))
                extreme+=int(np.sum(np.abs((signs*d).mean(axis=1))>=observed-1e-14))
            p=(extreme+1)/(draws+1); mode='MONTE_CARLO_UNDER_DECLARED_ASSUMPTION'; mcse=math.sqrt(p*(1-p)/draws)
        result.update(signflip_pvalue=p,signflip_mode=mode,signflip_mcse=mcse,signflip_reason='Assumption declared, not independently verified')
    return result

def gaussian_paired_power(n, *, effect, paired_sd, alpha=0.05):
    """Two-sided paired t power under iid Gaussian seed differences only."""
    integer(n,'n',2)
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (effect,paired_sd,alpha)) or paired_sd<=0 or not 0<alpha<0.5: raise ContractError('finite effect, positive paired SD and valid alpha required')
    threshold=stats.t.ppf(1-alpha/2,n-1); noncentrality=abs(effect)*math.sqrt(n)/paired_sd
    return float(stats.nct.sf(threshold,n-1,noncentrality)+stats.nct.cdf(-threshold,n-1,noncentrality))

def power_sensitivity(*, sizes=(10,20,30,50,100,200), effects=(0.02,0.05,0.1), paired_sds=(0.05,0.1,0.2)):
    return [{'n':n,'minimum_difference':e,'paired_sd_assumption':s,'power':gaussian_paired_power(n,effect=e,paired_sd=s),
             'status':'MODEL_SENSITIVITY_NOT_APPROVED_SAMPLE_SIZE'} for n,e,s in itertools.product(sizes,effects,paired_sds)]
