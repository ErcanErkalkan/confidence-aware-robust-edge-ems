"""R20 exploratory *post-archive* microbenchmark on exact GitHub source blobs.

Not a historical CPU reconstruction, no new sim calls, no validation/TEST input.
Measured on replayed TRAIN candidate samples from an archived R16 ZIP.
"""
from __future__ import annotations
import csv
import datetime
import hashlib
import io
import json
import os
import platform
import resource
import statistics
import sys
import time
import tracemalloc
import zipfile
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference_snapshot'))
from crmt_edge_ems.archive import ConfidenceArchive,CandidateRecord
import crmt_edge_ems.archive as archive_module
from crmt_edge_ems.risk import RiskConfig,risk_calibrated_score
from crmt_edge_ems.dominance import pareto_dominates
from cost_audit import OBJ,AuditBlocked

SOURCE_BLOBS={'risk.py':'edee0d3361691535330419d0203757d0b3624638',
              'dominance.py':'c0fa644839407aaf1ac388a5082435a3a446be29',
              'archive.py':'bb644663febea3990ebeb23f47e403ab0c8070f3'}


def validate_source_snapshots():
    for name,expected in SOURCE_BLOBS.items():
        path=ROOT/'reference_snapshot/crmt_edge_ems'/name
        content=path.read_bytes()
        blob=b'blob '+str(len(content)).encode()+b'\0'+content
        got=hashlib.sha1(blob).hexdigest()
        if got!=expected:raise AuditBlocked(f'{name}: source blob changed; BLOCKED')


def load_records(z:zipfile.ZipFile,seed:int, candidates:int):
    stem=f'crmt_r16/raw/seed{seed}_C1_A1/F0/candidate_metrics.csv'
    raw=z.read(stem)
    source_sha=hashlib.sha256(raw).hexdigest()
    records={}
    # Streaming CSV parser: original R16 source, never one row invented or imputed.
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    values={}
    for row in reader:
        key=row['candidate_id']
        if key not in values:values[key]=[]
        values[key].append((row['block_id'],[float(row[o]) for o in OBJ]))
    ids=sorted(values)[:candidates]
    if len(ids)!=candidates:raise AuditBlocked('candidate subset too large')
    for cid in ids:
        ordered=values[cid]
        bids=tuple(x for x,_ in ordered)
        arr=np.asarray([v for _,v in ordered],float)
        if len(bids)!=len(set(bids)) or arr.shape[1]!=4 or not np.isfinite(arr).all():raise AuditBlocked('invalid subset samples')
        risk=np.array([risk_calibrated_score(arr[:,j]) for j in range(4)])
        records[cid]=CandidateRecord(cid,{},arr,risk,bids)
    return records,source_sha


def run_one(records:dict,method:str,n_boot:int, *, track_memory:bool=False):
    count={'compared_candidate_pairs':0,'confidence_bootstrap_calls':0,'aligned_pair_block_sum':0}
    def counted(*args,**kwargs):
        count['confidence_bootstrap_calls']+=1
        count['aligned_pair_block_sum']+=len(args[0])
        return original(*args,**kwargs)
    clock0=time.perf_counter_ns(); cpu0=time.process_time_ns()
    if track_memory:tracemalloc.start()
    if method=='F0':
        ids=list(records)
        result=[]
        for cid in ids:
            dominated=False
            for other in ids:
                if other==cid:continue
                count['compared_candidate_pairs']+=1
                if pareto_dominates(records[other].risk_vector,records[cid].risk_vector):
                    dominated=True;break
            if not dominated:result.append(cid)
    elif method=='F1':
        ar=ConfidenceArchive(risk=RiskConfig(),alpha=.05,n_boot=n_boot)
        for x in records.values():ar.add(x)
        original=archive_module.confidence_risk_dominance
        archive_module.confidence_risk_dominance=counted
        try:
            result=ar.confidently_nondominated_ids()
        finally:
            archive_module.confidence_risk_dominance=original
        count['compared_candidate_pairs']=count['confidence_bootstrap_calls']
    else:raise AuditBlocked('unknown F method')
    if track_memory:
        _current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    else:peak=None
    cpu_ns=time.process_time_ns()-cpu0
    wall_ns=time.perf_counter_ns()-clock0
    return {**count,'method':method,'cpu_ns':cpu_ns,'wall_ns':wall_ns,'tracemalloc_peak_bytes':peak,
            'replayed_archive_count':len(result),'bootstrap_draws_per_direction':n_boot if method=='F1' else 0,
            'bootstrap_resamples_total':count['confidence_bootstrap_calls']*n_boot*2,
            'actual_measured_source_archive_only':True}


