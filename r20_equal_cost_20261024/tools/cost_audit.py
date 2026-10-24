"""R20: immutable-source historical TRAIN cost-accounting audit.

This audit compares accounting and observability. It does NOT reconstruct
historical wall-clock time, change archived policies, or supply a new TEST.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

BUDGET=12600
OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')

class AuditBlocked(ValueError): pass

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _rows(b: bytes):
    return list(csv.DictReader(io.StringIO(b.decode('utf-8-sig'),newline='')))

def audit_arm(z: zipfile.ZipFile, stem: str):
    """Checks three immutable raw files against that run's immutable summary."""
    p=f'crmt_r16/raw/{stem}/'
    summary=json.loads(z.read(p+'run_summary.json'))
    raw={k:z.read(p+k) for k in ('candidate_metrics.csv','ledger.csv','optimizer_front.csv')}
    for name, contents in raw.items():
        expected=summary['files_sha256'][name]
        if sha(contents)!=expected:
            raise AuditBlocked(f'{stem}/{name}: SHA mismatch')
    rows=_rows(raw['candidate_metrics.csv']); ledger=_rows(raw['ledger.csv']); front=_rows(raw['optimizer_front.csv'])
    if len(rows)!=BUDGET or len(ledger)!=BUDGET:
        raise AuditBlocked(f'{stem}: expected 12600 exact rows')
    pairs={(r['candidate_id'],r['block_id']) for r in rows}
    lpairs={(r['candidate_id'],r['block_id']) for r in ledger}
    if len(pairs)!=BUDGET or pairs!=lpairs:
        raise AuditBlocked(f'{stem}: duplicate/missing ledger pairs')
    if int(summary['train_budget_used'])!=BUDGET or len(front)!=int(summary['archive_count']):
        raise AuditBlocked(f'{stem}: budget/archive conflict')
    fids=[r['candidate_id'] for r in front]
    if len(set(fids))!=len(fids) or not set(fids).issubset({r['candidate_id'] for r in rows}):
        raise AuditBlocked(f'{stem}: invalid front IDs')
    block_obj={}
    total_ticks=0; sum_mean_cpu_ms_times_ticks=0.0; sum_mean_cpu_ms=0.0; max_reported_cpu_ms=0.0
    for r in rows:
        if r.get('split')!='train': raise AuditBlocked(f'{stem}: non TRAIN row')
        vec=tuple(float(r[x]) for x in OBJ)
        if not all(math.isfinite(x) for x in vec):raise AuditBlocked(f'{stem}: nonfinite science loss')
        block_obj[(r['candidate_id'],r['block_id'])]=vec
        ticks=int(r['n_ticks']);avg=float(r['mean_cpu_ms']);mx=float(r['max_cpu_ms'])
        if ticks<=0 or not all(math.isfinite(x) and x>=0 for x in (avg,mx)):
            raise AuditBlocked(f'{stem}: CPU proxy metrics invalid')
        total_ticks+=ticks
        sum_mean_cpu_ms_times_ticks+=avg*ticks
        sum_mean_cpu_ms+=avg
        max_reported_cpu_ms=max(max_reported_cpu_ms,mx)
    return {
        'key':stem,'summary_sha256':sha(z.read(p+'run_summary.json')),
        'execution_sha_recorded':summary.get('original_git_sha'),
        'n_candidate_blocks':len(rows),'n_candidates':len({r['candidate_id'] for r in rows}),
        'archive_native_count':len(front),'final_B10_feasible':len(front)>=10,
        'total_ticks':total_ticks,
        'simulator_tick_cpu_proxy_ms':round(sum_mean_cpu_ms_times_ticks,5),
        'mean_reported_tick_cpu_ms':round(sum_mean_cpu_ms/len(rows),8),
        'peak_reported_tick_cpu_ms':round(max_reported_cpu_ms,8),
        'raw_sha256':{k:sha(v) for k,v in raw.items()},
    },pairs,block_obj

def audit_pairs(zip_path:Path, *, only_c1a1=True):
    outcome=[]
    with zipfile.ZipFile(zip_path) as z:
        dirs=sorted({f.split('/')[2] for f in z.namelist() if f.startswith('crmt_r16/raw/') and f.endswith('/F0/run_summary.json')})
        if only_c1a1:dirs=[x for x in dirs if x.endswith('_C1_A1')]
        if not dirs:raise AuditBlocked('no paired historical data in ZIP')
        for pair in dirs:
            a,pa,va=audit_arm(z,pair+'/F0');b,pb,vb=audit_arm(z,pair+'/F1')
            if pa!=pb or va!=vb:
                raise AuditBlocked(f'{pair}: ledger or scientific objectives mismatch')
            diff=b['simulator_tick_cpu_proxy_ms']-a['simulator_tick_cpu_proxy_ms']
            outcome.append({
              'pair':pair,'source':'R16_original_raw_files_SHA_verified','scientific_objectives_match':True,
              'candidate_block_ledger_match':True,'budget_F0':a['n_candidate_blocks'],'budget_F1':b['n_candidate_blocks'],
              'native_archive_F0':a['archive_native_count'],'native_archive_F1':b['archive_native_count'],
              'B10_export_F0':10 if a['final_B10_feasible'] else None,
              'B10_export_F1':10 if b['final_B10_feasible'] else None,
              'sim_tick_cpu_proxy_F0_ms':a['simulator_tick_cpu_proxy_ms'],
              'sim_tick_cpu_proxy_F1_ms':b['simulator_tick_cpu_proxy_ms'],
              'sim_tick_cpu_proxy_difference_F1_minus_F0_ms':round(diff,5),
              'total_ticks_F0':a['total_ticks'],'total_ticks_F1':b['total_ticks'],
              'mean_tick_cpu_F0_ms':a['mean_reported_tick_cpu_ms'],
              'mean_tick_cpu_F1_ms':b['mean_reported_tick_cpu_ms'],
              'native_archive_capacity_equal':a['archive_native_count']==b['archive_native_count'],
              'cpu_archive_historical':'NOT_RECORDED',
              'wall_clock_archive_historical':'NOT_RECORDED',
              'bootstrap_work_historical':'NOT_RECORDED',
              'source_git_sha_F0':a['execution_sha_recorded'],
              'source_git_sha_F1':b['execution_sha_recorded'],
            })
    return outcome

