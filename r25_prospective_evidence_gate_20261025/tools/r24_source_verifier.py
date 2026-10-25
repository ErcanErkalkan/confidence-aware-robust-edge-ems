"""R24: source-byte-attested historical TRAIN-only bridge from R23 to R19 B10.

Never interprets an observed archive/seed as a blind new TEST, external
pre-registration, stationarity proof or a finite-m-dependence witness.
"""
from __future__ import annotations
import csv, hashlib, io, json, math, sys, zipfile
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference_snapshot'))
from crmt_edge_ems.risk import risk_calibrated_score

SEEDS=(1001,1004,1005)
OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
ORIGINAL_BLOBS={'risk.py':'edee0d3361691535330419d0203757d0b3624638',
                'dominance.py':'c0fa644839407aaf1ac388a5082435a3a446be29',
                'archive.py':'bb644663febea3990ebeb23f47e403ab0c8070f3'}
SOURCE=ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip'
PROTOCOL=ROOT/'config/R19_PRIMARY_PROTOCOL_UNCHANGED.json'

class AuditBlocked(ValueError): pass

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def check_sources()->dict:
    out={}
    for name,expected in ORIGINAL_BLOBS.items():
        data=(ROOT/'reference_snapshot/crmt_edge_ems'/name).read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest()
        if actual!=expected:raise AuditBlocked('SOURCE_BLOB_MISMATCH '+name)
        out[name]=actual
    conf=json.loads(PROTOCOL.read_text(encoding='utf8'))
    if (conf.get('c'),conf.get('a'),conf.get('b'),conf.get('k'))!=(1,1,10,10) or conf.get('locked') is not False or conf.get('planned_seeds')!=list(range(2001,2031)):
        raise AuditBlocked('R19_PROTOCOL_CHANGED_OR_UNVERIFIED')
    return out

def parse(block:str)->tuple[str,str]:
    items=block.split(':')
    if len(items)!=3 or items[0]!='opencem' or items[1] not in ('inv1','inv2') or len(items[2])!=10 or items[2][:5]!='2025-':
        raise AuditBlocked('INVALID_DAY_SUBSYSTEM_KEY: '+block)
    try:
        from datetime import date
        date.fromisoformat(items[2])
    except ValueError:raise AuditBlocked('INVALID_CALENDAR_DAY')
    return items[2],items[1]