def execute(source:Path, seeds=(1004,1005), candidate_counts=(8,16,32), n_boot=200):
    validate_source_snapshots()
    if n_boot<200:raise AuditBlocked('source confidence routine requires >=200 draws')
    report=[]
    with zipfile.ZipFile(source) as z:
        for seed in seeds:
            for n in candidate_counts:
                records,sha=load_records(z,seed,n)
                # Warm-up outside measurement: reduce import / JIT / allocator noise.
                risk_calibrated_score(np.arange(4,dtype=float))
                arms=[]
                for method in ('F0','F1'):
                    timed=run_one(records,method,n_boot,track_memory=False)
                    # Separate second run measures Python allocation peak, so
                    # tracing overhead cannot bias the reported CPU timings.
                    mem=run_one(records,method,n_boot,track_memory=True)
                    if mem['replayed_archive_count']!=timed['replayed_archive_count'] or mem['confidence_bootstrap_calls']!=timed['confidence_bootstrap_calls']:
                        raise AuditBlocked('memory and timing runs disagree on output or comparisons')
                    timed['tracemalloc_peak_bytes']=mem['tracemalloc_peak_bytes']
                    timed['memory_profile_cpu_ns_EXCLUDED_FROM_TIMING']=mem['cpu_ns']
                    arms.append(timed)
                # No equality assertion on *native* archive size: that's precisely being measured.
                report.append({'seed':seed,'n_candidates':n,'n_boot':n_boot,
                   'source_metrics_sha256':sha,
                   'input_sample_block_counts':[len(v.block_ids) for v in records.values()],
                   'measures':arms,'cpu_ratio_F1_over_F0':arms[1]['cpu_ns']/max(arms[0]['cpu_ns'],1),
                   'wall_ratio_F1_over_F0':arms[1]['wall_ns']/max(arms[0]['wall_ns'],1),
                   'scope':'POSTPROCESS_ONLY_REPLAYED_HISTORICAL_TRAIN_SUBPOOL_NOT_FULL_256'})
    return {'provenance':{'source':'Historical R16 packaged C1/A1 TRAIN metric rows',
        'live_source_modules_sha':SOURCE_BLOBS,
        'python':sys.version.split()[0], 'numpy':np.__version__, 'os':platform.platform(),
        'processor':platform.processor(),'logical_cpus':os.cpu_count(),
        'timestamps_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'rss_max_running_process_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
      'n_comparisons':len(report),'results':report,
      'caveats':['Measured reference code without EMS evaluation, optimizer, AUDIT or input parsing time.',
      'No B=10 memory cap enforced *inside* reference archive: post-export capacity is a different concept.',
      'Benchmark variance due to runtime/OS; times are NOT historical F0/F1 run times. Timing run excludes tracemalloc overhead; Python allocation peak recorded in a separate replay.',
      'n_boot=200 microbenchmark setting differs from frozen historical n_boot; never extrapolate 256 costs.',
      'tracemalloc measures tracked Python allocations, not peak resident or NumPy allocator full RSS; ru_maxrss is process-wide maximum.',
      'F1 lower error not implied by elapsed CPU; no independent TEST.']}

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--r16-zip',required=True,type=Path)
    a.add_argument('--out',required=True,type=Path);a.add_argument('--n-boot',type=int,default=200)
    args=a.parse_args()
    report=execute(args.r16_zip,n_boot=args.n_boot)
    args.out.parent.mkdir(exist_ok=True,parents=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    for row in report['results']:
        a,b=row['measures'];print(row['seed'],row['n_candidates'],'F0 CPUms',round(a['cpu_ns']/1e6,2),'F1 CPUms',round(b['cpu_ns']/1e6,2),'ratio',round(row['cpu_ratio_F1_over_F0'],2),'F1 calls',b['confidence_bootstrap_calls'])
