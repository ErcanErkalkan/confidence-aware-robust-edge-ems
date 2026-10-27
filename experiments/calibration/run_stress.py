"""Deterministic synthetic calibration study; never operational TEST evidence."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
import time
import math
import numpy as np
from scipy.stats import norm
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from crmt_edge_ems.calibration import calibrate,ground_truth_metrics,CalibrationResult
from crmt_edge_ems.contracts import ContractError,digest,canonical,integer
from crmt_edge_ems.profiling import peak_rss_bytes

SCENARIOS=('clear_iid','near_iid','flat_null_iid','near_ar1_095','clear_ar1_095',
    'missing_observation','unequal_support','missing_chronological_block','archive_overflow')
METHODS=('legacy_F1_unchanged','maxT_iid_v1','maxT_circular_block_v1','bonferroni_iid_v1','abstain_v1')

def fixture(scenario,rng):
    c=12 if scenario=='archive_overflow' else 6;n=64
    mu=np.zeros((c,4))
    if scenario not in {'flat_null_iid','archive_overflow'}:
        mu[:3]=np.asarray([[-2,0,1,2],[0,-2,2,1],[1,2,-2,0]])
        mu[3:]=np.arange(3,c)[:,None]
        if scenario.startswith('near'): mu*=.025
    rho=.95 if 'ar1' in scenario else 0
    noise=rng.normal(size=(c,n,4))
    for t in range(1,n): noise[:,t,:]=rho*noise[:,t-1,:]+math.sqrt(1-rho*rho)*noise[:,t,:]
    x=mu[:,None,:]+noise
    truth=1.5*mu+0.5*norm.pdf(norm.ppf(.9))/.1
    chronology=np.arange(n)
    if scenario=='missing_observation': x[0,3,0]=np.nan
    if scenario=='unequal_support': x[1,5,:]=np.nan
    if scenario=='missing_chronological_block': x=np.delete(x,4,axis=1);chronology=np.delete(chronology,4)
    return x,truth,chronology

def legacy(x,*,seed,n_boot,capacity,chronology):
    from crmt_edge_ems.risk import RiskConfig
    from crmt_edge_ems.dominance import confidence_risk_dominance
    if not np.isfinite(x).all() or not np.all(np.diff(chronology)==1): raise ContractError('strict wrapper rejects unsupported legacy input')
    c=len(x);upper=np.full((c,c,4),np.inf);decl=np.zeros((c,c),dtype=bool)
    for a in range(c):
        for b in range(c):
            if a==b: continue
            r=confidence_risk_dominance(x[a],x[b],risk=RiskConfig(),n_boot=n_boot,seed=seed+a*c+b)
            upper[a,b]=r.upper_diff_a_minus_b;decl[a,b]=r.relation==-1
    retained=~decl.any(axis=0)
    return CalibrationResult('legacy_F1_unchanged',upper,decl,retained,int(retained.sum())>capacity,True,x.shape[1])

def wilson_upper(count,n,*,z=1.6448536269514722):
    if not n:return None
    p=count/n
    return (p+z*z/(2*n)+z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)

def run(out,*,repetitions=80,n_boot=399,seed=20261027):
    integer(repetitions,'repetitions',1);integer(n_boot,'n_boot',200)
    out=Path(out)
    if out.exists() and any(out.iterdir()): raise ContractError('nonempty output directory: preserve previous experiment')
    out.mkdir(parents=True,exist_ok=True)
    config={'implementation_id':'CAL-STRESS-v1','status':'SYNTHETIC_EXPLORATORY_NOT_PREREGISTERED',
        'seed':seed,'repetitions':repetitions,'n_boot':n_boot,'scenarios':SCENARIOS,'methods':METHODS,
        'capacity':10,'block_length':8,'nominal_alpha':.05,'family':'All ordered candidate pairs and four minimization objectives',
        'draft_acceptance':'One-sided 95% Wilson upper bound on family-undercoverage <= .05 in EVERY required valid scenario; input rejection scenarios must block. No external preregistration exists.',
        'estimand':'Population Gaussian mean + 0.5 upper 10% tail mean. Empirical ceil-tail estimator is preserved in all methods.',
        'limits':'AR1 has infinite dependence horizon; L=8 is a predeclared stress setting, not a validated block choice. Gaussian losses are mathematical fixtures, not physical nonnegative EMS losses.'}
    (out/'config.json').write_bytes(canonical(config))  # written BEFORE outcomes
    rows=[]
    for si,scenario in enumerate(SCENARIOS):
        for rep in range(repetitions):
            rng=np.random.default_rng(np.random.SeedSequence([seed,si,rep]))
            x,truth,chronology=fixture(scenario,rng)
            for method in METHODS:
                start=time.perf_counter();cpu=time.process_time()
                row={'scenario':scenario,'repetition':rep,'method':method,'status':'MEASURED',
                    'family_undercoverage':None,'false_pair_declaration':None,'false_removal':None,'archive_overflow':None,'archive_size':None,'true_front_size':None}
                try:
                    if method=='legacy_F1_unchanged': r=legacy(x,seed=seed+rep,n_boot=n_boot,capacity=10,chronology=chronology)
                    else:
                        r=calibrate(x,method=method,n_boot=n_boot,seed=seed+rep,capacity=10,
                            chronology=chronology,block_length=8 if method=='maxT_circular_block_v1' else 1)
                    row.update(ground_truth_metrics(r,truth));row['tail_resolution_sufficient']=r.bootstrap_tail_resolution_sufficient
                except ContractError as exc: row.update(status='BLOCKED_INVALID_SUPPORT',reason=str(exc))
                row.update(runtime_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu,
                    peak_process_rss_bytes=peak_rss_bytes(),memory_scope='PROCESS_LIFETIME_HIGH_WATER_MARK')
                rows.append(row)
        print(f'{scenario}: {repetitions} repetitions x {len(METHODS)} methods',flush=True)
    summary=[]
    for scenario in SCENARIOS:
        for method in METHODS:
            group=[r for r in rows if r['scenario']==scenario and r['method']==method];measured=[r for r in group if r['status']=='MEASURED'];n=len(measured)
            s={'scenario':scenario,'method':method,'n_attempted':len(group),'n_measured':n,'n_blocked':len(group)-n,
                'average_archive_size':float(np.mean([r['archive_size'] for r in measured])) if n else None,
                'runtime_seconds':sum(r['runtime_seconds'] for r in group),'peak_process_rss_bytes':max(r['peak_process_rss_bytes'] for r in group)}
            for metric in ('family_undercoverage','false_pair_declaration','false_removal','archive_overflow'):
                count=sum(r[metric] for r in measured);s[metric+'_count']=count;s[metric+'_rate']=count/n if n else None
                s[metric+'_wilson_upper_one_sided95']=wilson_upper(count,n)
            s['draft_coverage_criterion_met']=bool(n and s['family_undercoverage_wilson_upper_one_sided95']<=.05)
            summary.append(s)
    for name,data in [('per_repetition.json',rows),('summary.json',summary)]: (out/name).write_bytes(canonical(data))
    for name,data in [('per_repetition.csv',rows),('summary.csv',summary)]:
        columns=sorted(set().union(*(r.keys() for r in data)))
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(data)
    status={'config_sha256':digest(config),'synthetic_only':True,'new_operational_evaluations':0,
        'scientifically_validated_archive_95_guarantee':False,'output_rows':len(rows),
        'reason':'Finite synthetic sensitivity does not establish assumptions or archive-wide validity on real data; abstention has no elimination utility',
        'method_all_valid_scenarios_meet_draft_criterion':{m:all(r['draft_coverage_criterion_met'] for r in summary if r['method']==m and r['n_measured']) for m in METHODS}}
    (out/'status.json').write_bytes(canonical(status))
    return status

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--repetitions',type=int,default=80);p.add_argument('--n-boot',type=int,default=399)
    a=p.parse_args();print(json.dumps(run(a.out,repetitions=a.repetitions,n_boot=a.n_boot),indent=2))