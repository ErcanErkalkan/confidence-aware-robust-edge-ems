"""R28: public Pecan Street *metadata-only* screen; never ingests customer time series.

No flag or metadata column is evidence for native battery SOC, contracted cap,
controller switching, custody rights, preregistration, or unseen TEST eligibility.
"""
from __future__ import annotations
import csv, hashlib, io, json, math, re
from datetime import datetime
from pathlib import Path

MANDATORY = ('dataid','pv','grid','solar','egauge_1min_min_time',
             'egauge_1min_max_time','egauge_1min_data_availability')
OPTIONAL = ('egauge_1s_min_time','egauge_1s_max_time','egauge_1s_data_availability')
class MetadataBlocked(ValueError): pass

def classify(v):
    s=(v or '').strip().lower()
    return s=='yes' # blank/false/unknown cannot be assumed present

def timestamp(v):
    if not v or not v.strip(): return None
    raw=v.strip()
    if re.search(r'[+-]\d{2}$',raw): raw+=':00'  # e.g. -05 -> -05:00
    try: dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
    except ValueError: raise MetadataBlocked('INVALID_META_TIMESTAMP')
    if dt.utcoffset() is None: raise MetadataBlocked('TIMESTAMP_NO_TZ')
    return dt

def availability(v):
    if not v or not v.strip(): return None
    s=v.strip()
    if not s.endswith('%'): raise MetadataBlocked('INVALID_AVAILABILITY_UNIT')
    try: n=float(s[:-1])
    except ValueError: raise MetadataBlocked('INVALID_AVAILABILITY')
    if not math.isfinite(n) or not 0<=n<=100: raise MetadataBlocked('INVALID_AVAILABILITY_RANGE')
    return n

def screen_csv_text(raw:str):
    reader=csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames) or not set(MANDATORY).issubset(reader.fieldnames):
        raise MetadataBlocked('MISSING_OR_DUPLICATE_METADATA_FIELDS')
    if {'battery_soc_pct','contractual_grid_cap_kw','control_flip_event'} & set(reader.fieldnames):
        # Those raw-like fields are not part of the reviewed public metadata schema.
        raise MetadataBlocked('UNVERIFIED_RAW_LIKE_METADATA_FIELDS')
    out=[];seen=set()
    for row in reader:
        if None in row: raise MetadataBlocked('BAD_ROW_FIELD_COUNT')
        id=(row.get('dataid') or '').strip()
        if not id or not id.isdigit() or id in seen:raise MetadataBlocked('DUPLICATE_OR_INVALID_DATAID')
        seen.add(id)
        start=timestamp(row['egauge_1min_min_time']);end=timestamp(row['egauge_1min_max_time'])
        if bool(start)!=bool(end):raise MetadataBlocked('ONE_SIDED_COVERAGE_WINDOW')
        if start and end<start:raise MetadataBlocked('INVERTED_COVERAGE_WINDOW')
        one_min_av=availability(row['egauge_1min_data_availability'])
        if (start is None)!=(one_min_av is None):raise MetadataBlocked('COVERAGE_WITHOUT_DATES')
        has_pv=classify(row['pv']);has_grid=classify(row['grid']);has_solar=classify(row['solar'])
        metadata_candidate=bool(has_pv and has_grid and has_solar and start is not None and (one_min_av or 0)>0)
        out.append({'dataid':id,'metadata_pv':has_pv,'metadata_grid':has_grid,'metadata_solar':has_solar,
                    'one_min_window_start':start.isoformat() if start else None,
                    'one_min_window_end':end.isoformat() if end else None,
                    'metadata_1min_availability_percent':one_min_av,
                    'metadata_joint_grid_solar_1min_candidate':metadata_candidate,
                    'observed_joint_raw_grid_solar_2min_blocks':None,
                    'native_battery_SOC_verified':False,
                    'contractual_grid_cap_verified':False,
                    'LFP_chemistry_verified':False,
                    'controller_switch_events_verified':False,
                    'new_unseen_TEST_eligible':False})
    if not out:raise MetadataBlocked('EMPTY_CATALOG')
    return {'stage':'R28_PUBLIC_METADATA_ONLY','metadata_rows':len(out),
            'plausible_grid_solar_1min_site_metadata_count':sum(x['metadata_joint_grid_solar_1min_candidate'] for x in out),
            'approved_r19_sources':0, 'raw_participant_data_accessed':False,
            'external_source_custody_approved':False,'license_signed':False,
            'independent_TEST':'NO_GO','rows':out}

def screen_file(path:Path):
    content=Path(path).read_bytes()
    if len(content)>25*1024*1024: raise MetadataBlocked('OVERSIZED_METADATA')
    try:raw=content.decode('utf-8-sig')
    except UnicodeDecodeError:raise MetadataBlocked('BAD_ENCODING')
    result=screen_csv_text(raw)
    result['local_metadata_sha256']=hashlib.sha256(content).hexdigest()
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description='Public metadata only, never new TEST or licensed raw')
    p.add_argument('metadata_csv');p.add_argument('--out',required=True);a=p.parse_args()
    target=Path(a.out)
    if target.exists():raise SystemExit('R28_BLOCKED_OUTPUT_EXISTS')
    r=screen_file(Path(a.metadata_csv));target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print('R28_METADATA_ONLY_SOURCE_NOT_ADMITTED',r['plausible_grid_solar_1min_site_metadata_count'])
