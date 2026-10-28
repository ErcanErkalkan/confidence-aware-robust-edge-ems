#!/usr/bin/env python3
"""Read-only, scope-limited OpenCEM raw measurement to frozen 2-min replay validation.

This is an independent raw-value reaggregation of only the user-supplied CSV
partitions, NOT the 19-partition historical pipeline, original controller tensor,
prospective R19, independent TEST, or any operational physical validation.
"""
from __future__ import annotations
import argparse, gzip, hashlib, io, json, zipfile
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd

SIGNALS=['outsumw','outw_a','outw_b','outw_c','pv1power','pv2power','pv3power']
COLS=['read_ts','inverter',*SIGNALS]
FROZEN_BINS='RESULTS/ACCEPTED_2MIN_REPLAY_BINS_WITH_SOURCE_ROWS.csv.gz'
FROZEN_MAP='RESULTS/RAW_ROWS_TO_ACCEPTED_REPLAY_BINS.csv.gz'
FROZEN_SHA='RESULTS/RAW_19_SOURCE_HASHES.csv'

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raw',nargs='+',type=Path,required=True)
    ap.add_argument('--lineage-zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.out.exists():raise ValueError('Output must not preexist; fail closed')
    if len({x.name for x in a.raw})!=len(a.raw):raise ValueError('duplicate raw names')
    parts={p.name:p for p in a.raw}
    with zipfile.ZipFile(a.lineage_zip) as z:
        expected=pd.read_csv(z.open(FROZEN_SHA)).set_index('partition_name')
        data=[];rows_by_partition={}; hashes={}
        for fname,p in parts.items():
            if fname not in expected.index:raise ValueError('Raw file not in pinned reference '+fname)
            observed_sha=sha(p); exp=str(expected.loc[fname,'sha256'])
            if observed_sha!=exp:raise ValueError('Raw file SHA mismatch '+fname)
            df=pd.read_csv(p,usecols=COLS,low_memory=False)
            df['row_1based']=np.arange(1,len(df)+1,dtype=np.int32)
            for name in COLS:df[name]=pd.to_numeric(df[name],errors='coerce')
            rows_by_partition[fname]=df
            hashes[fname]={'sha256':observed_sha,'rows':len(df),'expected_sha256':exp,'raw_size_bytes':p.stat().st_size}
            data.append(df[COLS])
        raw=pd.concat(data,ignore_index=True).dropna(subset=['read_ts','inverter'])
        if raw.empty:raise ValueError('no valid raw rows')
        mean=raw.groupby(['read_ts','inverter'],sort=True,dropna=False)[SIGNALS].mean().reset_index()
        phase=mean[['outw_a','outw_b','outw_c']].sum(axis=1,min_count=1)
        total=mean['outsumw'].where(mean['outsumw'].notna(),phase)
        load=(total.where(total>=0)/1000)
        pv=mean[['pv1power','pv2power','pv3power']].sum(axis=1,min_count=1)
        pv=(pv.where(pv>=0)/1000)
        mean['bin_utc']=pd.to_datetime(mean.read_ts,unit='s',utc=True,errors='raise').dt.floor('2min')
        mean['load_kw']=load;mean['pv_kw']=pv
        mean['n_load']=(load.notna()).astype(int);mean['n_pv']=(pv.notna()).astype(int)
        bins=mean.groupby(['inverter','bin_utc'],sort=True).agg(
            load_kw=('load_kw','mean'),pv_kw=('pv_kw','mean'),n_load=('n_load','sum'),n_pv=('n_pv','sum'),
            n_distinct_raw_timestamps=('read_ts','size')).reset_index()
        bins=bins[(bins.n_load>=1)&(bins.n_pv>=1)].copy()
        bins['base_kw']=bins.load_kw-bins.pv_kw
        bins['local_date']=(bins.bin_utc+pd.Timedelta(hours=8)).dt.strftime('%Y-%m-%d')
        bins['block_id']='opencem:inv'+bins.inverter.astype(str)+':'+bins.local_date
        bins['bin_utc']=bins.bin_utc.dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        with gzip.GzipFile(fileobj=z.open(FROZEN_BINS)) as f: frozen=pd.read_csv(f)
        covered=frozen.source_partition_names.apply(lambda s:bool(s) and set(s.split(';')).issubset(parts))
        eligible=frozen[covered].copy()
        # Require that every frozen accepted bin in an eligible block has fully
        # materialized source partitions: prevents boundary undercoverage.
        full_scope_ids=set(g.block_id.iloc[0] for _,g in frozen.groupby('block_id')
                           if g.source_partition_names.apply(lambda s:set(s.split(';')).issubset(parts)).all())
        eligible=eligible[eligible.block_id.isin(full_scope_ids)].copy()
        keys=['block_id','inverter','bin_utc']
        merged=eligible.merge(bins,on=keys,how='left',validate='one_to_one',suffixes=('_frozen','_raw'),indicator=True)
        comparisons=[]
        for col in ('load_kw','pv_kw','base_kw'):
            delta=(merged[col+'_raw']-merged[col+'_frozen']).abs().to_numpy(dtype=float)
            comparisons.append({'signal':col,'max_abs_diff':float(np.nanmax(delta)) if delta.size else None,
                                'nonmatching_above_1e-10':int(np.sum(delta>1e-10))})
        for col in ('n_load','n_pv','n_distinct_raw_timestamps'):
            delta=(merged[col+'_raw']-merged[col+'_frozen']).abs().to_numpy(dtype=float)
            comparisons.append({'signal':col,'max_abs_diff':float(np.nanmax(delta)) if delta.size else None,
                                'nonmatching_above_1e-10':int(np.sum(delta>0))})
        unseen_bins=int((merged._merge!='both').sum())
        # Mapping audits independent of aggregate comparisons: resolve frozen
        # row IDs to actual records and verify the raw source keys and per-channel flags.
        mapping_issues=[]; mapping_counts={}
        for fname,df in rows_by_partition.items():
            filtered=[]
            with gzip.GzipFile(fileobj=z.open(FROZEN_MAP)) as stream:
                for c in pd.read_csv(stream,chunksize=350000):
                    sub=c[c.source_partition==fname]
                    if len(sub):filtered.append(sub)
            m=pd.concat(filtered,ignore_index=True) if filtered else pd.DataFrame()
            if len(m):
                if m.row_1based.duplicated().any():mapping_issues.append(fname+':duplicate_source_row_reference')
                indices=m.row_1based.to_numpy(dtype=int)-1
                if len(indices) and (indices.min()<0 or indices.max()>=len(df)):
                    mapping_issues.append(fname+':out_of_range_source_row');continue
                original=df.iloc[indices]
                ts=original.read_ts.to_numpy(dtype=float); inv=original.inverter.to_numpy(dtype=float)
                if not np.array_equal(ts,m.read_ts.to_numpy(dtype=float)) or not np.array_equal(inv,m.inverter.to_numpy(dtype=float)):
                    mapping_issues.append(fname+':source_row_timestamp_inverter_mismatch')
                timestamps=pd.to_datetime(ts,unit='s',utc=True).floor('2min').strftime('%Y-%m-%dT%H:%M:%SZ')
                if not np.array_equal(timestamps,m.bin_utc_str.to_numpy(dtype=str)):
                    mapping_issues.append(fname+':source_row_bin_mismatch')
                present_load=(original.outsumw.notna()|original[['outw_a','outw_b','outw_c']].notna().any(axis=1)).to_numpy()
                present_pv=original[['pv1power','pv2power','pv3power']].notna().any(axis=1).to_numpy()
                if not np.array_equal(present_load,m.load_channel_present.to_numpy(dtype=bool)):
                    mapping_issues.append(fname+':load_presence_flag_mismatch')
                if not np.array_equal(present_pv,m.pv_channel_present.to_numpy(dtype=bool)):
                    mapping_issues.append(fname+':pv_presence_flag_mismatch')
            mapping_counts[fname]={'mapped_rows':len(m),'total_csv_rows':len(df)}
        full_days=[]
        for block_id,g in merged.groupby('block_id'):
            ts=pd.to_datetime(g.bin_utc,utc=True)
            valid=(len(g)==720 and ts.is_unique and ts.is_monotonic_increasing and
                   (ts.diff().dropna()==pd.Timedelta(minutes=2)).all())
            full_days.append({'block_id':block_id,'bins':len(g),'full_720_contiguous':bool(valid),'raw_frozen_value_match':bool(
                (g._merge=='both').all() and all(np.isclose(g[col+'_raw'],g[col+'_frozen'],rtol=0,atol=1e-10).all() for col in ('load_kw','pv_kw','base_kw')))})
        a.out.mkdir(parents=True)
        merged[['block_id','bin_utc','load_kw_frozen','load_kw_raw','pv_kw_frozen','pv_kw_raw','base_kw_frozen','base_kw_raw']].to_csv(a.out/'SCOPED_RAW_TO_REPLAY_COMPARISON.csv',index=False)
        pd.DataFrame(full_days).to_csv(a.out/'SCOPED_FULL_DAY_VALIDATION.csv',index=False)
        ok=bool(len(eligible)>0 and unseen_bins==0 and len(mapping_issues)==0 and all(x['nonmatching_above_1e-10']==0 for x in comparisons))
        status={'result':'PASS_SCOPED_RAW_MEASUREMENT_RECONSTRUCTION' if ok else 'FAIL_SCOPED_RAW_MEASUREMENT_RECONSTRUCTION',
                'scientific_status':'ENGINEERING_HISTORICAL_TRAIN_VALIDATION_ONLY','source_ref':'5884d253a5267fb240b7a8df6fa9e4d49a905167',
                'raw_partitions':hashes,'recomputed_eligible_bins':len(merged),'recomputed_blocks':len(full_days),
                'full_720_days':sum(x['full_720_contiguous'] for x in full_days),
                'frozen_bin_missing_raw_aggregate':unseen_bins,'values':comparisons,
                'source_row_mapping':mapping_counts,'mapping_issues':mapping_issues,
                'lineage_zip_sha256':sha(a.lineage_zip),'checks_cover_all_19_partitions':False,
                'full_381_days_verified_from_raw_values':False,'prospective_or_independent_TEST':False,
                'historical_controller_tensors_verified':False,'source_files_mutated':False,
                'qualification':'Scope is only days whose complete frozen source partitions lie in supplied raw files; original converter semantics independently reaggregated.'}
        (a.out/'SCOPED_RESULT.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:v for k,v in status.items() if k not in ('raw_partitions','values')},indent=2))
        if not ok:raise SystemExit(2)

if __name__=='__main__': main()
