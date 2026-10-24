"""R22 bounded-day simultaneous Pareto certificate (TRAIN-only diagnostic).

Conditional finite-sample familywise guarantee under IID *daily vectors* and
precommitted almost-sure objective bounds. Does not verify independence from data.
Original CRMT uses pooled controller-block empirical top-k; this day-aggregated
estimand is DIFFERENT, and will only coincide in special cases.
"""
from __future__ import annotations
import hashlib
import sys
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np

Q=0.9
LAMBDA=0.5
DELTA=0.05
OBJECTIVES=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
ORIGINAL_BLOBS={'risk.py':'edee0d3361691535330419d0203757d0b3624638',
                'dominance.py':'c0fa644839407aaf1ac388a5082435a3a446be29',
                'archive.py':'bb644663febea3990ebeb23f47e403ab0c8070f3'}
class CertificateBlocked(ValueError): pass


def check_originals(folder:Path|None=None):
    src=folder or Path(__file__).resolve().parents[1]/'reference_snapshot/crmt_edge_ems'
    for name,sha in ORIGINAL_BLOBS.items():
        b=(src/name).read_bytes()
        found=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if found!=sha:raise CertificateBlocked('BLOCKED_SOURCE_BLOB_MISMATCH: '+name)
    return True


def empirical_risk(x:np.ndarray)->np.ndarray:
    """Risk mean+.5 top decile of daily losses; n required multiple of 10."""
    a=np.asarray(x,dtype=float)
    if a.ndim!=3 or a.shape[2]!=4 or a.shape[1]<20 or a.shape[1]%10:
        raise CertificateBlocked('BLOCKED_DAY_GRID: [candidate,days,4], n>=20 and multiple of ten')
    if not np.isfinite(a).all():raise CertificateBlocked('BLOCKED_NONFINITE_DAILY_OBJECTIVE')
    n=a.shape[1];k=n//10
    return a.mean(axis=1)+LAMBDA*np.partition(a,n-k,axis=1)[:,n-k:,:].mean(axis=1)


def empirical_risk_original_reference(x:np.ndarray)->np.ndarray:
    """Check exactly equal to original CRMT risk-calibrated top-k on complete days."""
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference_snapshot'))
    from crmt_edge_ems.risk import risk_calibrated_score
    res=np.empty((x.shape[0],4))
    for i in range(x.shape[0]):
        for j in range(4):res[i,j]=risk_calibrated_score(x[i,:,j],q=Q,tail_weight=LAMBDA)
    return res


