"""CAL-MAXT-v1: exploratory simultaneous bootstrap, no coverage guarantee.

Input must be a complete common chronological panel. Missing/unequal support
is rejected, never silently compressed into adjacent chronological blocks.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..contracts import ContractError, finite_array, integer, strict_risk, pareto_mask

METHODS={'maxT_iid_v1','maxT_circular_block_v1','bonferroni_iid_v1','abstain_v1'}

@dataclass(frozen=True)
class CalibrationResult:
    method_id: str
    upper_differences: np.ndarray
    declarations: np.ndarray
    retained: np.ndarray
    archive_overflow: bool
    bootstrap_tail_resolution_sufficient: bool
    support_blocks: int

def calibrate(samples, *, method='maxT_iid_v1', alpha=0.05, n_boot=399, seed=0, block_length=1, chronology=None, capacity=10):
    x=finite_array(samples,'calibration panel',ndim=3)
    c,n,m=x.shape
    if c<2 or n<8 or m!=4: raise ContractError('panel must be candidates>=2 x blocks>=8 x objectives=4')
    integer(n_boot,'n_boot',199); integer(seed,'seed'); integer(block_length,'block_length',1); integer(capacity,'capacity',1)
    if method not in METHODS or not np.isfinite(alpha) or not 0<alpha<0.5 or block_length>n: raise ContractError('invalid calibration configuration')
    if chronology is not None:
        times=finite_array(chronology,'chronology',ndim=1)
        if len(times)!=n or not np.all(np.diff(times)==1): raise ContractError('missing/nonconsecutive chronological blocks')
    if method=='maxT_circular_block_v1' and chronology is None: raise ContractError('block bootstrap requires explicit complete chronology')
    if method!='maxT_circular_block_v1' and block_length!=1: raise ContractError('iid/abstain method requires block_length=1')
    observed=strict_risk(x); diff=observed[:,None,:]-observed[None,:,:]
    offdiag=~np.eye(c,dtype=bool)
    if method=='abstain_v1':
        upper=np.full((c,c,m),np.inf); sufficient=True
    else:
        rng=np.random.default_rng(seed); boot=[]
        for _ in range(n_boot):
            if method=='maxT_circular_block_v1':
                starts=rng.integers(n,size=int(np.ceil(n/block_length)))
                indices=((starts[:,None]+np.arange(block_length))%n).ravel()[:n]
            else: indices=rng.integers(n,size=n)
            boot.append(strict_risk(x[:,indices,:]))
        b=np.stack(boot)
        delta=b[:,:,None,:]-b[:,None,:,:]-diff[None,:,:,:]
        errors=-delta[:,offdiag,:]
        family_size=c*(c-1)*m
        if method=='bonferroni_iid_v1':
            margin=np.zeros_like(diff)
            margin[offdiag]=np.quantile(errors,1-alpha/family_size,axis=0)
            sufficient=(n_boot+1)*alpha/family_size>=1
        else:
            scale=np.maximum(np.std(errors,axis=0,ddof=1),1e-12)
            max_t=np.max(errors/scale[None,:,:],axis=(1,2))
            critical=max(0.0,float(np.quantile(max_t,1-alpha)))
            margin=np.zeros_like(diff); margin[offdiag]=critical*scale
            sufficient=(n_boot+1)*alpha>=1
        upper=diff+margin
    declarations=np.all(upper<=0,axis=2)&np.any(diff<0,axis=2)&offdiag
    retained=~np.any(declarations,axis=0)
    return CalibrationResult(method,upper,declarations,retained,int(retained.sum())>capacity,sufficient,n)

def ground_truth_metrics(result, truth_risk):
    truth=finite_array(truth_risk,'known truth risk',ndim=2)
    c=len(truth)
    if truth.shape!=(c,4) or result.upper_differences.shape!=(c,c,4): raise ContractError('truth shape mismatch')
    delta=truth[:,None,:]-truth[None,:,:]; offdiag=~np.eye(c,dtype=bool)
    true_dominance=np.all(delta<=0,axis=2)&np.any(delta<0,axis=2)&offdiag
    true_front=pareto_mask(truth)
    return {'family_undercoverage':bool(np.any((delta>result.upper_differences+1e-12)[offdiag])),
        'false_pair_declaration':bool(np.any(result.declarations&~true_dominance)),
        'false_removal':bool(np.any(true_front&~result.retained)),
        'archive_overflow':result.archive_overflow,'archive_size':int(result.retained.sum()),
        'true_front_size':int(true_front.sum())}
