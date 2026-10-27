"""Strict opt-in lineage adapter. Existing historical ingest stays unchanged."""
from __future__ import annotations
from datetime import date
import itertools
from pathlib import Path
import numpy as np
import pandas as pd
from crmt_edge_ems.contracts import ContractError, finite_array, file_hash, digest, integer

SPLITS={'DISCOVERY','AUDIT','VALIDATION','INTERNAL_TEST','EXTERNAL_TEST'}

def reconstruct_with_lineage(raw, *, source_sha256, local_timezone='Asia/Shanghai', cadence_minutes=2, original_row_numbers=None):
    """Keep inverter subsystems separate; no imputation or duplicate collapse.

    Raw row numbers refer to the caller's original parsed row order, before any
    sorting. The caller must bind source_sha256 to the original file bytes.
    Inputs: read_ts (Unix seconds UTC), inverter, outsumw, pv1power. Additional
    PV channels are summed only when present, complete, finite and nonnegative.
    """
    integer(cadence_minutes,'cadence_minutes',1)
    if 1440%cadence_minutes: raise ContractError('cadence must divide a local ordinary day')
    if not isinstance(source_sha256,str) or len(source_sha256)!=64 or any(c not in '0123456789abcdef' for c in source_sha256): raise ContractError('source SHA-256 required')
    required={'read_ts','inverter','outsumw','pv1power'}
    if not required<=set(raw) or raw.empty: raise ContractError('raw schema incomplete')
    cols=['read_ts','inverter','outsumw']+[c for c in ('pv1power','pv2power','pv3power') if c in raw]
    values=finite_array(raw[cols].to_numpy(),'raw measurements',ndim=2)
    if np.any(values[:,2:]<0): raise ContractError('negative load/PV')
    inverter=raw['inverter'].to_numpy()
    if np.any(inverter!=np.floor(inverter)) or np.any(inverter<1): raise ContractError('invalid inverter identity')
    if raw[['read_ts','inverter']].duplicated().any(): raise ContractError('duplicated observation: explicit historical duplicate policy required')
    row_numbers=np.arange(1,len(raw)+1) if original_row_numbers is None else finite_array(original_row_numbers,'original row numbers',ndim=1)
    if len(row_numbers)!=len(raw) or len(set(row_numbers))!=len(raw) or np.any(row_numbers<1) or np.any(row_numbers!=np.floor(row_numbers)): raise ContractError('invalid original row mapping')
    x=raw.copy(); x['raw_row_1based']=row_numbers
    x['timestamp']=pd.to_datetime(x['read_ts'],unit='s',utc=True,errors='raise')
    if x['timestamp'].isna().any(): raise ContractError('invalid timestamp')
    x['local_date']=x['timestamp'].dt.tz_convert(local_timezone).dt.strftime('%Y-%m-%d')
    x['bin']=x['timestamp'].dt.floor(f'{cadence_minutes}min')
    pvcols=[c for c in ('pv1power','pv2power','pv3power') if c in x]
    x['pv_kw']=x[pvcols].sum(axis=1)/1000; x['load_kw']=x['outsumw']/1000
    rows=[]
    for (inv,stamp),g in x.groupby(['inverter','bin'],sort=True):
        if g['local_date'].nunique()!=1: raise ContractError('resampling bin crosses local day')
        rowids=sorted(g['raw_row_1based'].astype(int).tolist()); day=g['local_date'].iloc[0]
        row={'timestamp':stamp,'site_id':f'inv{int(inv)}','local_date':day,
             'block_id':f'opencem:inv{int(inv)}:{day}','load_kw':float(g['load_kw'].mean()),
             'pv_kw':float(g['pv_kw'].mean()),'wind_kw':0.0,'peak_flag':0,
             'source_sha256':source_sha256,'raw_rows':rowids,'valid_observations':len(g),
             'timezone':local_timezone,'cadence_minutes':cadence_minutes}
        row['base_kw']=row['load_kw']-row['pv_kw']
        row['lineage_id']=digest({**row,'timestamp':stamp.isoformat()})
        rows.append(row)
    return pd.DataFrame(rows)

