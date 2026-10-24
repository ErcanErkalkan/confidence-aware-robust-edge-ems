"""R21 exploratory calibration of UNMODIFIED CRMT confidence dominance.

Reference bootstrap is imported byte-for-byte from frozen Git blob snapshots.
Max-T simultaneous procedures are new *diagnostics*, not a validated fix.
No external TEST, no historical frozen artifacts modified.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference_snapshot'))
from crmt_edge_ems.dominance import confidence_risk_dominance, pareto_dominates
from crmt_edge_ems.archive import ConfidenceArchive
from crmt_edge_ems.risk import RiskConfig

SRC_SHA={'risk.py':'edee0d3361691535330419d0203757d0b3624638',
         'dominance.py':'c0fa644839407aaf1ac388a5082435a3a446be29',
         'archive.py':'bb644663febea3990ebeb23f47e403ab0c8070f3'}
METHODS=('point_pareto','legacy_reference_iid','maxT_shared_iid','maxT_shared_moving_block')
SCENARIOS=('clear_iid','near_iid','near_serial','flat_serial','near_serial_partial')
KAPPA=NormalDist().pdf(NormalDist().inv_cdf(.90))/.10

class CalibrationBlocked(ValueError): pass

def validate_source():
    for fname,expected in SRC_SHA.items():
        b=(ROOT/'reference_snapshot/crmt_edge_ems'/fname).read_bytes()
        got=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        if got!=expected:raise CalibrationBlocked(f'{fname}: reference source Git blob mismatch')

@dataclass
class Panel:
    values:np.ndarray # candidate x time x objective; nan means missing, never impute
    oracle:np.ndarray # candidates x objectives population Gaussian marginal risk
    scenario:str
    labels:tuple[str,...]
    rho:float


def risk(arr:np.ndarray)->np.ndarray:
    """... x block x 4; vectorized empirical mean+.5 top 10% tail mean."""
    arr=np.asarray(arr,float)
    if arr.ndim<2 or arr.shape[-1]!=4 or arr.shape[-2]<2 or not np.isfinite(arr).all():
        raise CalibrationBlocked('invalid complete score array')
    n=arr.shape[-2];k=max(1,math.ceil(.1*n))
    return arr.mean(axis=-2)+.5*np.partition(arr,n-k,axis=-2)[...,-k:,:].mean(axis=-2)


def generate(scenario:str,seed:int,n_blocks:int=48,n_candidates:int=5)->Panel:
    if scenario not in SCENARIOS or n_candidates!=5 or n_blocks<32:
        raise CalibrationBlocked('unrecognized scenario/candidate count or too few blocks')
    rng=np.random.default_rng(seed)
    near='near' in scenario or 'flat' in scenario
    gap=.09 if near else .70
    if scenario=='flat_serial':
        offsets=np.zeros((5,4))
    else:
        offsets=np.array([[0,1,1,1],[1,0,1,1],[.50,.50,.15,.50],
                          [.50+gap,.50+gap,.15+gap,.50+gap],
                          [gap,1+gap,1+gap,1+gap]],float)
    base=6+offsets
    rho=.87 if ('serial' in scenario) else 0.0
    def ar1():
        e=rng.standard_normal((n_blocks,4));y=np.empty_like(e)
        y[0]=e[0]
        for t in range(1,n_blocks):y[t]=rho*y[t-1]+np.sqrt(1-rho*rho)*e[t]
        return y
    common=ar1()
    independent=np.stack([ar1() for _ in range(5)])
    common_scale=.36; individual_scale=.28
    noise=common_scale*common[None,:,:]+individual_scale*independent
    values=base[:,None,:]+noise
    sd=math.sqrt(common_scale**2+individual_scale**2)
    oracle=1.5*base+.5*KAPPA*sd  # mean+.5*tail contains 1.5 * Gaussian location
    if scenario=='near_serial_partial':
        # Missing completely at random by candidate and day; destroys global alignment.
        mask=rng.random((5,n_blocks))<.28
        values[mask]=np.nan
    return Panel(values,oracle,scenario,tuple(f'ctrl_{i}' for i in range(5)),rho)


def oracle_front(scores:np.ndarray)->set[int]:
    if scores.ndim!=2 or scores.shape[1]!=4 or not np.isfinite(scores).all():
        raise CalibrationBlocked('invalid oracle')
    return {i for i in range(len(scores)) if not any(
        j!=i and pareto_dominates(scores[j],scores[i]) for j in range(len(scores)))}


def complete_subpanel(p:Panel,minimum:int=30)->np.ndarray:
    valid=np.isfinite(p.values).all(axis=(0,2))
    aligned=p.values[:,valid,:]
    if len(aligned.shape)!=3 or aligned.shape[1]<minimum:
        raise CalibrationBlocked(f'BLOCKED_GLOBAL_ALIGNMENT: {aligned.shape[1]}/{minimum} complete shared blocks')
    # Circular moving blocks are only meaningful for continuous time windows.
    if p.scenario=='near_serial_partial':
        raise CalibrationBlocked('BLOCKED_TIME_GAPS: full chronological series not observed')
    return aligned


def _max_t_decisions(p:Panel,n_boot:int,rng:np.random.Generator,block_len:int,mode:str):
    values=complete_subpanel(p)
    n_c,T,m=values.shape
    if mode=='maxT_shared_moving_block':
        if block_len<2 or block_len>=T or T//block_len<4:
            raise CalibrationBlocked('BLOCKED_BLOCK_LENGTH: infeasible circular moving block')
        block_count=math.ceil(T/block_len)
        starts=rng.integers(0,T,size=(n_boot,block_count))
        idx=(starts[:,:,None]+np.arange(block_len)[None,None,:])%T
        idx=idx.reshape(n_boot,-1)[:,:T]
    elif mode=='maxT_shared_iid':
        idx=rng.integers(0,T,size=(n_boot,T))
    else:raise CalibrationBlocked('unrecognized maxT method')
    if n_boot<200:raise CalibrationBlocked('bootstrap>=200 required')
    observed=risk(values)                           # [c,m]
    boot=risk(values[:,idx,:]).transpose(1,0,2)    # [boot,c,m]
    diff=observed[:,None,:]-observed[None,:,:]        # [c,c,m]
    bootdiff=boot[:,:,None,:]-boot[:,None,:,:]        # [boot,c,c,m]
    se=np.std(bootdiff,axis=0,ddof=1)
    mask=~np.eye(n_c,dtype=bool)
    # A nonzero standard error is required to support global studentization.
    if np.any(se[mask]<1e-12):raise CalibrationBlocked('BLOCKED_DEGENERATE_BOOTSTRAP_SE')
    z=(bootdiff-diff[None,:,:,:])/np.maximum(se[None,:,:,:],1e-12)
    max_stat=np.max(z[:,mask,:],axis=(1,2))
    critical=float(np.quantile(max_stat,.95))
    upper=diff+critical*se
    domination=(np.all(upper<=0,axis=2)&np.any(diff<0,axis=2))
    np.fill_diagonal(domination,False)
    actual=p.oracle[:,None,:]-p.oracle[None,:,:]
    under=np.any(upper[mask]<actual[mask]-1e-10)
    return domination,bool(under),critical


def _legacy(p:Panel,n_boot:int):
    n=len(p.labels);dom=np.zeros((n,n),bool);under=False
    for i in range(n):
        for j in range(n):
            if i==j:continue
            valid=np.isfinite(p.values[[i,j]]).all(axis=(0,2))
            av,bv=p.values[i,valid],p.values[j,valid]
            if len(av)<2:continue
            dec=confidence_risk_dominance(av,bv,risk=RiskConfig(),
                 alpha=.05,n_boot=n_boot,seed=ConfidenceArchive._pair_seed(p.labels[i],p.labels[j]))
            dom[i,j]=(dec.relation==-1)
            # The reference code uses independent opposite-direction RNG; its one-sided
            # upper bound is checked only for the requested i->j ordered family here.
            oracle_diff=p.oracle[i]-p.oracle[j]
            if np.any(dec.upper_diff_a_minus_b<oracle_diff-1e-10):under=True
    return dom,under,None


def _point(p:Panel):
    vals=[]
    for i in range(len(p.labels)):
        arr=p.values[i];arr=arr[np.isfinite(arr).all(axis=1)]
        vals.append(risk(arr))
    vals=np.stack(vals)
    n=len(vals);dom=np.zeros((n,n),bool)
    for i in range(n):
        for j in range(n):
            if i!=j:dom[i,j]=pareto_dominates(vals[i],vals[j])
    return dom,None,None


def assess(p:Panel,method:str,seed:int,n_boot:int=350,block_len:int=6,capacity:int=3)->dict[str,Any]:
    if method not in METHODS:raise CalibrationBlocked('unknown method')
    truth=oracle_front(p.oracle)
    if method=='point_pareto':dom,under,crit=_point(p)
    elif method=='legacy_reference_iid':dom,under,crit=_legacy(p,n_boot)
    else:
        try:dom,under,crit=_max_t_decisions(p,n_boot,np.random.default_rng(seed),block_len,method)
        except CalibrationBlocked as e:
            return dict(scenario=p.scenario,method=method,seed=seed,status=str(e).split(':')[0],
                        true_front_size=len(truth),false_removal=None,false_pair_declaration=None,
                        family_undercoverage=None,retained=None,overflow=None,critical_value=None)
    n=dom.shape[0]
    retained={j for j in range(n) if not np.any(dom[:,j])}
    false_pair=any(dom[i,j] and not pareto_dominates(p.oracle[i],p.oracle[j])
                   for i in range(n) for j in range(n) if i!=j)
    return dict(scenario=p.scenario,method=method,seed=seed,status='MEASURED',
                true_front_size=len(truth),false_removal=bool(truth-retained),
                false_pair_declaration=bool(false_pair),family_undercoverage=under,
                retained=len(retained),overflow=bool(len(retained)>capacity),
                critical_value=crit)


def wilson(k:int,n:int,z:float=1.959963984540054)->tuple[float,float]:
    if n<=0:raise CalibrationBlocked('Wilson needs n>0')
    p=k/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d
    width=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0.0,center-width),min(1.0,center+width)


def run_experiment(repetitions:int=80,n_boot:int=350,block_len:int=6,seed_base:int=20261024):
    validate_source()
    if repetitions<2 or n_boot<200:raise CalibrationBlocked('reps>=2 and boots>=200')
    rows=[]
    for case_i,scenario in enumerate(SCENARIOS):
        for r in range(repetitions):
            seed=seed_base+10000*case_i+r
            p=generate(scenario,seed)
            for m in METHODS:
                rows.append(assess(p,m,seed=seed+187,n_boot=n_boot,block_len=block_len))
    summary=[]
    for s in SCENARIOS:
        for m in METHODS:
            rr=[row for row in rows if row['scenario']==s and row['method']==m]
            measured=[row for row in rr if row['status']=='MEASURED']
            item={'scenario':s,'method':m,'n_repetitions':repetitions,'n_measured':len(measured),
                  'n_blocked':len(rr)-len(measured),'status':'MEASURED' if measured else 'ALL_BLOCKED'}
            for metric in ('false_removal','false_pair_declaration','overflow','family_undercoverage'):
                if metric=='family_undercoverage' and m=='point_pareto':
                    item.update({metric+'_rate':None,metric+'_count':None,metric+'_wilson_upper95':None});continue
                if not measured:
                    item.update({metric+'_rate':None,metric+'_count':None,metric+'_wilson_upper95':None});continue
                k=sum(int(r[metric]) for r in measured)
                item.update({metric+'_rate':k/len(measured),metric+'_count':k,
                             metric+'_wilson_upper95':wilson(k,len(measured))[1]})
            item['mean_retained']=float(np.mean([x['retained'] for x in measured])) if measured else None
            item['true_front_size']=rr[0]['true_front_size']
            summary.append(item)
    return {'metadata':{'date':'2026-10-24','run_class':'SYNTHETIC_CALIBRATION_EXPLORATORY_NOT_REAL_TEST',
                        'reference_github_blobs':SRC_SHA,'repetitions':repetitions,'n_boot':n_boot,
                        'block_len':block_len,'n_candidates':5,'n_objectives':4,'n_time_blocks':48,
                        'archive_capacity':3,'caveats':['oracle is stationary parametric Gaussian marginal risk, not truth for any OpenCEM site',
                        'no method has a finite-sample archive FWER guarantee; maxT uses approximate bootstrap',
                        'temporal circular blocks require stationary chronology; missingness blocks maxT',
                        'Wilson bounds describe Monte-Carlo scenario variability only, not deployment risk',
                        'the original F1 code is used unmodified; maxT methods are new diagnostics']},
            'rows':rows,'summary':summary}


def main():
    p=argparse.ArgumentParser();p.add_argument('--repetitions',type=int,default=80)
    p.add_argument('--n-boot',type=int,default=350);p.add_argument('--block-len',type=int,default=6)
    p.add_argument('--output-dir',type=Path,default=ROOT/'results')
    x=p.parse_args();r=run_experiment(x.repetitions,x.n_boot,x.block_len)
    x.output_dir.mkdir(parents=True,exist_ok=True)
    (x.output_dir/'R21_EXPERIMENT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    for name,rows in [('R21_PER_REPETITION.csv',r['rows']),('R21_SUMMARY.csv',r['summary'])]:
        with (x.output_dir/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for row in r['summary']:
        print(row['scenario'],row['method'],row['status'],'false',row['false_removal_rate'],'overflow',row['overflow_rate'],'undercoverage',row['family_undercoverage_rate'])

if __name__=='__main__':main()
