#!/usr/bin/env python3
"""Independent consolidation of two overlapping verified raw-file scopes.

Verifies that their union equals the frozen complete 406-block 292256-bin
historical OpenCEM ledger, and that overlap is byte-level/numerically consistent.
Only exposed historical data integrity; NOT independent EMS TEST.
"""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
import numpy as np

NUMERIC=['load_kw_frozen','load_kw_raw','pv_kw_frozen','pv_kw_raw','base_kw_frozen','base_kw_raw']
KEY=['block_id','bin_utc']

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--scope-a',type=Path,required=True);p.add_argument('--scope-b',type=Path,required=True);p.add_argument('--lineage',type=Path,required=True);p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Refusing overwrite of output directory')
    with zipfile.ZipFile(a.lineage) as z:
        man=pd.read_csv(z.open('canonical_block_manifest.csv'));frozen=pd.read_csv(z.open('RESULTS/EXACT_406_BLOCK_RECONSTRUCTION.csv'));refs=pd.read_csv(z.open('RESULTS/RAW_19_SOURCE_HASHES.csv')).set_index('partition_name')
    reports=[]; arrays=[]; days=[]
    for directory in (a.scope_a,a.scope_b):
        s=json.loads((directory/'FULL_RAW_REPLAY_VERIFICATION.json').read_text(encoding='utf-8'))
        if s['result']!='PASS' or s['mapping_issues'] or s['missing_aggregates'] or any(x['mismatches'] for x in s['column_checks']):raise AssertionError('Source scope did not fully pass: '+str(directory))
        reports.append(s)
        tab=pd.read_csv(directory/'RAW_TO_REPLAY_VALUE_COMPARISON.csv',low_memory=False)
        day=pd.read_csv(directory/'FULL_DAY_SUPPORT_AUDIT.csv')
        if len(tab)!=s['bins_compared'] or len(day)!=s['historical_blocks_compared']:raise AssertionError('Scoped file count mismatch')
        if tab.duplicated(KEY).any() or day.block_id.duplicated().any():raise AssertionError('Duplicate keys in scope')
        arrays.append(tab);days.append(day)
    c=pd.concat(arrays,ignore_index=True);d=pd.concat(days,ignore_index=True)
    dup=c[c.duplicated(KEY,keep=False)].copy()
    overlap_keys=int(dup.groupby(KEY).ngroups)
    if dup.groupby(KEY).size().max()>2:raise AssertionError('A key appeared more than twice')
    overlap_nonidentical=0
    for col in NUMERIC:
        spread=dup.groupby(KEY)[col].agg(lambda v:float(v.max()-v.min()))
        overlap_nonidentical+=int((spread>1e-12).sum())
    if overlap_nonidentical:raise AssertionError('Overlapping source reaggregation disagrees')
    for col in ['bins','full_720_contiguous','values_match']:
        if d.groupby('block_id')[col].nunique().max()>1:raise AssertionError('Duplicate day summary disagrees: '+col)
    c=c.drop_duplicates(KEY).sort_values(KEY).reset_index(drop=True)
    d=d.drop_duplicates('block_id').sort_values('block_id').reset_index(drop=True)
    if set(d.block_id)!=set(man.block_id) or set(d.block_id)!=set(frozen.block_id):raise AssertionError('Historical block coverage mismatch')
    check=d.merge(frozen[['block_id','n_ticks']],on='block_id',how='left',validate='one_to_one')
    if (check.bins!=check.n_ticks).any():raise AssertionError('Frozen-day count mismatch')
    for col in ['load_kw','pv_kw','base_kw']:
        if not np.isfinite(c[col+'_raw']).all():raise AssertionError('nonfinite reconstructed signal')
        if (np.abs(c[col+'_raw']-c[col+'_frozen'])>1e-10).any():raise AssertionError('Raw-value mismatch: '+col)
    if not d.values_match.all():raise AssertionError('Not all day values match')
    common_source={}
    for report in reports:
        for fname,v in report['sources'].items():
            if fname in common_source and common_source[fname]!=v:raise AssertionError('Duplicate partition audit differs')
            common_source[fname]=v
    if set(common_source)!=set(refs.index):raise AssertionError('19-partition coverage missing')
    for fname,v in common_source.items():
        if sha(a.raw_dir/fname)!=v['sha256'] or v['sha256']!=str(refs.loc[fname,'sha256']):raise AssertionError('Pinned raw SHA mismatch: '+fname)
    groups=d.merge(man[['block_id','split']],on='block_id',validate='one_to_one').groupby('split',sort=True).agg(blocks=('block_id','size'),bins=('bins','sum'),full_days=('full_720_contiguous','sum')).reset_index()
    assert len(common_source)==19 and len(c)==292256 and len(d)==406 and int(d.full_720_contiguous.sum())==381 and len(d)-int(d.full_720_contiguous.sum())==25
    assert sum(int(v['mapped_rows']) for v in common_source.values())==3853508
    assert sum(int(v['rows']) for v in common_source.values())==4021635
    assert overlap_keys==len(arrays[0])+len(arrays[1])-len(c)
    output={'verification_status':'PASS_FULL_HISTORICAL_RAW_TO_FROZEN_REPLAY_REAGGREGATION','verification_time_utc':datetime.now(timezone.utc).isoformat(),'scientific_scope':'PAST_EXPOSED_2025_2026_DATA_INTEGRITY_ONLY; NOT_REPRODUCTION_OF_ORIGINAL_CONTROLLER_TENSORS; NOT_NEW_TEST','pinned_opencem_source_ref':'5884d253a5267fb240b7a8df6fa9e4d49a905167','raw_partitions_verified':19,'raw_source_rows_read':sum(int(v['rows']) for v in common_source.values()),'raw_source_rows_mapped':sum(int(v['mapped_rows']) for v in common_source.values()),'recomputed_bins_frozen_matched':len(c),'frozen_historical_blocks_matched':len(d),'full720_days_verified':int(d.full_720_contiguous.sum()),'partial_days_rejected_as_full':int((~d.full_720_contiguous).sum()),'max_abs_value_diffs':{col:float(np.max(np.abs(c[col+'_raw']-c[col+'_frozen']))) for col in ['load_kw','pv_kw','base_kw']},'scope_a_raw_parts':len(reports[0]['sources']),'scope_b_raw_parts':len(reports[1]['sources']),'duplicate_source_parts_between_scopes':len(set(reports[0]['sources'])&set(reports[1]['sources'])),'overlap_bins_checked':overlap_keys,'overlap_bin_value_disagreements':overlap_nonidentical,'split_counts':groups.to_dict(orient='records'),'mapping_issues':[],'source_sha256':{k:v['sha256'] for k,v in sorted(common_source.items())},'lineage_zip_sha256':sha(a.lineage),'historical_control_command_soc_tensors_verified':False,'future_independent_test_executed':False,'physical_ems_safety_validated':False,'R19_prospective_authorized':False,'scientific_go':'NO_GO','source_files_mutated':False}
    a.out.mkdir(parents=True)
    (a.out/'FULL_19_RAW_TO_REPLAY_STATUS.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    d.merge(man[['block_id','split']],on='block_id',validate='one_to_one').to_csv(a.out/'FULL_406_DAY_VALIDATION.csv',index=False)
    c.to_csv(a.out/'FULL_292256_RECONSTRUCTED_VALUES.csv',index=False,float_format='%.17g')
    print(json.dumps({k:v for k,v in output.items() if k!='source_sha256'},indent=2),flush=True)
if __name__=='__main__':main()