def parse_cost_record(row:dict)->dict:
    """Fail-closed accounting for a *new* instrumented prospective run.

    Timing must use a real monotonic CPU/wall profiler and witnessed hardware;
    no missing measurement can be imputed from the simulator proxy.
    """
    expected={'seed','arm','run_sha','input_ledger_sha256','n_controller_blocks',
      'sim_cpu_ns','optimizer_cpu_ns','archive_cpu_ns','selection_cpu_ns','audit_cpu_ns',
      'sim_wall_ns','optimizer_wall_ns','archive_wall_ns','selection_wall_ns','audit_wall_ns',
      'peak_rss_bytes','archive_peak_tracemalloc_bytes','peak_native_archive_members',
      'final_export_members','pair_comparisons','bootstrap_draws_per_pair','confidence_pair_calls',
      'runtime_environment_sha256'}
    if set(row)!=expected:raise AuditBlocked(f'instrumentation schema mismatch: {sorted(set(row)^expected)}')
    if type(row['seed'])!=int or row['arm'] not in {'F0','F1'}:raise AuditBlocked('invalid identity')
    for key,n in [('run_sha',40),('input_ledger_sha256',64),('runtime_environment_sha256',64)]:
        val=row[key];
        if not isinstance(val,str) or len(val)!=n or any(c not in '0123456789abcdef' for c in val):raise AuditBlocked(f'{key} invalid')
    ints=expected-{'seed','arm','run_sha','input_ledger_sha256','runtime_environment_sha256'}
    for key in ints:
        if type(row[key])!=int or row[key]<0:raise AuditBlocked(f'{key} must be nonnegative integer')
    if row['n_controller_blocks']!=BUDGET:raise AuditBlocked('not equal 12600 CB budget')
    if row['final_export_members']!=10:raise AuditBlocked('final B=K=10 not honored')
    if row['peak_native_archive_members']<10:raise AuditBlocked('native archive unexpectedly below B10')
    if row['pair_comparisons']<row['confidence_pair_calls']:raise AuditBlocked('pair counts inconsistent')
    if row['arm']=='F0' and (row['confidence_pair_calls'] or row['bootstrap_draws_per_pair']):raise AuditBlocked('F0 should not run confidence bootstrap')
    if row['arm']=='F1' and (not row['confidence_pair_calls'] or not row['bootstrap_draws_per_pair']):raise AuditBlocked('F1 missing bootstrap counts')
    if row['sim_cpu_ns']==0 or row['archive_cpu_ns']==0 or row['peak_rss_bytes']==0:raise AuditBlocked('timing/RSS instrument missing')
    row=dict(row)
    row['total_cpu_ns']=sum(row[x] for x in ('sim_cpu_ns','optimizer_cpu_ns','archive_cpu_ns','selection_cpu_ns','audit_cpu_ns'))
    row['total_wall_phase_sum_ns']=sum(row[x] for x in ('sim_wall_ns','optimizer_wall_ns','archive_wall_ns','selection_wall_ns','audit_wall_ns'))
    return row

def paired_cost_check(rows:list[dict]):
    if len(rows)!=2:raise AuditBlocked('exact F0/F1 pair required')
    by={r['arm']:parse_cost_record(r) for r in rows}
    if set(by)!={'F0','F1'}:raise AuditBlocked('must be one F0 and one F1')
    a,b=by['F0'],by['F1']
    for k in ('seed','run_sha','input_ledger_sha256','runtime_environment_sha256','n_controller_blocks'):
        if a[k]!=b[k]:raise AuditBlocked(f'cannot compare across different {k}')
    return {'seed':a['seed'],'same_input_ledger':True,'same_hardware_environment':True,
      'same_controller_block_evaluations':True,
      'post_export_B_equal':True,
      'native_archive_storage_equal':a['peak_native_archive_members']==b['peak_native_archive_members'],
      'cpu_total_F0_ns':a['total_cpu_ns'],'cpu_total_F1_ns':b['total_cpu_ns'],
      'cpu_total_ratio_F1_to_F0':b['total_cpu_ns']/a['total_cpu_ns'],
      'peak_rss_F0_bytes':a['peak_rss_bytes'],'peak_rss_F1_bytes':b['peak_rss_bytes'],
      'meets_equal_total_compute':False if a['total_cpu_ns']!=b['total_cpu_ns'] else True,
      'equal_total_compute_criterion':'MEASURED_EQUAL_WITHOUT_TOLERANCE; alternative equivalence margin must be prospectively locked',
      'confidence_archive_cpu_ratio_F1_to_F0':b['archive_cpu_ns']/a['archive_cpu_ns']}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--r16-zip',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--all-available',action='store_true')
    a=p.parse_args()
    results=audit_pairs(a.r16_zip,only_c1a1=not a.all_available)
    a.out.parent.mkdir(exist_ok=True,parents=True)
    with a.out.open('w',encoding='utf-8') as f:json.dump(results,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(f'Validated {len(results)} historical TRAIN pairs. Simulator-tick proxy only; not native archive CPU.')
