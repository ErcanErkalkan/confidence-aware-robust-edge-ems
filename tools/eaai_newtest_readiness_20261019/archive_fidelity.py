#!/usr/bin/env python3
"""Read-only diagnostic comparison of F0/F1 archived membership to a common reference.

Reference is based only on fixed COMMON rescoring and is NOT a blind oracle
unless separately established as one before looking at archive membership.
"""
import argparse,csv,json,math
from pathlib import Path

OBJECTIVES=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
class FidelityError(Exception): pass

def require(x,msg):
    if not x: raise FidelityError(msg)

def read_ids(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        require(r.fieldnames and 'candidate_id' in r.fieldnames,'archive missing candidate_id')
        ids=[x['candidate_id'].strip() for x in r]
    require(ids and len(ids)==len(set(ids)) and all(ids),'Duplicate/empty archive ID')
    return set(ids)

def reference(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        require(r.fieldnames and {'candidate_id',*OBJECTIVES}.issubset(r.fieldnames), 'Missing reference columns')
        rows=list(r)
    m={}
    for row in rows:
        cid=row['candidate_id'].strip()
        require(cid and cid not in m,'Duplicate reference candidate')
        try: values=tuple(float(row[k]) for k in OBJECTIVES)
        except (TypeError,ValueError) as e:raise FidelityError('Invalid objective') from e
        require(all(math.isfinite(v) for v in values), 'Nonfinite reference objective')
        m[cid]=values
    require(len(m)>=2,'Need at least two candidates')
    nondom=set()
    for k,x in m.items():
        if not any(all(y[i]<=x[i] for i in range(4)) and any(y[i]<x[i] for i in range(4))
                   for j,y in m.items() if j!=k):
            nondom.add(k)
    return m,nondom

def compute(ref, f0, f1):
    candidates,truth=ref
    pool=set(candidates)
    require(f0<=pool and f1<=pool,'Archive includes candidate without common reference scores')
    def row(name,archive):
        tp=len(archive & truth);fp=len(archive-truth);fn=len(truth-archive)
        return {'name':name,'true_retained':tp,'false_retained':fp,'false_eliminated':fn,
                'reference_nondominated':len(truth),'archive_size':len(archive),
                'precision':tp/len(archive) if archive else None,
                'recall':tp/len(truth) if truth else None,
                'false_elimination_rate':fn/len(truth) if truth else None,
                'false_retention_rate':fp/(len(pool)-len(truth)) if len(pool)>len(truth) else None}
    return {'status':'COMMON_REFERENCE_ARCHIVE_DIAGNOSTIC_NOT_BLIND_TEST',
            'candidate_count':len(pool),'F0':row('F0',f0),'F1':row('F1',f1),
            'only_F0':sorted(f0-f1),'only_F1':sorted(f1-f0),
            'limitation':'Common reference must be fixed, uniform-budget, fully scored, provenance checked; no inferential confidence claims from TRAIN-only reference.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',required=True)
    p.add_argument('--f0',required=True)
    p.add_argument('--f1',required=True)
    a=p.parse_args()
    try: out=compute(reference(a.reference),read_ids(a.f0),read_ids(a.f1))
    except (FidelityError,ValueError,OSError,KeyError,TypeError) as ex:
        print('ARCHIVE_FIDELITY_BLOCKED:',str(ex));raise SystemExit(2)
    print(json.dumps(out,indent=2,sort_keys=True))
    print('ARCHIVE_FIDELITY_DIAGNOSTIC_ONLY; NO TEST')
if __name__=='__main__': main()