def certifier(blocks:np.ndarray,*,independence_evidence:str,
              lower:tuple[float,...]=(0.,)*4,upper:tuple[float,...]=(4.,)*4,
              delta:float=DELTA,capacity:int=3,candidate_ids:tuple[str,...]|None=None)->dict[str,Any]:
    """Input [candidate,day,subsystem(2),objective(4)], reject missingness.
    DAY average is a NEW estimand; both subsystems of a day must be observed.
    IID is an external design assumption, NOT empirically identified by this code.
    """
    a=np.asarray(blocks,dtype=float)
    if a.ndim!=4 or a.shape[2:]!=(2,4) or a.shape[0]<2:
        raise CertificateBlocked('BLOCKED_INPUT_SCHEMA: exact 2 subsystems per candidate-day')
    c,n,_,_=a.shape
    if candidate_ids is not None and (len(candidate_ids)!=c or len(set(candidate_ids))!=c):
        raise CertificateBlocked('BLOCKED_CANDIDATE_IDS')
    if type(capacity)!=int or capacity<1 or capacity>c:raise CertificateBlocked('BLOCKED_CAPACITY_CONFIG')
    if not (0<delta<1):raise CertificateBlocked('BLOCKED_ALPHA')
    if not np.isfinite(a).all():raise CertificateBlocked('BLOCKED_MISSING_OR_NONFINITE')
    l=np.asarray(lower,dtype=float);u=np.asarray(upper,dtype=float)
    if l.shape!=(4,) or u.shape!=(4,) or not np.isfinite(l).all() or not np.isfinite(u).all() or not np.all(l<u):
        raise CertificateBlocked('BLOCKED_PREDECLARED_SUPPORT_INVALID')
    if np.any(a<l[None,None,None,:]-1e-12) or np.any(a>u[None,None,None,:]+1e-12):
        raise CertificateBlocked('BLOCKED_OUT_OF_SUPPORT_NO_CLIPPING')
    if independence_evidence!='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS':
        return {'status':'BLOCKED_IID_DAY_EVIDENCE_UNVERIFIED','n_days':n,'capacity':capacity,
            'scope':'SEEN_OR_UNVERIFIED_NOT_CERTIFIED',
            'warning':'Cannot infer IID days from a single time series; do not reinterpret as deployment guarantee.'}
    if n<20 or n%10!=0:raise CertificateBlocked('BLOCKED_DAY_GRID_REQUIRED_N_MULTIPLE_10')
    daily=a.mean(axis=2)
    est=empirical_risk(daily)
    assert np.allclose(est,empirical_risk_original_reference(daily),atol=1e-10)
    # DKW+union bound, m=4*c marginals; dependencies within day are unrestricted.
    m=4*c
    eps_cdf=math.sqrt(math.log(2*m/delta)/(2*n))
    radius=(u-l)*(1+LAMBDA/(1-Q))*eps_cdf
    lower_risk=est-radius[None,:]
    upper_risk=est+radius[None,:]
    # Intersection of support-based risk bounds is also coverage-preserving.
    lower_risk=np.maximum(lower_risk,(1+LAMBDA)*l)
    upper_risk=np.minimum(upper_risk,(1+LAMBDA)*u)
    certified=np.zeros((c,c),dtype=bool)
    for i in range(c):
        for j in range(c):
            if i!=j and np.all(upper_risk[i,:]<lower_risk[j,:]-1e-12):certified[i,j]=True
    retained=[j for j in range(c) if not certified[:,j].any()]
    return {'status':'CERTIFIED_SELECTION_CONDITIONAL_IID' if len(retained)<=capacity else 'ABSTAIN_CAPACITY_UNCERTAINTY',
            'scope':'SYNTHETIC_CONDITIONAL_DKW_NOT_OPENCEM_CERTIFICATE',
            'n_candidates':c,'n_days':n,'n_subsystems_per_day':2,'capacity':capacity,
            'effective_n_independent_units':n,'family_alpha':delta,'family_marginals':m,
            'cdf_sup_radius':float(eps_cdf),'risk_halfwidths':radius.tolist(),
            'point_risk':est.tolist(),'lower_risk':lower_risk.tolist(),'upper_risk':upper_risk.tolist(),
            'certified_domination_pairs':[(i,j) for i in range(c) for j in range(c) if certified[i,j]],
            'retained_indices':retained,'n_retained':len(retained),
            'candidate_ids':list(candidate_ids) if candidate_ids else [f'ctrl_{i}' for i in range(c)],
            'warning':'Conditional on fixed bounded IID days only; day averaging changes pooled-block CRMT estimand; no real field safety guarantee.'}


def prove_coverage_bound(n:int,c:int,lo:tuple[float,...],hi:tuple[float,...],delta:float=.05)->dict:
    if n<20 or n%10:raise CertificateBlocked('BLOCKED_DAY_GRID')
    if c<2 or not 0<delta<1:raise CertificateBlocked('BLOCKED_CONFIG')
    width=np.asarray(hi)-np.asarray(lo)
    if width.shape!=(4,) or np.any(width<=0):raise CertificateBlocked('BLOCKED_SUPPORT')
    eps=math.sqrt(math.log(8*c/delta)/(2*n))
    return {'delta':delta,'m':c*4,'n_iid_days':n,'dkw_sup_radius':eps,
            'risk_halfwidths':(width*(1+LAMBDA/(1-Q))*eps).tolist(),
            'guarantee':'P(any marginal population risk outside simultaneous bands) <= delta under IID days and valid fixed support; hence P(any false certified Pareto elimination) <= delta.'}


def required_iid_days_for_pareto_margin(gamma:float,n_candidates:int,range_width:float,delta:float=.05)->int:
    """Conservative sufficient n to separate true risks by margin gamma on all 4 objectives.
    Uses 2*DKW risk radius < gamma, *before* possible support clipping.
    """
    if not all(math.isfinite(x) and x>0 for x in (gamma,range_width,delta)) or not delta<1 or type(n_candidates)!=int or n_candidates<2:
        raise CertificateBlocked('BLOCKED_SAMPLE_SIZE_PARAMETERS')
    m=4*n_candidates
    target=2*range_width*(1+LAMBDA/(1-Q))
    bound=target**2*math.log(2*m/delta)/(2*gamma**2)
    if bound>1e12:raise CertificateBlocked('BLOCKED_INFEASIBLE_DAY_COUNT')
    return max(20,10*(math.floor(bound/10)+1))
