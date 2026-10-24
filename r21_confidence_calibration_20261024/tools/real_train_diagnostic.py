"""Read-only actual OpenCEM historical TRAIN common-day and pairing diagnostic.

No F0/F1 superiority computed; no AUDIT/TEST data accessed.
"""
from __future__ import annotations
import argparse,csv,io,json,zipfile,hashlib,statistics
from pathlib import Path
from collections import defaultdict
from calibrate import CalibrationBlocked

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip'
OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')


def run(source:Path=SOURCE,seeds=(1001,1004,1005)):
    result=[]
    with zipfile.ZipFile(source) as z:
        for seed in seeds:
            prefix=f'crmt_r16/raw/seed{seed}_C1_A1/'
            arms={}
            for f in ('F0','F1'):
                stem=prefix+f+'/'
                summ=json.loads(z.read(stem+'run_summary.json'))
                raw=z.read(stem+'candidate_metrics.csv')
                if hashlib.sha256(raw).hexdigest()!=summ['files_sha256']['candidate_metrics.csv']:
                    raise CalibrationBlocked(f'{seed} {f}: original SHA mismatch')
                rows=list(csv.DictReader(io.TextIOWrapper(io.BytesIO(raw),encoding='utf-8-sig')))
                if len(rows)!=12600 or any(row['split']!='train' for row in rows):
                    raise CalibrationBlocked('expected 12600 TRAIN rows')
                by=defaultdict(set);day=defaultdict(set);v={}
                for row in rows:
                    cid,bid=row['candidate_id'],row['block_id']
                    if (cid,bid) in v:raise CalibrationBlocked('duplicate candidate/block')
                    for ob in OBJ:float(row[ob])
                    v[(cid,bid)]=tuple(row[ob] for ob in OBJ)
                    by[cid].add(bid)
                    parts=bid.split(':')
                    if len(parts)!=3 or not parts[2].startswith('2025-'):
                        raise CalibrationBlocked('unrecognized block clock; do not infer chronology')
                    day[cid].add(parts[2])
                arms[f]=(summ,by,day,v)
            a,b=arms['F0'],arms['F1']
            if a[3]!=b[3]:raise CalibrationBlocked('arms do not have identical science observation pairs')
            candidate_ids=sorted(a[1]);cnt=[len(a[1][k]) for k in candidate_ids]
            days=[len(a[2][k]) for k in candidate_ids]
            total_common=[];same_day=[]
            for i in range(min(10,len(candidate_ids))):
                for j in range(i+1,min(10,len(candidate_ids))):
                    ci,cj=candidate_ids[i],candidate_ids[j]
                    total_common.append(len(a[1][ci]&a[1][cj]))
                    same_day.append(len(a[2][ci]&a[2][cj]))
            result.append({'seed':seed,'scenario':'C1_A1_HISTORICAL_OPEN_CEM_TRAIN',
                           'source_sha256':hashlib.sha256(z.read(prefix+'F0/candidate_metrics.csv')).hexdigest(),
                           'arm_metrics_identical':True,'n_records':len(a[3]),
                           'n_unique_controllers':len(candidate_ids),
                           'candidate_block_count_min':min(cnt),'candidate_block_count_median':statistics.median(cnt),
                           'candidate_block_count_max':max(cnt),
                           'unique_calendar_days_per_controller_min':min(days),
                           'unique_calendar_days_per_controller_max':max(days),
                           'first10_pair_common_blocks_min':min(total_common),
                           'first10_pair_common_blocks_median':statistics.median(total_common),
                           'first10_pair_common_blocks_max':max(total_common),
                           'first10_pair_shared_days_min':min(same_day),
                           'first10_pair_shared_days_median':statistics.median(same_day),
                           'first10_pair_shared_days_max':max(same_day),
                           'f0_archive_size':int(a[0]['archive_count']),
                           'f1_archive_size':int(b[0]['archive_count']),
                           'conclusion':'DAY_GROUPING_RELEVANT_NO_INDEPENDENCE_PROOF; DATA_ALREADY_SEEN; NOT_NEW_TEST'})
    return {'source_kind':'HISTORICAL_SEEN_OPEN_CEM_TRAIN_ONLY','rows':result}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE)
    p.add_argument('--output',type=Path,default=ROOT/'results/R21_REAL_TRAIN_PAIRING_DIAGNOSTIC.json')
    a=p.parse_args();r=run(a.source)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2)+'\n')
    for row in r['rows']:print(row)
