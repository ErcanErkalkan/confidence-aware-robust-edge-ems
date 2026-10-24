"""CRMT R19: TRAIN-only two-phase prospective archive-fidelity design.

NOT a preregistration, independent TEST, or physical-safety certificate.
Selection is sealed on DISCOVERY records; AUDIT records are never read in select mode.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from collections import Counter
from typing import Any
import numpy as np

class Blocked(ValueError):
    pass

OBJECTIVES = (
    'cap_violation_pct_total', 'lfp_cycle_loss_pct',
    'ramp95_kw_per_min', 'flip_per_day',
)


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True,
                       separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _require(flag: bool, message: str) -> None:
    if not flag:
        raise Blocked(message)


def _id_list(seq: Any, name: str, *, allow_empty: bool = False) -> list[str]:
    _require(isinstance(seq, list), f'{name} must be list')
    _require((bool(seq) or allow_empty) and all(isinstance(x, str) and x and x == x.strip() for x in seq),
             f'{name} must contain nonempty trimmed strings')
    _require(len(seq) == len(set(seq)), f'{name}: duplicate IDs')
    return seq


def _vec(raw: Any, where: str) -> np.ndarray:
    _require(isinstance(raw, list) and len(raw) == 4, f'{where}: four objectives required')
    _require(all(type(v) in (int, float) and math.isfinite(v) for v in raw), f'{where}: invalid objective')
    return np.asarray(raw, dtype=float)


def config_validate(c: dict) -> None:
    _require(isinstance(c, dict), 'config must be object')
    _require(c.get('status') == 'INTERNAL_DESIGN_FREEZE_DRAFT_NOT_PREREGISTERED', 'config: draft status must not be falsified')
    _require(c.get('scope') == 'TRAIN_ONLY_EXPLORATORY_ARCHIVE_FIDELITY', 'TRAIN-only only')
    _require(c.get('primary_contrast') == 'F1_MINUS_F0_MISS_RATE', 'unrecognized primary contrast')
    _require(c.get('c') == 1 and c.get('a') == 1, 'primary contrast must fix C1/A1')
    _require(c.get('b') == c.get('k') == 10, 'primary B=K=10 (no backfill)')
    _require(c.get('n_prospective_seeds') == 30, '30 planned independent seeds')
    _require(c.get('planned_seeds') == list(range(2001,2031)), 'prospective seed manifest changed')
    _require(c.get('minimum_audit_blocks') == 8, 'minimum AUDIT block validator changed')
    _require(c.get('recommended_audit_blocks_for_new_runs') >= 40, 'AUDIT panel too small for planning')
    _require(type(c.get('minimum_mean_improvement')) in (int,float) and 0 < c['minimum_mean_improvement'] < 1,'practical importance threshold invalid')
    _require(c.get('optim_evals_per_arm') == 12600, 'expected budget 12600')
    _require(c.get('q') == 0.9 and c.get('tail_weight') == 0.5, 'risk functional changed')
    _require(c.get('primary_alpha_two_sided') == 0.05, 'alpha changed')
    _require(c.get('objectives') == list(OBJECTIVES), 'objectives/order changed')
    _require(c.get('audit_role') == 'HELD_OUT_WITHIN_HISTORICAL_TRAIN_NOT_NEW_TEST', 'audit exposure claim invalid')
    _require(c.get('locked') is False, 'draft may not claim external preregistration')


def _ranking(scores: dict[str, list[float]], ids: list[str]) -> list[str]:
    _require(set(scores) == set(ids), 'discovery scores must cover exact candidate pool')
    array = np.stack([_vec(scores[x], f'discovery:{x}') for x in ids])
    low, span = array.min(axis=0), np.ptp(array, axis=0)
    norm = np.divide(array - low, span, out=np.zeros_like(array), where=span > 1e-12)
    ranks = {cid: (float(np.max(norm[i])), float(np.sum(norm[i])), cid) for i,cid in enumerate(ids)}
    return sorted(ids, key=lambda cid: ranks[cid])


def _ledger(ledger: Any, name: str, candidates: set[str], discovery: set[str], expected: int) -> set[tuple[str,str]]:
    _require(isinstance(ledger, list) and len(ledger) == expected, f'{name}: expected {expected} events')
    obs=[]
    for i,e in enumerate(ledger):
        _require(isinstance(e, list) and len(e)==2, f'{name}[{i}]: expected [candidate,block]')
        cid,bid=e
        _require(isinstance(cid,str) and cid in candidates and isinstance(bid,str) and bid in discovery,
                 f'{name}[{i}]: illegal candidate or AUDIT block leakage')
        obs.append((cid,bid))
    _require(len(set(obs))==expected, f'{name}: duplicate candidate-block events')
    return set(obs)


def _block_registry(entries: Any) -> tuple[list[str],list[str]]:
    _require(isinstance(entries,list) and entries, 'block registry missing')
    seen=set(); splits={'DISCOVERY':[],'AUDIT':[]}; groups={'DISCOVERY':set(),'AUDIT':set()}
    for row in entries:
        _require(isinstance(row,dict) and set(row)=={'block_id','group_id','split'}, 'block record needs block_id/group_id/split')
        bid,gid,s=row['block_id'],row['group_id'],row['split']
        _require(isinstance(bid,str) and bool(bid) and bid not in seen, 'block IDs duplicate or empty')
        _require(isinstance(gid,str) and bool(gid) and s in splits, 'block group/split invalid')
        seen.add(bid); splits[s].append(bid);groups[s].add(gid)
    _require(splits['DISCOVERY'] and splits['AUDIT'], 'discovery and audit required')
    _require(not groups['DISCOVERY']&groups['AUDIT'], 'temporal/site group crosses discovery and AUDIT')
    return splits['DISCOVERY'],splits['AUDIT']


def selection_lock(config:dict,input_data:dict) -> dict:
    config_validate(config)
    _require(isinstance(input_data,dict), 'selection input must be object')
    _require(set(input_data)=={'seed','run_git_sha','source_manifest_sha256','candidate_ids','blocks','archives','discovery_objectives','evaluation_pairs'},
             'selection input schema mismatch; AUDIT observations prohibited')
    seed=input_data['seed']
    _require(type(seed) is int and seed in config['planned_seeds'], 'seed absent from frozen planned seed set')
    run_sha=input_data['run_git_sha']
    manifest_sha=input_data['source_manifest_sha256']
    _require(isinstance(run_sha,str) and len(run_sha)==40 and all(c in '0123456789abcdef' for c in run_sha), 'missing original 40-char execution SHA')
    _require(isinstance(manifest_sha,str) and len(manifest_sha)==64 and all(c in '0123456789abcdef' for c in manifest_sha), 'invalid source manifest SHA')
    ids=_id_list(input_data['candidate_ids'],'candidates')
    _require(len(ids)==256, 'exact 256 prospective candidates required')
    discovery,audit=_block_registry(input_data['blocks'])
    _require(len(audit)>=config['minimum_audit_blocks'],'too few common AUDIT blocks')
    archives=input_data['archives']
    _require(isinstance(archives,dict) and set(archives)=={'F0','F1'}, 'both archives required')
    picks={}
    for f in ('F0','F1'):
        members=_id_list(archives[f],f'archive {f}')
        _require(set(members)<=set(ids),f'archive {f}: unknown candidate')
        _require(len(members)>=config['b'],f'archive {f}: no-backfill capacity B=10 unavailable')
    evaluations=input_data['evaluation_pairs']
    _require(isinstance(evaluations,dict) and set(evaluations)=={'F0','F1'}, 'both evaluation ledgers required')
    l0=_ledger(evaluations['F0'],'F0',set(ids),set(discovery),config['optim_evals_per_arm'])
    l1=_ledger(evaluations['F1'],'F1',set(ids),set(discovery),config['optim_evals_per_arm'])
    _require(l0==l1, 'not paired / different TRAIN candidate-block budgets')
    raw=input_data['discovery_objectives']
    _require(isinstance(raw,dict) and set(raw)==set(ids), 'discovery raw metrics must cover exact candidate pool')
    by_candidate={cid:[] for cid in ids}
    for cid,bid in l0: by_candidate[cid].append(bid)
    discovery_scores={}
    for cid in ids:
        observed=raw[cid]
        _require(isinstance(observed,dict) and set(observed)==set(by_candidate[cid]),
                 f'discovery metrics do not match actual evaluation ledger for {cid}')
        _require(len(observed)>=2,f'discovery has fewer than 2 blocks for {cid}')
        matrix=np.stack([_vec(observed[bid],f'discovery {cid}/{bid}') for bid in sorted(observed)])
        discovery_scores[cid]=(np.mean(matrix,axis=0)+
              config['tail_weight']*np.mean(np.partition(matrix,len(matrix)-max(1,math.ceil((1-config['q'])*len(matrix))),axis=0)[-max(1,math.ceil((1-config['q'])*len(matrix))):],axis=0)).tolist()
    ranked=_ranking(discovery_scores,ids)
    for f in ('F0','F1'):
        members=set(archives[f]); picks[f]=[cid for cid in ranked if cid in members][:10]
        _require(len(picks[f])==10,f'archive {f}: incorrect B after recomputed ranking')
    base={'stage':'SELECTION_LOCK_READY_FOR_IMMUTABLE_EXTERNAL_COMMIT','scope':config['scope'],
          'seed':seed,'protocol_sha256':canonical_hash(config),'source_manifest_sha256':manifest_sha,
          'run_git_sha':run_sha,'selection_input_sha256':canonical_hash(input_data),
          'discovery_risk_vectors_sha256':canonical_hash(discovery_scores),
          'candidate_ids':ids,'audit_block_ids':audit,'discovery_block_count':len(discovery),
          'audit_block_count':len(audit),'common_discovery_ledger_sha256':canonical_hash(sorted([list(x) for x in l0])),
          'B':10,'F0_selected_ids':picks['F0'],'F1_selected_ids':picks['F1'],
          'F0_natural_count':len(archives['F0']),'F1_natural_count':len(archives['F1']),
          'audit_outcomes_seen':False,
          'warning':'Commit this lock with external immutable timestamp BEFORE viewing audit outcomes; a JSON flag cannot prove temporal ordering.'}
    base['selection_lock_sha256']=canonical_hash(base)
    return base


def topk_cvar(data:np.ndarray,q:float,weight:float)->np.ndarray:
    _require(data.ndim==3 and data.shape[2]==4 and data.shape[1]>1,'AUDIT matrix shape invalid')
    n=data.shape[1]; k=max(1,math.ceil((1.0-q)*n))
    return np.mean(data,axis=1)+weight*np.mean(np.partition(data,n-k,axis=1)[:,n-k:,:],axis=1)


def nondominated_ids(scores:dict[str,np.ndarray],tol=1e-12)->set[str]:
    ids=list(scores); matrix=np.stack([scores[cid] for cid in ids])
    keep=set()
    for i,cid in enumerate(ids):
        # Pareto: other no-worse in all and strictly better in at least one.
        dominated=np.any(np.all(matrix <= matrix[i] + tol,axis=1) &
                         np.any(matrix < matrix[i]-tol,axis=1))
        if not dominated:keep.add(cid)
    return keep


def score_audit(config:dict,lock:dict,audit_data:dict) -> dict:
    config_validate(config)
    _require(isinstance(lock,dict) and isinstance(audit_data,dict),'lock and AUDIT need objects')
    sealed=dict(lock); seal=sealed.pop('selection_lock_sha256',None)
    _require(isinstance(seal,str) and seal==canonical_hash(sealed),'lock digest mismatch; fail closed')
    _require(lock['protocol_sha256']==canonical_hash(config),'different protocol, stop')
    _require(lock['stage']=='SELECTION_LOCK_READY_FOR_IMMUTABLE_EXTERNAL_COMMIT','bad selection stage')
    _require(set(audit_data)=={'seed','candidate_block_objectives','independent_lock_receipt'},'AUDIT data schema mismatch')
    _require(audit_data['seed']==lock['seed'],'seed mismatch')
    receipt=audit_data['independent_lock_receipt']
    _require(isinstance(receipt,dict) and set(receipt)=={'selection_lock_sha256','external_commit_url','committed_before_audit'},'external receipt absent')
    _require(receipt['selection_lock_sha256']==seal and receipt['committed_before_audit'] is True,'not externally locked before AUDIT')
    _require(isinstance(receipt['external_commit_url'],str) and receipt['external_commit_url'].startswith('https://'),'immutable external receipt URL absent')
    raw=audit_data['candidate_block_objectives']
    ids=lock['candidate_ids']; blocks=lock['audit_block_ids']
    _require(isinstance(raw,dict) and set(raw)==set(ids), 'AUDIT must cover every one of 256 candidates')
    arr=np.empty((len(ids),len(blocks),4),float)
    for i,cid in enumerate(ids):
        rec=raw[cid]
        _require(isinstance(rec,dict) and set(rec)==set(blocks),f'AUDIT incomplete/extra block for {cid}')
        for j,bid in enumerate(blocks):arr[i,j]=_vec(rec[bid],f'AUDIT {cid}:{bid}')
    risks=topk_cvar(arr,config['q'],config['tail_weight'])
    reference=nondominated_ids({cid:risks[i] for i,cid in enumerate(ids)})
    _require(bool(reference),'AUDIT reference Pareto front empty')
    missed={f:len(reference-set(lock[f'{f}_selected_ids']))/len(reference) for f in ('F0','F1')}
    retention={f:len(set(lock[f'{f}_selected_ids'])-reference)/config['b'] for f in ('F0','F1')}
    return {'stage':'EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST',
            'seed':lock['seed'],'selection_lock_sha256':seal,'audit_input_sha256':canonical_hash(audit_data),
            'reference_nondominated_n':len(reference),'reference_ids_sha256':canonical_hash(sorted(reference)),
            'F0_miss_rate':missed['F0'],'F1_miss_rate':missed['F1'],
            'delta_F1_minus_F0':missed['F1']-missed['F0'],
            'F0_false_retained_fraction':retention['F0'],'F1_false_retained_fraction':retention['F1'],
            'same_k':lock['F0_selected_ids']==lock['F1_selected_ids'],
            'disclaimer':'AUDIT reference is finite empirical TRAIN Pareto, not population truth or independent TEST.'}


def paired_two_sided_signflip(diffs:list[float], *, seed:int=20261024, draws:int=99999)->float:
    d=np.asarray(diffs,dtype=float)
    _require(d.ndim==1 and len(d)>0 and np.isfinite(d).all(),'nonfinite or empty paired differences')
    if not np.any(d):return 1.0
    obs=abs(float(np.mean(d))); n=len(d)
    if n<=16:
        n_all=2**n
        stats=np.empty(n_all)
        for i in range(n_all):
            signs=np.where(np.array([(i>>j)&1 for j in range(n)])==1,1.0,-1.0)
            stats[i]=abs(float(np.mean(d*signs)))
        return float(np.mean(stats >= obs-1e-12))
    _require(draws>=999,'for n>16 require >=999 MC draws')
    rng=np.random.default_rng(seed)
    exceed=0; batch=2000
    for start in range(0,draws,batch):
        k=min(batch,draws-start)
        s=rng.choice((-1.0,1.0),size=(k,n))
        exceed+=int(np.sum(np.abs(np.mean(s*d,axis=1))>=obs-1e-12))
    return float((exceed+1)/(draws+1))


def summarise(config:dict,results:list[dict]) -> dict:
    config_validate(config)
    _require(isinstance(results,list) and len(results)>0,'nonempty seed results required')
    seeds=[]; diffs=[]
    for r in results:
        _require(isinstance(r,dict) and r.get('stage')=='EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST','invalid seed evidence')
        _require(type(r.get('seed')) is int and type(r.get('delta_F1_minus_F0')) in (int,float),'invalid seed/delta')
        seeds.append(r['seed']);diffs.append(r['delta_F1_minus_F0'])
    _require(len(set(seeds))==len(seeds),'duplicated seed: pseudo-replication')
    _require(set(seeds).issubset(set(config['planned_seeds'])), 'seed not in prospective fixed manifest')
    diffs=np.array(diffs,float);_require(np.isfinite(diffs).all(),'nonfinite differences')
    p=paired_two_sided_signflip(diffs.tolist())
    if len(diffs)>=2:
        rng=np.random.default_rng(20261024)
        idx=rng.integers(0,len(diffs),size=(12000,len(diffs)))
        lo,hi=np.quantile(np.mean(diffs[idx],axis=1),[.025,.975])
    else:lo=hi=None
    enough=len(diffs)==config['n_prospective_seeds']
    success=bool(enough and p<.05 and hi is not None and hi<0 and float(np.mean(diffs))<=-config['minimum_mean_improvement'])
    return {'status':'DESCRIPTIVE_TRAIN_ONLY_NOT_NEW_TEST',
      'n_unique_seeds':len(diffs),'n_target':config['n_prospective_seeds'],'target_met':enough,
      'mean_delta_F1_minus_F0':float(np.mean(diffs)),'p_two_sided_signflip':p,
      'paired_seed_bootstrap_ci95':[float(lo),float(hi)] if lo is not None else None,
      'minimum_mean_improvement':config['minimum_mean_improvement'],
      'primary_claim_supported_for_exploratory_audit':success,
      'warning':'Needs independent pre-exposure preregistration + genuinely new blinded TEST for confirmatory field claim; train seeds are not independent sites.'}


def _read(p:str)->Any: return json.loads(Path(p).read_text(encoding='utf-8'))

def _write_exclusive(p:str,value:Any):
    path=Path(p);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=['select','audit','summary'])
    ap.add_argument('--config',required=True)
    ap.add_argument('--input',required=True)
    ap.add_argument('--lock',help='Required for audit')
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    conf=_read(args.config)
    if args.command=='select':r=selection_lock(conf,_read(args.input))
    elif args.command=='audit':
        if not args.lock:ap.error('--lock required for audit')
        r=score_audit(conf,_read(args.lock),_read(args.input))
    else:r=summarise(conf,_read(args.input))
    _write_exclusive(args.output,r)
    print(r.get('stage',r.get('status')),r.get('selection_lock_sha256',''))

if __name__=='__main__':main()