def ingest_csv(path, **kwargs):
    path=Path(path)
    return reconstruct_with_lineage(pd.read_csv(path),source_sha256=file_hash(path),**kwargs)

def require_complete_days(frame, *, min_coverage=0.95, min_observations_per_bin=1):
    if not isinstance(min_coverage,(int,float)) or not np.isfinite(min_coverage) or not 0<min_coverage<=1: raise ContractError('invalid coverage threshold')
    integer(min_observations_per_bin,'min_observations_per_bin',1)
    required={'timestamp','site_id','local_date','cadence_minutes','timezone','valid_observations'}
    if not required<=set(frame) or frame.empty: raise ContractError('lineage frame missing')
    blocks={}
    for (site,day),g in frame.groupby(['site_id','local_date'],sort=True):
        if g['cadence_minutes'].nunique()!=1 or g['timezone'].nunique()!=1: raise ContractError('mixed cadence/timezone')
        cadence=int(g['cadence_minutes'].iloc[0]); zone=g['timezone'].iloc[0]
        start=pd.Timestamp(day,tz=zone); stop=start+pd.DateOffset(days=1)
        grid=pd.date_range(start,stop,freq=f'{cadence}min',inclusive='left').tz_convert('UTC')
        ts=pd.DatetimeIndex(g['timestamp'])
        if ts.tz is None or ts.hasnans or ts.has_duplicates or not ts.is_monotonic_increasing or not ts.isin(grid).all(): raise ContractError('invalid day support')
        if (g['valid_observations']<min_observations_per_bin).any() or len(g)<np.ceil(len(grid)*min_coverage): raise ContractError(f'insufficient day support: {site}/{day}')
        blocks[f'{site}:{day}']=g.copy()
    return blocks

def validate_partitions(entries, *, embargo_days=7, require_unexposed_test=True):
    integer(embargo_days,'embargo_days')
    if not entries: raise ContractError('empty split inventory')
    ids=set(); groups={}; partitions={s:[] for s in SPLITS}
    for e in entries:
        if set(e)!={'block_id','split','site_id','local_day','group_id','exposure','source_sha256'}: raise ContractError('partition schema mismatch')
        if any(not isinstance(e[k],str) or not e[k].strip() for k in e): raise ContractError('blank partition metadata')
        if len(e['source_sha256'])!=64 or any(c not in '0123456789abcdef' for c in e['source_sha256']): raise ContractError('invalid partition source SHA')
        try: day=date.fromisoformat(e['local_day'])
        except ValueError as exc: raise ContractError('invalid local day') from exc
        if day.isoformat()!=e['local_day'] or e['split'] not in SPLITS: raise ContractError('invalid split/day')
        if e['exposure'] not in {'UNEXPOSED','EXPOSED'}: raise ContractError('unknown exposure')
        if e['block_id'] in ids: raise ContractError('duplicate block across partitions')
        ids.add(e['block_id'])
        for key in (('GROUP',e['group_id']),('SITE_DAY',e['site_id'],e['local_day'])):
            if key in groups and groups[key]!=e['split']: raise ContractError('forbidden group/day overlap')
            groups[key]=e['split']
        if require_unexposed_test and e['split']=='EXTERNAL_TEST' and e['exposure']!='UNEXPOSED': raise ContractError('exposed data cannot be independent TEST')
        partitions[e['split']].append((e,day))
    for s0,s1 in itertools.combinations(sorted(SPLITS),2):
        for (a,da),(b,db) in itertools.product(partitions[s0],partitions[s1]):
            if a['site_id']==b['site_id'] and abs((da-db).days)<=embargo_days: raise ContractError('temporal embargo violation')
    return {'schema_version':1,'status':'STRUCTURAL_CHECK_PASSED_NOT_EXPOSURE_ATTESTATION',
        'blocks':len(ids),'embargo_days':embargo_days,'inventory_sha256':digest(entries)}