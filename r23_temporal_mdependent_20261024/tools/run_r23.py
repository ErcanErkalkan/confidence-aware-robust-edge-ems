"""Reproducible R23 synthetic serial-dependence calibration; not new TEST."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,sys,zipfile
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from r23_certifier import certify,SyntheticDesign,known_oracle_front,Refused
BASE=np.asarray([[.75,2.5,2.4,2.3],[2.4,.75,2.3,2.4],[2.35,2.4,.75,2.35],[3.8,3.8,3.8,3.8],[3.8,3.8,3.8,3.8]],float)
SCENARIOS=(('iid_easy_600',0,600,'iid'),('iid_easy_2000',0,2000,'iid'),('iid_easy_4000',0,4000,'iid'),('ma2_easy_2000',2,2000,'finite_MA'),('ma2_easy_4000',2,4000,'finite_MA'),('ma2_near_4000',2,4000,'finite_MA'),('ar1_unverified_400',None,400,'AR1'),('missing_600',0,600,'missing'))
METHODS=('hoeffding','empirical_bernstein')

def panel(scenario:str,n:int,seed:int,m:int|None):
    rng=np.random.default_rng(seed)
    base=BASE.copy()
    if 'near' in scenario:
        base[3]=base[2]+.12;base[4]=base[2]+.2
    lag=max(0,m or 0)
    if m is None:
        phi=.92;e=rng.uniform(-1,1,(n,))
        common=np.empty(n);common[0]=e[0]
        for t in range(1,n):common[t]=phi*common[t-1]+(1-phi)*e[t]
        noise_id=rng.uniform(-1,1,(5,n,4))
        witness=None
    else:
        innov=rng.uniform(-1,1,n+lag)
        common=np.mean(np.stack([innov[k:k+n] for k in range(lag+1)],axis=1),axis=1)
        e=rng.uniform(-1,1,(5,n+lag,4))
        noise_id=np.mean(np.stack([e[:,k:k+n,:] for k in range(lag+1)],axis=2),axis=2)
        witness=SyntheticDesign('iid' if m==0 else 'finite_MA',m,hashlib.sha256(b'R23_FIXED_GENERATOR_V1').hexdigest(),True)
    y=base[:,None,:]+.08*common[None,:,None]+.04*noise_id
    a=np.stack((y+.02,y-.02),axis=2)
    if scenario.startswith('missing'):a[4,-1,1,0]=np.nan
    return a,base,witness

def trial(scenario:str,m:int|None,n:int,kind:str,seed:int)->dict:
    a,base,w=panel(scenario,n,seed,m)
    true_front=known_oracle_front(base)
    if scenario.startswith('missing'):
        try:certify(a,w,method=kind)
        except Refused as e:
            return dict(scenario=scenario,n_days=n,method=kind,seed=seed,status=str(e),blocked=True,
                        false_removal=None,capacity_met=None,any_band_violation=None,retained=None,ref_size=len(true_front),mean_band_width=None)
        raise AssertionError('Missing data accepted')
    rr=certify(a,w,method=kind)
    blocked=rr['status'].startswith('BLOCKED_')
    if blocked:return dict(scenario=scenario,n_days=n,method=kind,seed=seed,status=rr['status'],blocked=True,
                           false_removal=None,capacity_met=None,any_band_violation=None,retained=None,ref_size=len(true_front),mean_band_width=None)
    retained=set(rr['retained_ids'])
    # The oracle Pareto set is known EXACTLY from common additive marginals.
    false_removed=bool(true_front-retained)
    # Population risk common offset is not needed for false removal; optional
    # full coverage is not claimed from a simulated oracle approximation.
    l=np.asarray(rr['population_risk_lower']);u=np.asarray(rr['population_risk_upper'])
    return dict(scenario=scenario,n_days=n,method=kind,seed=seed,status=rr['status'],blocked=False,
                false_removal=false_removed,capacity_met=rr['certified'],any_band_violation=None,
                retained=len(retained),ref_size=len(true_front),mean_band_width=float(np.mean(u-l)))

def run(repetitions=30,seed_base=20261024):
    if type(repetitions)!=int or repetitions<2:raise ValueError('repetitions >= 2')
    results=[]
    for i,(scenario,m,n,typ) in enumerate(SCENARIOS):
        for rep in range(repetitions):
            seed=seed_base+i*10000+rep
            for kind in METHODS:results.append(trial(scenario,m,n,kind,seed))
    summary=[]
    for scenario,m,n,typ in SCENARIOS:
        for kind in METHODS:
            batch=[r for r in results if r['scenario']==scenario and r['method']==kind]
            ok=[r for r in batch if not r['blocked']]
            summary.append(dict(scenario=scenario,model=typ,n_days=n,method=kind,repetitions=repetitions,
                n_measured=len(ok),n_blocked=len(batch)-len(ok),false_removal_events=sum(bool(z['false_removal']) for z in ok) if ok else None,
                false_removal_rate=(sum(bool(z['false_removal']) for z in ok)/len(ok)) if ok else None,
                capacity_decisions=sum(bool(z['capacity_met']) for z in ok) if ok else None,
                capacity_decision_rate=sum(bool(z['capacity_met']) for z in ok)/len(batch),
                mean_retained=float(np.mean([z['retained'] for z in ok])) if ok else None,
                mean_risk_band_width=float(np.mean([z['mean_band_width'] for z in ok])) if ok else None))
    return {'metadata':{'date':'2026-10-24','run_type':'R23_SYNTHETIC_M_DEPENDENT_STUDY_ONLY_NOT_NEW_TEST',
            'mathematical_limit':'stationary bounded strictly m-dependent day-vectors; IID within each mod-(m+1) class',
            'n_methods':2,'n_scenarios':len(SCENARIOS),'repetitions':repetitions,'n_candidate':5,'n_objectives':4,
            'pooled_original_estimand':True,'unknown_AR1_m':'BLOCKED','missing_values':'BLOCKED',
            'family_alpha':.05,'grid_size':31,'capacity':3,'r19_B10_unchanged':True,
            'oracle_front':'known exactly by common-shape additive marginal noise; no finite MC oracle needed'},
           'records':results,'summary':summary}

def real_train_gate(zip_path:Path):
    """Read-only source-verified real TRAIN gate; no m-dependent certification."""
    OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
    rows=[]
    with zipfile.ZipFile(zip_path) as z:
        for seed in (1001,1004,1005):
            pairs={}
            for f in ('F0','F1'):
                prefix=f'crmt_r16/raw/seed{seed}_C1_A1/{f}/'
                summ=json.loads(z.read(prefix+'run_summary.json'))
                b=z.read(prefix+'candidate_metrics.csv')
                if hashlib.sha256(b).hexdigest()!=summ['files_sha256']['candidate_metrics.csv']:
                    raise Refused('REAL_SOURCE_SHA_MISMATCH')
                parsed=list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))))
                if len(parsed)!=12600:raise Refused('REAL_SOURCE_COUNT')
                loss={};days=defaultdict(set)
                for r in parsed:
                    key=(r['candidate_id'],r['block_id'])
                    if key in loss:raise Refused('DUPLICATE_CONTROLLER_BLOCK')
                    loss[key]=tuple(r[v] for v in OBJ)
                    days[r['candidate_id']].add(r['block_id'].split(':')[-1])
                pairs[f]=(loss,days)
            if pairs['F0'][0]!=pairs['F1'][0]:raise Refused('REAL_SCIENCE_MISMATCH')
            dd=pairs['F0'][1]
            rows.append({'seed':seed,'n_controller_blocks':len(pairs['F0'][0]),'candidate_n':len(dd),
                 'day_count_min':min(map(len,dd.values())),'day_count_max':max(map(len,dd.values())),
                 'F0_F1_same_source_science':True,'fixed_pooled_objective_support_documented':False,
                 'verified_finite_dependence_lag_m':None,'verified_stationarity':False,
                 'candidate_day_complete_across_256':False,
                 'decision':'BLOCKED_REAL_OPEN_CEM_NOT_CERTIFIABLE',
                 'data':'HISTORICALLY_SEEN_TRAIN_NOT_NEW_TEST'})
    return {'source':'R16_ARCHIVED_ORIGINAL_SHA_VERIFIED_SEEN_TRAIN_ONLY','rows':rows}

def save(folder:Path,repetitions=30,source_zip:Path|None=None):
    folder.mkdir(parents=True,exist_ok=True)
    x=run(repetitions)
    (folder/'R23_EXPERIMENT.json').write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
    for name,rows in [('R23_SUMMARY.csv',x['summary']),('R23_PER_REPETITION.csv',x['records'])]:
        with (folder/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if source_zip:
        y=real_train_gate(source_zip)
        (folder/'R23_REAL_TRAIN_GATE.json').write_text(json.dumps(y,indent=2)+'\n')
    return x

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repetitions',type=int,default=30)
    p.add_argument('--out',type=Path,default=ROOT/'results');p.add_argument('--source',type=Path,default=ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip')
    a=p.parse_args();s=save(a.out,a.repetitions,a.source)
    for r in s['summary']:print(r)
