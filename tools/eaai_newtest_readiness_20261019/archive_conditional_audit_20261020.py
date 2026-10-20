#!/usr/bin/env python3
"""Offline seed1001 F archive diagnostic. Historical, selected VAL subset only.

This computation reconstructs risk-Pareto membership on the 256 TRAIN profiles
and compares it with the *stored* F1 terminal archive and the *selected* 54
historical VAL candidates. This NEVER labels the 54-candidate reference a full
256-candidate oracle and never performs any new simulator evaluation.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

OBJECTIVES = ('cap_violation_pct_total', 'lfp_cycle_loss_pct', 'ramp95_kw_per_min', 'flip_per_day')
EXPECTED_SOURCE = '3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1'
EXPECTED_COMMIT = 'be5756321617087ca421a639d60a99513f29d889'
EXPECTED_VAL_LOCK = 'GATE3-V2-DEDUPE-VAL-SEED1001-EXPLORATORY-v1'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()


def require(ok, msg):
    if not ok: raise ValueError(msg)


def risk_vectors(frame, q=.9, tail=.5):
    require(0 <= tail and .5<=q<1, 'Bad risk parameters')
    require(set(['candidate_id','block_id','split',*OBJECTIVES]).issubset(frame.columns), 'Missing metric columns')
    out={}
    for cid,g in frame.groupby('candidate_id', sort=True):
        require(g.block_id.is_unique, 'Repeated candidate-block record: '+str(cid))
        a=g.loc[:,OBJECTIVES].to_numpy(dtype=float)
        require(len(a)>=2 and np.isfinite(a).all(), 'Missing/nonfinite objective: '+str(cid))
        k=max(1,int(math.ceil((1-q)*len(a))))
        val=a.mean(axis=0)+tail*np.partition(a,len(a)-k,axis=0)[-k:].mean(axis=0)
        out[cid]=val
    return out


def nondominated(scores, atol=1e-12):
    ids=sorted(scores)
    x=np.array([scores[i] for i in ids], dtype=float)
    require(len(ids)>=2 and x.ndim==2 and x.shape[1]==4 and np.isfinite(x).all(), 'Bad risk matrix')
    result=set()
    for idx,v in enumerate(x):
        # Mirrors CRMT pareto_dominates: all <= with atol and any strictly < with atol
        d=np.all(x<=v+atol,axis=1) & np.any(x<v-atol,axis=1)
        d[idx]=False
        if not d.any(): result.add(ids[idx])
    return result


def diagnostic(train, stored_f1, val):
    require(train.candidate_id.nunique()==256 and len(train)==12600, 'Expected seed1001 C1A1 TRAIN size')
    require(len(val)==54*118 and val.candidate_id.nunique()==54 and val.block_id.nunique()==118, 'Expected historical VAL 54x118')
    require(set(val.candidate_id).issubset(set(train.candidate_id)), 'Untrained VALIDATION candidate')
    require(set(train.split)=={'train'} and set(val.split)=={'validation'}, 'Split contamination')
    require(all(g.block_id.nunique()==118 and len(g)==118 for _,g in val.groupby('candidate_id')), 'Missing/duplicate VAL blocks')
    require(stored_f1.candidate_id.nunique()==len(stored_f1) and len(stored_f1)==236, 'Unexpected frozen F1 archive size')
    require(set(stored_f1.candidate_id).issubset(set(train.candidate_id)), 'Unknown F1 archive candidate')
    tr=risk_vectors(train)
    vv=risk_vectors(val)
    f0=nondominated(tr)
    f1=set(stored_f1.candidate_id)
    ref=nondominated(vv)
    require(len(f0)==18,'TRAIN F0 candidate count changed')
    # Verify that stored confidence front uses the same 256-candidate risk scoring rules.
    f1risk=stored_f1.set_index('candidate_id').loc[sorted(f1),list(OBJECTIVES)].to_numpy(dtype=float)
    pred=np.array([tr[c] for c in sorted(f1)])
    require(np.allclose(f1risk,pred,rtol=0,atol=1e-10), 'Stored F1 risk-vector mismatch')
    sampled=set(vv)
    rows=[]
    for label,s in [('F0_RECONSTRUCTED_TRAIN_RISK_PARETO',f0),('F1_STORED_CONFIDENCE_ARCHIVE',f1)]:
        inside=s&sampled
        rows.append(dict(archive=label, archive_size_full256=len(s),selected_val_candidates=54,
                         retained_in_selected54=len(inside), val_nondominated_within54=len(ref),
                         reference_front_retained=len(inside&ref),
                         reference_front_not_retained=len(ref-inside),
                         reference_dominated_retained=len(inside-ref),
                         reference_dominated_not_retained=len((sampled-ref)-inside),
                         conditional_recall=len(inside&ref)/len(ref),
                         conditional_precision=len(inside&ref)/len(inside) if inside else float('nan')))
    membership=[]
    for cid in sorted(sampled):
        membership.append(dict(candidate_id=cid,in_256_train_reconstructed_f0=int(cid in f0),
                               in_256_train_stored_f1=int(cid in f1),
                               nondominated_within_selected54_historical_val=int(cid in ref),
                               val_common_blocks=118))
    meta=dict(stage='SEED1001_SELECTED54_HISTORICAL_VAL_ARCHIVE_CONDITIONAL_DIAGNOSTIC',
              outcome='DESCRIPTIVE_ONLY_NO_INDEPENDENT_F_PROOF',
              n_train_candidates=256,n_f0_risk_pareto_train=len(f0),n_stored_f1_confidence_train=len(f1),
              n_val_selected=54,n_val_common_blocks=118,n_val_nondominated_within_selected54=len(ref),
              n_val_candidate_blocks=6372,
              f0_f1_common_train_members=len(f0&f1),f0_only=len(f0-f1),f1_only=len(f1-f0),
              caution=('VALIDATION 54 were selected using prior TRAIN decisions/K20. Only those 54 were rescored; '
                       'the full 256-candidate VALIDATION reference is unavailable; archive precision/recall '
                       'are conditional-on-selection, biased/retrospective, NOT confidence reliability proof. '
                       'F0 re-derived from F1 candidate metrics, not loaded from the stored F0 run. '
                       'No new blinded TEST run and no field improvement claim.'),
              library_provenance='Seed1001 historical C1_F1_A1 run_summary plus previous seed1001 VALIDATION lock')
    return pd.DataFrame(rows),pd.DataFrame(membership),meta


def execute(args):
    out=Path(args.output)
    require(not out.exists(), 'Existing output folder — no overwrite')
    summary=json.loads(Path(args.train_summary).read_text(encoding='utf-8'))
    val_lock=json.loads(Path(args.val_lock).read_text(encoding='utf-8'))
    require(summary['stage']=='GATE3_FACTORIAL_TRAIN_ONLY' and summary['seed']==1001 and summary['condition_id']=='C1_F1_A1', 'Wrong TRAIN context')
    require(summary['archive_mode']=='confidence' and summary['allocation_mode']=='adaptive' and summary['risk_tail_weight']==.5 and summary['risk_q']==.9, 'Wrong TRAIN risk')
    require(summary['canonical_manifest_sha256']==EXPECTED_SOURCE, 'Wrong TRAIN source')
    require(val_lock['protocol']==EXPECTED_VAL_LOCK and val_lock['seed']==1001, 'Wrong VAL stage')
    require(val_lock['source_manifest_sha256']==EXPECTED_SOURCE and val_lock['source_commit']==EXPECTED_COMMIT, 'VAL source mismatch')
    paths={'candidate_metrics.csv':args.train_metrics,'optimizer_front.csv':args.f1_front}
    for k,p in paths.items():require(sha(p)==summary['files_sha256'][k],k+' immutable TRAIN SHA256 mismatch')
    require(sha(args.val_metrics)==val_lock['files_sha256']['UNIQUE_VALIDATION_BLOCK_METRICS.csv'], 'VAL metrics SHA256 mismatch')
    require(len(set(summary['files_sha256']))>=2,'Invalid manifest')
    train=pd.read_csv(args.train_metrics);f1=pd.read_csv(args.f1_front);val=pd.read_csv(args.val_metrics)
    scores,members,meta=diagnostic(train,f1,val)
    out.mkdir(parents=True,exist_ok=False)
    for name,frame in [('CONDITIONAL_F0_F1_REFERENCE_SUMMARY.csv',scores),('SELECTED54_REFERENCE_MEMBERSHIP.csv',members)]:
        frame.to_csv(out/name,index=False,float_format='%.17g',lineterminator='\n')
    meta['input_sha256']={Path(p).name:sha(p) for p in [args.train_summary,args.train_metrics,args.f1_front,args.val_lock,args.val_metrics]}
    meta['outputs_sha256']={name:sha(out/name) for name in ['CONDITIONAL_F0_F1_REFERENCE_SUMMARY.csv','SELECTED54_REFERENCE_MEMBERSHIP.csv']}
    (out/'CONDITIONAL_AUDIT_LOCK.json').write_text(json.dumps(meta,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(meta,sort_keys=True,indent=2))
    print('CONDITIONAL_HISTORICAL_VAL_DIAGNOSTIC_PASS; NO NEW TEST')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['train_summary','train_metrics','f1_front','val_lock','val_metrics','output']:
        p.add_argument('--'+key.replace('_','-'),required=True)
    a=p.parse_args()
    try: execute(a)
    except Exception as e:
        print('CONDITIONAL_F_ARCHIVE_AUDIT_BLOCKED:',str(e))
        raise SystemExit(2)

if __name__=='__main__':main()
