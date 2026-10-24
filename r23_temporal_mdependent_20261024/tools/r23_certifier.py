"""R23 conditional certificate for original *pooled inverter/block* CRMT risk.

Simultaneous empirical-Bernstein (or Hoeffding) confidence bands using fixed
hinge grids, residue colors and m-dependent stationary day vectors.
This is a SYNTHETIC / STUDY-ONLY prototype. No runtime user string can verify
stationarity, finite dependence, loss supports or a field safety claim.
"""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass
from typing import Any
import numpy as np

Q=.9
LAMBDA=.5
OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
BUILTIN_SYNTHETIC_SHA256=hashlib.sha256(b'R23_FIXED_GENERATOR_V1').hexdigest()

class Refused(ValueError): pass

@dataclass(frozen=True)
class SyntheticDesign:
    """Witness created only by the bundled synthetic generator, NOT field attestation."""
    model: str
    dependence_lag: int
    generator_sha256: str
    stationary: bool
    source: str='SYNTHETIC_ONLY'


def _sha(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _calibration_radius(samples:np.ndarray, bound_range:float, ln:float, method:str) -> np.ndarray:
    """Samples [ncolor, functions]. Two-sided, simultaneous via union bound."""
    k=len(samples)
    if k<2:raise Refused('INSUFFICIENT_INDEPENDENT_COLOR_SAMPLES')
    if method=='hoeffding':
        return np.full(samples.shape[1],bound_range*math.sqrt(ln/(2*k)))
    if method!='empirical_bernstein':raise Refused('UNKNOWN_BOUND_METHOD')
    v=np.var(samples,axis=0,ddof=1)
    # Maurer-Pontil empirical Bernstein, deliberately conservative two-sided log.
    return np.sqrt(2*v*ln/k)+(7*bound_range*ln/(3*(k-1)))


def risk_original_pooled(x:np.ndarray)->np.ndarray:
    """Exact original top-k formula over all subsystem BLOCKS, not daily averages."""
    x=np.asarray(x,float)
    if x.ndim!=4 or x.shape[2:]!=(2,4) or x.shape[1]<2 or not np.isfinite(x).all():
        raise Refused('BAD_OBJECTIVE_GRID')
    pooled=x.reshape(x.shape[0],x.shape[1]*2,4)
    count=pooled.shape[1];k=max(1,math.ceil((1-Q)*count))
    return pooled.mean(axis=1)+LAMBDA*np.partition(pooled,count-k,axis=1)[:,-k:,:].mean(axis=1)


def certify(x:np.ndarray, witness:SyntheticDesign | None, *,
            lower=(0.,0.,0.,0.), upper=(4.,4.,4.,4.), delta=.05,
            capacity=3, grid_size=31, method='empirical_bernstein',
            candidate_ids:tuple[str,...]|None=None)->dict[str,Any]:
    """Conditional global FWER bound for fixed C candidates, fixed supports and known lag-m.

    For each candidate/objective, pooled-block CVaR has Rockafellar form
       inf_t { t + E[(X-t)_+]/(1-q) }.
    The empirical process is indexed by PREDECLARED fixed hinge t grid. Each
    residue color modulo (m+1) is IID (under strict stationarity and m-dependence).
    Hoeffding or empirical Bernstein on each color is unioned over all functions;
    weighted radii give a rigorous bound for pooled marginal risk. Lipschitz
    grid approximation controls the lower CVaR limit.
    """
    x=np.asarray(x,float)
    if x.ndim!=4 or x.shape[2:]!=(2,4) or x.shape[0]<2:raise Refused('INPUT_SHAPE')
    c,n,_,_ = x.shape
    if not np.isfinite(x).all():raise Refused('MISSING_OR_NONFINITE')
    if candidate_ids is not None and (len(candidate_ids)!=c or len(set(candidate_ids))!=c or any(not s for s in candidate_ids)):
        raise Refused('CANDIDATE_IDENTITY')
    if type(capacity)!=int or not 1<=capacity<=c:raise Refused('CAPACITY')
    if type(grid_size)!=int or not 3<=grid_size<=501:raise Refused('PREDECLARED_GRID_SIZE')
    if not 0<delta<1:raise Refused('DELTA')
    lo=np.asarray(lower,dtype=float);hi=np.asarray(upper,dtype=float)
    if lo.shape!=(4,) or hi.shape!=(4,) or not np.isfinite(lo).all() or not np.isfinite(hi).all() or not np.all(lo<hi):
        raise Refused('UNVERIFIED_SUPPORT')
    if np.any(x<lo[None,None,None,:]-1e-12) or np.any(x>hi[None,None,None,:]+1e-12):
        raise Refused('OUT_OF_SUPPORT_NO_CLIPPING')
    if witness is None or witness.source!='SYNTHETIC_ONLY' or witness.generator_sha256!=BUILTIN_SYNTHETIC_SHA256 or witness.model not in ('iid','finite_MA') or not witness.stationary:
        return {'status':'BLOCKED_DEPENDENCE_WITNESS','certified':False,'source':'NO_PROVEN_REAL_WORLD_ASSUMPTIONS'}
    if type(witness.dependence_lag)!=int or witness.dependence_lag<0 or witness.dependence_lag>n//3:
        return {'status':'BLOCKED_UNKNOWN_FINITE_DEPENDENCE','certified':False}
    if (witness.model=='iid') != (witness.dependence_lag==0):
        return {'status':'BLOCKED_MODEL_LAG_MISMATCH','certified':False}
    colors=witness.dependence_lag+1
    group=[np.arange(r,n,colors) for r in range(colors)]
    if any(len(idx)<2 for idx in group):
        return {'status':'ABSTAIN_TOO_FEW_COLOR_SAMPLES','certified':False}
    # Fixed threshold functions count: mean plus grid hinge evaluations.
    family_functions = c*4*(grid_size+1)*colors
    ln=math.log(4*family_functions/delta)
    mu_lo=np.zeros((c,4));mu_hi=np.zeros((c,4))
    cv_lo=np.zeros((c,4));cv_hi=np.zeros((c,4))
    estimated=risk_original_pooled(x)
    max_hinge_gap=0.
    for j in range(4):
        width=float(hi[j]-lo[j]);thresholds=np.linspace(lo[j],hi[j],grid_size)
        step=width/(grid_size-1);max_hinge_gap=max(max_hinge_gap,step)
        for i in range(c):
            # g_t(day) = mean across two subsystems of hinge(X_subsystem - t)
            day_mean=x[i,:,:,j].mean(axis=1)
            hinge=np.maximum(x[i,:,:,j,None]-thresholds[None,None,:],0).mean(axis=1)
            features=np.column_stack((day_mean,hinge))
            feature_hat=features.mean(axis=0)
            radius=np.zeros(grid_size+1)
            for idx in group:
                radius += (len(idx)/n)*_calibration_radius(features[idx],width,ln,method)
            # Fixed-grid CVaR envelope, Lipschitz discretization on LOWER side.
            phihat=thresholds+feature_hat[1:]/(1-Q)
            cr=float(np.min(phihat));h=float(radius[1:].max()/(1-Q))
            lip=max(1,Q/(1-Q))
            mu_lo[i,j]=max(lo[j],feature_hat[0]-radius[0])
            mu_hi[i,j]=min(hi[j],feature_hat[0]+radius[0])
            cv_lo[i,j]=max(lo[j],cr-h-lip*step/2)
            cv_hi[i,j]=min(hi[j],cr+h)
    Rlo=mu_lo+LAMBDA*cv_lo
    Rhi=mu_hi+LAMBDA*cv_hi
    domination=np.zeros((c,c),dtype=bool)
    for i in range(c):
        for j in range(c):
            if i!=j and np.all(Rhi[i] < Rlo[j]-1e-12):domination[i,j]=True
    retained=[j for j in range(c) if not domination[:,j].any()]
    return {'status':'CERTIFIED_CAPACITY_CONDITIONAL_SYNTHETIC' if len(retained)<=capacity else 'ABSTAIN_CAPACITY_UNCERTAINTY',
            'certified':len(retained)<=capacity,'source':'SYNTHETIC_ONLY_CONDITIONAL_ASSUMPTIONS',
            'method':method,'independent_coloring_count':colors,'known_dependence_lag':witness.dependence_lag,
            'n_days':n,'n_color_min':min(map(len,group)),'n_candidates':c,'n_objectives':4,
            'n_thresholds_per_objective':grid_size,'family_functions':family_functions,
            'family_delta':delta,'width_of_threshold_grid':max_hinge_gap,'candidate_ids':list(candidate_ids) if candidate_ids else [f'ctrl_{i}' for i in range(c)],
            'estimated_original_pooled_risk':estimated.tolist(),'population_risk_lower':Rlo.tolist(),'population_risk_upper':Rhi.tolist(),
            'certified_dominance_pairs':[(int(i),int(j)) for i in range(c) for j in range(c) if domination[i,j]],
            'retained_ids':[int(v) for v in retained],'n_retained':len(retained),'capacity':capacity,
            'warning':'NOT approved for real OpenCEM: requires external proof of stationarity, finite m-dependence, pre-fixed bounded support, and candidate independence from evaluation days; not a deployment safety certificate.'}


def known_oracle_front(base:np.ndarray)->set[int]:
    """For additive identically distributed noise, marginal risk is shifted equally."""
    b=np.asarray(base,float)
    if b.ndim!=2 or b.shape[1]!=4:raise Refused('ORACLE_BASE_SHAPE')
    return {j for j in range(len(b)) if not any(i!=j and np.all(b[i]<=b[j]) and np.any(b[i]<b[j]) for i in range(len(b)))}
