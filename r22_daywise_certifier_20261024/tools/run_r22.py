"""R22 reproducible bounded synthetic experiments + read-only R16 day audit."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,sys,zipfile
from pathlib import Path
from collections import defaultdict,Counter
from statistics import NormalDist
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from day_certifier import certifier,check_originals,prove_coverage_bound,CertificateBlocked,empirical_risk

# No mode below is a new independent real TEST.
EXPERIMENTS=(('iid_easy_200',200),('iid_easy_4000',4000),('iid_near_200',200),
             ('iid_near_4000',4000),('serial_easy_200',200),('serial_easy_4000',4000),
             ('missing_iid_200',200))

BASE=np.array([[.75,2.50,2.40,2.30],
               [2.40,.75,2.30,2.40],
               [2.35,2.40,.75,2.35],
               [3.80,3.80,3.80,3.80],
               [3.80,3.80,3.80,3.80]],float)
A=.08;B=.04;INV=.02
# For sum of two independent uniforms U[-A,A]+U[-B,B], with A>=B
# q90 is in the upper triangular tail when P(X>A-B)=B/(2A)>=.1.
# q90=A+B-sqrt(8*A*B*.1); E[X|X>=q90]=A+B-2/3*sqrt(8*A*B*.1).
TAIL_MEAN=A+B-(2./3.)*math.sqrt(8*A*B*.10)


def make_panel(mode:str,n_days:int,seed:int):
    rng=np.random.default_rng(seed)
    base=BASE.copy()
    if 'near' in mode:
        base[3]=base[2]+.12
        base[4]=base[2]+.20
    if 'serial' in mode:
        rho=.95;x=np.empty(n_days);x[0]=rng.standard_normal()
        for t in range(1,n_days):x[t]=rho*x[t-1]+math.sqrt(1-rho*rho)*rng.standard_normal()
        common=np.tanh(x)
    else:common=rng.uniform(-1,1,n_days)
    indiv=rng.uniform(-1,1,size=(5,n_days,4))
    y=base[:,None,:]+A*common[None,:,None]+B*indiv
    # Paired simultaneous measurements; strongly dependent within day.
    a=np.empty((5,n_days,2,4),float)
    a[:,:,0,:]=y+INV
    a[:,:,1,:]=y-INV
    if mode.startswith('missing'):
        a[4,-2,1,0]=np.nan
    true_risk=1.5*base+.5*TAIL_MEAN
    return a,true_risk


def front(r:np.ndarray):
    keep=set()
    for j in range(len(r)):
        dominated=any(i!=j and np.all(r[i]<=r[j]+1e-12) and np.any(r[i]<r[j]-1e-12) for i in range(len(r)))
        if not dominated:keep.add(j)
    return keep


def point_archive(a:np.ndarray):
    if not np.isfinite(a).all():return None
    return front(empirical_risk(a.mean(axis=2)))


def one_run(name:str,n:int,seed:int)->dict:
    a,truth=make_panel(name,n,seed)
    oracle=front(truth)
    res={'scenario':name,'n_days':n,'seed':seed,'oracle_front_size':len(oracle),
         'point_false_removal':None,'point_retained_n':None}
    p=point_archive(a)
    if p is not None:
        res['point_false_removal']=bool(oracle-p)
        res['point_retained_n']=len(p)
    try:
        allowed='SYNTHETIC_GENERATOR_KNOWN_IID_DAYS' if name.startswith(('iid_','missing_iid')) else 'KNOWN_SERIAL_NOT_IID'
        cert=certifier(a,independence_evidence=allowed)
        res['status']=cert['status']
        if res['status']=='BLOCKED_IID_DAY_EVIDENCE_UNVERIFIED':
            res.update({'false_removal':None,'false_pair':None,'band_undercoverage':None,'retained_n':None,'decision':False})
            return res
        retrieved=set(cert['retained_indices'])
        res.update({'retained_n':len(retrieved),'false_removal':bool(oracle-retrieved),
                    'false_pair':any(not(np.all(truth[i]<=truth[j]+1e-12) and np.any(truth[i]<truth[j]-1e-12)) for i,j in cert['certified_domination_pairs']),
                    'band_undercoverage':bool(np.any(truth <np.asarray(cert['lower_risk'])-1e-10)|np.any(truth>np.asarray(cert['upper_risk'])+1e-10)),
                    'decision':res['status']=='CERTIFIED_SELECTION_CONDITIONAL_IID'})
        return res
    except CertificateBlocked as exc:
        res.update({'status':str(exc).split(':')[0], 'retained_n':None,'false_removal':None,
                    'false_pair':None,'band_undercoverage':None,'decision':False})
        return res


def wilson_upper(k,n,z=1.959963984540054):
    if n<=0:return None
    p=k/n;den=1+z*z/n
    return min(1.0,(p+z*z/(2*n)+z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den)


def experiment(repetitions=60,seed_base=20261024):
    if type(repetitions)!=int or repetitions<2:raise ValueError('at least two repetitions')
    check_originals()
    results=[]
    for si,(name,n) in enumerate(EXPERIMENTS):
        for i in range(repetitions):results.append(one_run(name,n,seed_base+si*10000+i))
    summary=[]
    for name,n in EXPERIMENTS:
        rows=[r for r in results if r['scenario']==name]
        measured=[r for r in rows if r['false_removal'] is not None]
        col={'scenario':name,'n_days':n,'n_repetitions':repetitions,
             'n_measured':len(measured),'n_blocked':repetitions-len(measured),
             'n_certified_decisions':sum(r['decision'] for r in rows),
             'decision_rate':sum(r['decision'] for r in rows)/repetitions,
             'status':Counter(r['status'] for r in rows).most_common(1)[0][0]}
        for met in ('false_removal','false_pair','band_undercoverage'):
            count=sum(bool(x[met]) for x in measured)
            col[met+'_count']=count if measured else None
            col[met+'_rate']=count/len(measured) if measured else None
            col[met+'_wilson_upper']=wilson_upper(count,len(measured)) if measured else None
        col['mean_retained']=float(np.mean([r['retained_n'] for r in measured])) if measured else None
        col['point_false_removal_rate']=sum(bool(r['point_false_removal']) for r in rows if r['point_false_removal'] is not None)/sum(r['point_false_removal'] is not None for r in rows) if any(r['point_false_removal'] is not None for r in rows) else None
        summary.append(col)
    return {'metadata':{'stage':'R22_NEW_BOUNDED_DKW_DAYWISE_SYNTHETIC_DIAGNOSTIC',
            'data':'SYNTHETIC_ONLY_NOT_NEW_OPENCEM_TEST','repetitions':repetitions,
            'n_candidates':5,'n_objectives':4,'n_inverters_per_day':2,
            'family_alpha':.05,'support':[0,4],
            'assumption':'Across-day IID required for theoretical bound, within-day two inverter arbitrarily dependent',
            'real_scope':'No field independence attested, estimator changes to day means, do not pool two inv as 2n independent',
            'source_blobs_checked':True},'summary':summary,'records':results}


def historical_day_audit(archive=ROOT/'reference_inputs_R16.zip',seeds=(1001,1004,1005)):
    """Real TRAIN grouping only: no certified dominance or new TEST claims."""
    check_originals()
    records=[]
    with zipfile.ZipFile(archive) as z:
        for seed in seeds:
            by_arm={}
            for f in ('F0','F1'):
                stem=f'crmt_r16/raw/seed{seed}_C1_A1/{f}/'
                summary=json.loads(z.read(stem+'run_summary.json'))
                raw=z.read(stem+'candidate_metrics.csv')
                if hashlib.sha256(raw).hexdigest()!=summary['files_sha256']['candidate_metrics.csv']:
                    raise CertificateBlocked('BLOCKED_REAL_TRAIN_SHA: '+stem)
                rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
                if len(rows)!=12600:raise CertificateBlocked('BLOCKED_RECORD_COUNT')
                fields={}
                days_by_candidate=defaultdict(lambda:defaultdict(set))
                for r in rows:
                    if r['split']!='train':raise CertificateBlocked('BLOCKED_SPLIT_EXPOSURE')
                    parts=r['block_id'].split(':')
                    if len(parts)!=3 or not parts[1].startswith('inv'):raise CertificateBlocked('BLOCKED_CLOCK_FORMAT')
                    ci,bid=r['candidate_id'],r['block_id']
                    k=(ci,bid)
                    if k in fields:raise CertificateBlocked('BLOCKED_DUPLICATED_BLOCK')
                    values=tuple(float(r[obj]) for obj in ('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day'))
                    if not all(math.isfinite(v) for v in values):raise CertificateBlocked('BLOCKED_NONFINITE_REAL')
                    fields[k]=values
                    days_by_candidate[ci][parts[2]].add(parts[1])
                by_arm[f]=(fields,days_by_candidate)
            if by_arm['F0'][0]!=by_arm['F1'][0]:raise CertificateBlocked('BLOCKED_F0F1_SCIENCE_MISMATCH')
            day_registry=by_arm['F0'][1]
            dcnt=[len(days) for days in day_registry.values()]
            complete=[sum(len(invs)==2 for invs in days.values()) for days in day_registry.values()]
            records.append({'seed':seed,'train_records':12600,'candidate_count':len(day_registry),
                            'min_days_per_candidate':min(dcnt),'median_days_per_candidate':float(np.median(dcnt)),
                            'max_days_per_candidate':max(dcnt),
                            'min_two_inverter_days':min(complete),'max_two_inverter_days':max(complete),
                            'all_candidate_full_common_day_panel':False,
                            'true_bound_catalog_sha256':None,'iid_day_assumption_supported':False,
                            'status':'BLOCKED_REAL_TRAIN_IID_AND_SUPPORT_UNVERIFIED_NOT_NEW_TEST'})
    return {'source':'HISTORICALLY_EXPOSED_OPEN_CEM_TRAIN_ONLY', 'rows':records}


def save(out:Path, repetitions=60):
    out.mkdir(parents=True,exist_ok=True)
    e=experiment(repetitions)
    (out/'R22_EXPERIMENT.json').write_text(json.dumps(e,indent=2,allow_nan=False)+'\n')
    h=historical_day_audit()
    (out/'R22_REAL_TRAIN_DAY_AUDIT.json').write_text(json.dumps(h,indent=2)+'\n')
    for name,rows in [('R22_SUMMARY.csv',e['summary']),('R22_PER_REPETITION.csv',e['records'])]:
        with (out/name).open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return e,h

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repetitions',type=int,default=60);p.add_argument('--output-dir',type=Path,default=ROOT/'results');args=p.parse_args()
    e,h=save(args.output_dir,args.repetitions)
    for x in e['summary']:print(x['scenario'],x['n_measured'],x['decision_rate'],x['false_removal_rate'],x['band_undercoverage_rate'])
    print(h)
