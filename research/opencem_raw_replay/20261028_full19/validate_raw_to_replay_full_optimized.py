#!/usr/bin/env python3
"""Fail-closed independently aggregated raw OpenCEM -> frozen replay values.

Historical/exposed engineering replay scope ONLY. No controller tensor equality,
new TEST, prospective study, field safety or external data-rights certification.
Does not write to or modify input source partitions or historical artifacts.
"""
from __future__ import annotations
import argparse, hashlib, json, gzip, zipfile, sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

SIGNALS=['outsumw','outw_a','outw_b','outw_c','pv1power','pv2power','pv3power']
COLS=['read_ts','inverter',*SIGNALS]
FROZEN_BINS='RESULTS/ACCEPTED_2MIN_REPLAY_BINS_WITH_SOURCE_ROWS.csv.gz'
FROZEN_MAP='RESULTS/RAW_ROWS_TO_ACCEPTED_REPLAY_BINS.csv.gz'
FROZEN_SHA='RESULTS/RAW_19_SOURCE_HASHES.csv'

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(4<<20),b''):h.update(chunk)
    return h.hexdigest()

def read_member(z,name):
    with gzip.GzipFile(fileobj=z.open(name)) as f:return pd.read_csv(f,low_memory=False)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw-dir',required=True,type=Path)
    ap.add_argument('--lineage-zip',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--allow-partial',action='store_true')
    a=ap.parse_args()
    if a.out.exists():raise ValueError('Fail closed: output directory already exists')
    with zipfile.ZipFile(a.lineage_zip) as z:
        ref=pd.read_csv(z.open(FROZEN_SHA)); expected=ref.set_index('partition_name')
        available={p.name:p for p in a.raw_dir.glob('*.csv')}
        present={name:path for name,path in available.items() if name in expected.index}
        if not present:raise ValueError('No pinned source files')
        if set(present)!=set(expected.index) and not a.allow_partial:raise ValueError('Not all 19 pinned sources available')
        # Loaded ONCE. Previous version parsed this large member once PER partition.
        frozen=read_member(z,FROZEN_BINS)
        mapping=read_member(z,FROZEN_MAP)
    mapgroups={k:v for k,v in mapping.groupby('source_partition',sort=False)}
    mapping_total_expected=len(mapping)
    frozen['source_partition_names']=frozen.source_partition_names.fillna('')
    full_scope_ids=set()
    for bid,g in frozen.groupby('block_id',sort=False):
        if all(set(str(x).split(';'))<=set(present) for x in g.source_partition_names):full_scope_ids.add(bid)
    eligible=frozen[frozen.block_id.isin(full_scope_ids)].copy()
    results=[]; source_report={}; issues=[]
    for fname in sorted(present):
        path=present[fname]; got=sha256(path); want=str(expected.loc[fname,'sha256'])
        if got!=want:raise ValueError('Source SHA256 mismatch: '+fname)
        df=pd.read_csv(path,usecols=COLS,low_memory=False)
        for c in COLS:df[c]=pd.to_numeric(df[c],errors='coerce')
        row_count=len(df)
        m=mapgroups.get(fname)
        mapped=0
        if m is not None and len(m):
            mapped=len(m)
            ids=m.row_1based.to_numpy(dtype='int64')-1
            if m.row_1based.duplicated().any():issues.append(fname+':duplicate_source_row')
            if ids.min()<0 or ids.max()>=row_count:issues.append(fname+':out_of_range_source_row')
            else:
                original=df.iloc[ids]
                if not np.array_equal(original.read_ts.to_numpy(dtype=float),m.read_ts.to_numpy(dtype=float)) or not np.array_equal(original.inverter.to_numpy(dtype=float),m.inverter.to_numpy(dtype=float)):
                    issues.append(fname+':source_row_timestamp_inverter_mismatch')
                timestamps=pd.to_datetime(original.read_ts.to_numpy(dtype=float),unit='s',utc=True).floor('2min').strftime('%Y-%m-%dT%H:%M:%SZ')
                if not np.array_equal(timestamps,m.bin_utc_str.to_numpy(dtype=str)):issues.append(fname+':source_row_bin_mismatch')
                present_load=(original.outsumw.notna()|original[['outw_a','outw_b','outw_c']].notna().any(axis=1)).to_numpy()
                present_pv=original[['pv1power','pv2power','pv3power']].notna().any(axis=1).to_numpy()
                if not np.array_equal(present_load,m.load_channel_present.to_numpy(dtype=bool)):issues.append(fname+':load_presence_flag_mismatch')
                if not np.array_equal(present_pv,m.pv_channel_present.to_numpy(dtype=bool)):issues.append(fname+':pv_presence_flag_mismatch')
        source_report[fname]={'rows':row_count,'mapped_rows':mapped,'sha256':got,'bytes':path.stat().st_size}
        keys=df.dropna(subset=['read_ts','inverter']).groupby(['read_ts','inverter'],sort=True)[SIGNALS].mean().reset_index()
        phase=keys[['outw_a','outw_b','outw_c']].sum(axis=1,min_count=1)
        total=keys['outsumw'].where(keys.outsumw.notna(),phase)
        load=total.where(total>=0)/1000
        pv=keys[['pv1power','pv2power','pv3power']].sum(axis=1,min_count=1)
        pv=pv.where(pv>=0)/1000
        keys['load_kw']=load;keys['pv_kw']=pv
        keys['n_load']=load.notna().astype(int);keys['n_pv']=pv.notna().astype(int)
        keys['bin_utc']=pd.to_datetime(keys.read_ts,unit='s',utc=True,errors='raise').dt.floor('2min')
        bins=keys.groupby(['inverter','bin_utc'],sort=True).agg(load_kw=('load_kw','mean'),pv_kw=('pv_kw','mean'),n_load=('n_load','sum'),n_pv=('n_pv','sum'),n_distinct_raw_timestamps=('read_ts','size')).reset_index()
        bins=bins[(bins.n_load>=1)&(bins.n_pv>=1)].copy()
        bins['base_kw']=bins.load_kw-bins.pv_kw
        bins['local_date']=(bins.bin_utc+pd.Timedelta(hours=8)).dt.strftime('%Y-%m-%d')
        bins['block_id']='opencem:inv'+bins.inverter.astype('int64').astype(str)+':'+bins.local_date
        bins['bin_utc']=bins.bin_utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        # Keep ONLY frozen-eligible keys from this partition. No reconstruction at
        # excluded hours/days is presented as evidence.
        partition_keys=eligible[eligible.source_partition_names==fname][['block_id','inverter','bin_utc']]
        if len(partition_keys):
            sel=bins.merge(partition_keys,on=['block_id','inverter','bin_utc'],how='inner',validate='one_to_one')
            results.append(sel)
        del df,keys,bins
        print('scanned',fname,'raw_rows',row_count,'mapped',mapped,flush=True)
    raw=pd.concat(results,ignore_index=True) if results else pd.DataFrame()
    if len(raw)==0:raise ValueError('No eligible reconstruction rows')
    if raw.duplicated(['block_id','inverter','bin_utc']).any():issues.append('multiple_source_files_for_same_accepted_bin')
    merged=eligible.merge(raw,on=['block_id','inverter','bin_utc'],how='left',validate='one_to_one',suffixes=('_frozen','_raw'),indicator=True)
    checks=[]
    for c in ['load_kw','pv_kw','base_kw','n_load','n_pv','n_distinct_raw_timestamps']:
        delta=(merged[c+'_raw']-merged[c+'_frozen']).abs().to_numpy(dtype=float)
        checks.append({'name':c,'max_abs_difference':float(np.nanmax(delta)) if len(delta) else None,'mismatches':int(np.count_nonzero(~np.isfinite(delta)|(delta>(1e-10 if c in ('load_kw','pv_kw','base_kw') else 0))))})
    missing=int((merged._merge!='both').sum())
    days=[]
    for bid,g in merged.groupby('block_id',sort=True):
        t=pd.to_datetime(g.bin_utc,utc=True)
        full=bool(len(g)==720 and t.is_unique and t.is_monotonic_increasing and (t.diff().dropna()==pd.Timedelta(minutes=2)).all())
        days.append({'block_id':bid,'bins':len(g),'full_720_contiguous':full,'values_match':bool((g._merge=='both').all() and all(np.isclose(g[c+'_raw'],g[c+'_frozen'],rtol=0,atol=1e-10).all() for c in ('load_kw','pv_kw','base_kw')))})
    status_pass=missing==0 and not issues and all(c['mismatches']==0 for c in checks)
    record={'result':'PASS' if status_pass else 'FAIL','source':'RAW_FROZEN_HISTORICAL_OPENCEM','source_ref':'5884d253a5267fb240b7a8df6fa9e4d49a905167','scientific_scope':'HISTORICALLY_EXPOSED_ENGINEERING_RAW_VALUE_LINEAGE_ONLY','raw_partitions_verified':len(present),'raw_partitions_expected':len(expected),'source_rows_scanned':sum(x['rows'] for x in source_report.values()),'source_rows_mapped':sum(x['mapped_rows'] for x in source_report.values()),'frozen_mapping_rows':mapping_total_expected,'bins_compared':len(merged),'historical_blocks_compared':len(days),'full720_days':sum(x['full_720_contiguous'] for x in days),'partial_days':sum(not x['full_720_contiguous'] for x in days),'missing_aggregates':missing,'column_checks':checks,'mapping_issues':issues,'sources':source_report,'lineage_zip_sha256':sha256(a.lineage_zip),'all_original_files_preserved':True,'historical_controller_inputs_reproduced':False,'new_independent_test':False,'physical_safety_validated':False,'prospective_r19_executed':False}
    a.out.mkdir(parents=True)
    (a.out/'FULL_RAW_REPLAY_VERIFICATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pd.DataFrame(days).to_csv(a.out/'FULL_DAY_SUPPORT_AUDIT.csv',index=False)
    merged[['block_id','bin_utc','load_kw_frozen','load_kw_raw','pv_kw_frozen','pv_kw_raw','base_kw_frozen','base_kw_raw']].to_csv(a.out/'RAW_TO_REPLAY_VALUE_COMPARISON.csv',index=False,float_format='%.17g')
    print(json.dumps({k:v for k,v in record.items() if k!='sources'},indent=2),flush=True)
    if not status_pass:raise SystemExit(2)

if __name__=='__main__':main()