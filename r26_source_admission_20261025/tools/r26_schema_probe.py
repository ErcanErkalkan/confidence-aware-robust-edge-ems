"""First-pass DATA STRUCTURE diagnostic only: NEVER unblinds or authorizes TEST.
Does not interpolate coarse time series or invent grid/SOC measurements.
"""
from __future__ import annotations
import csv,datetime as dt,math,statistics
from pathlib import Path
class SchemaBlocked(ValueError):pass
REQ={'timestamp','site_id','load_kw','pv_kw','grid_kw','battery_soc_pct'}
def probe_csv(path:Path,*,expected_step_minutes:float=2,allow_1min_to_2min:bool=True)->dict:
    if expected_step_minutes!=2:raise SchemaBlocked('R19_2_MIN_REQUIRED')
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not REQ.issubset(reader.fieldnames):raise SchemaBlocked('MISSING_NATIVE_GRID_LOAD_PV_SOC_COLUMNS')
        per={};n=0
        for row in reader:
            try:
                t=dt.datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
                if t.tzinfo is None:raise ValueError('naive')
                vals=[float(row[k]) for k in ('load_kw','pv_kw','grid_kw','battery_soc_pct')]
                if not all(math.isfinite(v) for v in vals) or not 0<=vals[3]<=100:raise ValueError('bad values')
                site=row['site_id'];assert site and not site.isspace()
            except (ValueError,TypeError,AssertionError,AttributeError):raise SchemaBlocked('INVALID_TIMESTAMP_UNITS_OR_SOC')
            per.setdefault(site,[]).append(t.astimezone(dt.timezone.utc));n+=1
    if n<2:raise SchemaBlocked('TOO_FEW_ROWS')
    result=[]
    for site,times in sorted(per.items()):
        if len(times)<2:raise SchemaBlocked('SITE_TOO_FEW_ROWS')
        if len(times)!=len(set(times)):raise SchemaBlocked('DUPLICATE_TIMESTAMP_SITE')
        ordered=sorted(times)
        intervals=[(b-a).total_seconds()/60 for a,b in zip(ordered,ordered[1:])]
        if any(k<=0 for k in intervals):raise SchemaBlocked('BAD_TEMPORAL_ORDER')
        med=statistics.median(intervals)
        if med not in ((1.0,2.0) if allow_1min_to_2min else (2.0,)):
            raise SchemaBlocked('COARSE_NATIVE_CADENCE_CANNOT_RECONSTRUCT_2MIN_DYNAMICS')
        discontinuities=sum(abs(interval-med)>1e-6 for interval in intervals)
        result.append({'site_id':site,'rows':len(ordered),'median_native_minutes':med,
            'gaps_at_native_cadence':discontinuities,
            'distinct_calendar_dates':len({x.date() for x in ordered})})
    return {'status':'SCHEMA_ONLY_INGEST_REVIEW_REQUIRED','sites':result,'total_rows':n,
       'measured_grid_not_necessarily_contract_cap':True,
       'native_subminute_inverter_flips_not_inferred':True,
       'source_rights_independence_external_lock_verified':False,
       'source_safety_certified':False,'is_independent_new_TEST':False}