def _load_arm(z:zipfile.ZipFile,seed:int,arm:str)->dict:
    root=f'crmt_r16/raw/seed{seed}_C1_A1/{arm}/'
    summary=json.loads(z.read(root+'run_summary.json'))
    if summary.get('seed')!=seed or summary.get('condition_id')!=f'C1_{arm}_A1' or summary.get('stage')!='GATE3_FACTORIAL_TRAIN_ONLY':
        raise AuditBlocked('WRONG_SOURCE_IDENTITY')
    raw={}
    for f in ('candidate_metrics.csv','optimizer_front.csv','ledger.csv'):
        b=z.read(root+f)
        if sha(b)!=summary['files_sha256'][f]:raise AuditBlocked('RAW_SHA_MISMATCH: '+root+f)
        raw[f]=b
    tables={name:list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')))) for name,data in raw.items()}
    metrics=tables['candidate_metrics.csv'];ledger=tables['ledger.csv'];front=tables['optimizer_front.csv']
    if not(len(metrics)==len(ledger)==summary['train_budget_used']==12600):raise AuditBlocked('BUDGET_NOT_12600')
    losses={};by=defaultdict(dict)
    for row in metrics:
        if row.get('split')!='train':raise AuditBlocked('NOT_TRAIN')
        cid,bid=row['candidate_id'],row['block_id']
        parse(bid)
        pair=(cid,bid)
        if pair in losses:raise AuditBlocked('DUPLICATE_CONTROLLER_BLOCK')
        values=tuple(float(row[j]) for j in OBJ)
        if not all(math.isfinite(v) for v in values):raise AuditBlocked('NONFINITE_LOSS')
        losses[pair]=values
        by[cid][bid]=values
    pair_ledger={(r['candidate_id'],r['block_id']) for r in ledger}
    if pair_ledger!=set(losses) or len(pair_ledger)!=12600:raise AuditBlocked('LEDGER_SCIENCE_MISMATCH')
    ids={r['candidate_id'] for r in front}
    if len(ids)!=len(front) or len(front)!=summary['archive_count'] or not ids<=set(by):raise AuditBlocked('FRONT_ARCHIVE_IDENTITY')
    if len(by)!=256:raise AuditBlocked('NOT_256_CONTROLLERS')
    return dict(summary=summary,archive=ids,metrics=losses,by=by,sha={k:sha(v) for k,v in raw.items()},front=front)

def _rank_all(by:dict)->tuple[list[str],dict[str,list[float]]]:
    ids=sorted(by)
    matrix=[];score={}
    for cid in ids:
        samples=np.asarray([by[cid][bid] for bid in sorted(by[cid])],float)
        risk=[risk_calibrated_score(samples[:,j],q=.9,tail_weight=.5) for j in range(4)]
        score[cid]=risk;matrix.append(risk)
    m=np.asarray(matrix,float);v=np.ptp(m,axis=0)
    norm=np.divide(m-m.min(axis=0),v,out=np.zeros_like(m),where=v>1e-12)
    order=sorted(range(len(ids)),key=lambda i:(float(norm[i].max()),float(norm[i].sum()),ids[i]))
    return [ids[j] for j in order],score

def _summary_days(by:dict)->dict:
    days_by_candidate={}
    paired_complete={}
    all_candidate_blocks=[]
    for cid,observed in by.items():
        dd=defaultdict(set)
        for bid in observed:
            day,inv=parse(bid);dd[day].add(inv)
        days_by_candidate[cid]=set(dd)
        paired_complete[cid]={d for d,v in dd.items() if v=={'inv1','inv2'}}
        all_candidate_blocks.append(set(observed))
    complete_global=set.intersection(*(paired_complete.values()))
    partial_global=set.intersection(*(days_by_candidate.values()))
    blocks_global=set.intersection(*all_candidate_blocks)
    day_counts=sorted(len(v) for v in days_by_candidate.values())
    full_counts=sorted(len(v) for v in paired_complete.values())
    block_counts=sorted(len(v) for v in all_candidate_blocks)
    return {'min_days_candidate':day_counts[0],'median_days_candidate':float(np.median(day_counts)),'max_days_candidate':day_counts[-1],
            'min_two_inverter_days_candidate':full_counts[0],'median_two_inverter_days_candidate':float(np.median(full_counts)),
            'max_two_inverter_days_candidate':full_counts[-1],'min_blocks_candidate':block_counts[0],
            'median_blocks_candidate':float(np.median(block_counts)),'max_blocks_candidate':block_counts[-1],
            'global_common_days_any_inverter':len(partial_global),
            'global_complete_two_inverter_days_256':len(complete_global),
            'global_common_blocks_256':len(blocks_global),
            'all_complete_days_list':sorted(complete_global),
            'fully_aligned_30_day_audit_available_in_historical_records':len(complete_global)>=30}

def audit_seed(z:zipfile.ZipFile,seed:int)->dict:
    a=_load_arm(z,seed,'F0');b=_load_arm(z,seed,'F1')
    if a['metrics']!=b['metrics']:raise AuditBlocked('F0_F1_DIFFERENT_OBSERVATIONS')
    rank,scores=_rank_all(a['by'])
    picks={f:[cid for cid in rank if cid in d['archive']][:10] for f,d in (('F0',a),('F1',b))}
    if any(len(picks[f])!=10 for f in picks):raise AuditBlocked('B10_NATURAL_CAPACITY_UNAVAILABLE')
    days=_summary_days(a['by']);common=set(picks['F0'])&set(picks['F1'])
    support={x:{'seen_min':float(min(v[i] for v in a['metrics'].values())),
                'seen_max':float(max(v[i] for v in a['metrics'].values())),
                'support_prospectively_justified':False} for i,x in enumerate(OBJ)}
    return dict(seed=seed,stage='HISTORICAL_SEEN_TRAIN_DESCRIPTIVE_ONLY',
                source_raw_SHA_verified=True,paired_objectives_match=True,
                original_git_sha_F0=a['summary'].get('original_git_sha'),
                original_git_sha_F1=b['summary'].get('original_git_sha'),
                n_candidate_block_events=12600,n_candidates=256,
                natural_archive_F0=len(a['archive']),natural_archive_F1=len(b['archive']),
                F0_selected_B10=picks['F0'],F1_selected_B10=picks['F1'],
                B10_shared=len(common),B10_arm_specific=10-len(common),B10_identical=picks['F0']==picks['F1'],
                historical_K20_identical_as_previous_R9_receipt=True,
                observed_loss_extrema_not_prospective_bounds=support,
                original_csv_sha_F0=a['sha'],original_csv_sha_F1=b['sha'],
                **days,
                R23_real_certification='BLOCKED_NO_AUTHENTICATED_STATIONARITY_FINITE_M_FIXED_SUPPORT_AND_COMPLETE_PANEL',
                R19_future_TRAIN_AUDIT='NOT_EXECUTED_NO_EXTERNAL_PRELOCK',
                independent_blind_TEST='NO_GO')

def run(source:Path=SOURCE)->dict:
    snap=check_sources()
    rows=[]
    with zipfile.ZipFile(source) as z:
        for seed in SEEDS:rows.append(audit_seed(z,seed))
    return {'version':'R24-v1','date':'2026-10-25','data_scope':'EXPOSED_HISTORICAL_TRAIN_ONLY_NOT_NEW_TEST',
            'snapshot_original_blobs':snap,'r19_protocol_sha256':sha(PROTOCOL.read_bytes()),
            'rows':rows,'n_sources':len(rows),'n_new_seed_runs':0,
            'all_three_B10_different':all(not x['B10_identical'] for x in rows),
            'all_three_real_R23_blocked':all(x['R23_real_certification'].startswith('BLOCKED_') for x in rows),
            'claims':{'independent_p_value':None,'new_AUDIT_score':None,'field_safety':None,'real_R23_coverage_guarantee':None},
            'future_30_seed_plan':{'discovery_per_arm_per_seed':12600,'new_seeds':list(range(2001,2031)),
                  'r19_B':10,'audit_blocks_per_all_256':60,'audit_events_per_seed':256*60,
                  'audit_events_all_30_seeds':256*60*30,
                  'audit_common_two_inverter_days_if_daily_paired':30,
                  'discovery_events_per_arm_all_30_seeds':12600*30,
                  'audit_role':'FUTURE_SEPARATE_TRAIN_AUDIT_NOT_NEW_INDEPENDENT_TEST',
                  'equal_total_CPU':'NOT_ESTABLISHED'},
            'gates':{'real_R23_finite_m':'BLOCKED_NO_EXTERNAL_PROOF',
                     'loss_bounds':'BLOCKED_NOT_PRECOMMITTED',
                     'source_common_day_coverage':'BLOCKED_FOR_FULL_256',
                     'r19_B10_historical':'DESCRIPTIVE_ONLY_NOT_PREREGISTERED',
                     'R19_confirmation':'NOT_RUN',
                     'original_seed1001_F1_git_sha':'UNRECORDED_LOCAL_SHA',
                     'new_independent_TEST':'NO_GO',
                     'deployment':'NO_GO'}}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--out',type=Path,default=ROOT/'results/R24_REAL_TRAIN_BRIDGE.json');a=p.parse_args()
    data=run(a.source);a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
    for r in data['rows']:
        print(f"seed {r['seed']}: B10 overlap {r['B10_shared']}/10, common day-256 full={r['global_complete_two_inverter_days_256']} blocks={r['global_common_blocks_256']}, commit={r['original_git_sha_F1']}")
    return data

if __name__=='__main__':main()
