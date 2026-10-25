#!/usr/bin/env python3
"""R30: audit public Pecan Street *metadata*, never licensed time series.

No approval can result from this tool: public flags are not measurements at common
clock times, do not prove SOC/LFP/control commands, and do not establish that
'dataid' is a unique physical home or that provider raw file bytes are attested.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, io, json, math, re
from pathlib import Path

REQUIRED = ('dataid','pv','grid','solar','egauge_1min_min_time','egauge_1min_max_time','egauge_1min_data_availability')
STORAGE=('battery1','energy_storage_system')
NEEDED_EXTRA=('battery1','energy_storage_system','active_record')
FORBIDDEN={'battery_soc_pct','grid_kw','pv_kw','controller_flips','lfp_cycle_loss_pct','contractual_grid_cap_kw'}
BOUNDARY=re.compile(r' (?=\d{1,7},(?:yes|no)?,(?:Single-Family|Town Home|Apartment|Commercial|Duplex|Condo|Multi-Family|Mobile Home|Sales|,))')
MAX_BYTES=26_000_000

class IntakeError(ValueError):
    pass

def _read_csv(text:str,mode:str):
    if mode not in ('original_csv','normalized_extractor_text'):raise IntakeError('INPUT_MODE')
    if not text or len(text)>MAX_BYTES: raise IntakeError('INPUT_SIZE')
    if mode=='normalized_extractor_text':
        if '\n' in text.strip() or '\r' in text.strip():raise IntakeError('EXTRACTOR_BOUNDARIES')
        parts=BOUNDARY.split(text.replace('\\_','_'))
        if len(parts)<2:raise IntakeError('EXTRACTOR_NO_RECORDS')
        try:headers=next(csv.reader([parts[0]],strict=True)); cells=[next(csv.reader([x],strict=True)) for x in parts[1:]]
        except (csv.Error, StopIteration) as e:raise IntakeError('EXTRACTOR_CSV_SYNTAX') from e
    else:
        try:
            parsed=list(csv.reader(io.StringIO(text),strict=True))
        except csv.Error as e:raise IntakeError('CSV_SYNTAX') from e
        if len(parsed)<2:raise IntakeError('EMPTY_OR_HEADER_ONLY')
        headers,cells=parsed[0],parsed[1:]
    if len(headers)!=len(set(headers)) or not set(REQUIRED).issubset(headers) or not set(STORAGE).issubset(headers):raise IntakeError('MISSING_OR_DUPLICATE_HEADERS')
    if FORBIDDEN & set(headers):raise IntakeError('PRIVATE_OR_MISLEADING_COLUMNS')
    if any(len(row)!=len(headers) for row in cells):raise IntakeError('ROW_WIDTH')
    rows=[dict(zip(headers, r)) for r in cells]
    ids=[r['dataid'].strip() for r in rows]
    if len(ids)!=len(set(ids)) or any(not re.fullmatch(r'\d{1,7}',x) for x in ids):raise IntakeError('DUPLICATE_OR_INVALID_PUBLIC_RECORD_ID')
    return headers,rows

def _yes(row,k):return row.get(k,'').strip().lower()=='yes'

def _iso(s):
    s=s.strip().replace(' ','T',1)
    s=re.sub(r'([+-]\d{2})$',r'\1:00',s)
    if not s:return None
    try:
        t=dt.datetime.fromisoformat(s)
    except ValueError: raise IntakeError('BAD_METADATA_TIMESTAMP')
    if t.tzinfo is None:raise IntakeError('TIMESTAMP_WITHOUT_TIMEZONE')
    return t

def _duration_and_availability(r):
    left=_iso(r['egauge_1min_min_time']);right=_iso(r['egauge_1min_max_time'])
    if (left is None)!=(right is None):raise IntakeError('PARTIAL_WINDOW')
    a=r['egauge_1min_data_availability'].strip()
    if not left and a:raise IntakeError('AVAILABILITY_WITHOUT_WINDOW')
    if left and right<=left:raise IntakeError('NONPOSITIVE_WINDOW')
    if not a:return None,None
    if not a.endswith('%'):raise IntakeError('AVAILABILITY_NOT_PERCENT')
    try:value=float(a[:-1])
    except ValueError:raise IntakeError('BAD_AVAILABILITY')
    if not math.isfinite(value) or not 0<=value<=100:raise IntakeError('AVAILABILITY_RANGE')
    return (right-left).total_seconds()/86400 if left else None,value

def _group(rows):
    days=[r['_days'] for r in rows if r['_days'] is not None]
    return {'public_home_resident_records':len(rows),
            'advertised_one_min_availability_ge90':sum(r['_av'] is not None and r['_av']>=90 for r in rows),
            'advertised_one_min_availability_ge95':sum(r['_av'] is not None and r['_av']>=95 for r in rows),
            'metadata_window_span_ge30days':sum(r['_days'] is not None and r['_days']>=30 for r in rows),
            'minimum_metadata_window_days_rounded':round(min(days),2) if days else None,
            'maximum_metadata_window_days_rounded':round(max(days),2) if days else None}

def evaluate_public_metadata(text:str,mode:str, *, provenance:str):
    headers,raw=_read_csv(text,mode)
    cleaned=[]
    for r in raw:
        days,avail=_duration_and_availability(r)
        v=dict(r);v['_days']=days;v['_av']=avail
        cleaned.append(v)
    meta=[r for r in cleaned if all(_yes(r,k) for k in ('pv','grid','solar')) and r['_days'] is not None and r['_av'] is not None and r['_av']>0]
    b=[r for r in meta if _yes(r,'battery1')];e=[r for r in meta if _yes(r,'energy_storage_system')]
    u=[r for r in meta if _yes(r,'battery1') or _yes(r,'energy_storage_system')]
    i=[r for r in meta if _yes(r,'battery1') and _yes(r,'energy_storage_system')]
    result={
        'stage':'R30_PUBLIC_METADATA_AND_EVIDENCE_CONDITIONAL_ONLY',
        'provenance':provenance,
        'input_mode':mode,
        'provider_original_bytes_authenticated':False,
        'public_metadata_record_count':len(cleaned),
        'public_metadata_columns':len(headers),
        'unique_physical_houses_count':None,
        'same_timestep_real_power_and_SOC_verified':False,
        'groups':{'pv_grid_solar_one_min':_group(meta),'battery1':_group(b),'energy_storage_system':_group(e),'storage_flag_union':_group(u)},
        'storage_flag_intersection_count':len(i),
        'storage_union_plus_zero_storage_flags':len(u)+len(meta)-len(u),
        'storage_flag_free_metadata_candidates':len(meta)-len(u),
        'physically_valid_CRMT_objectives':0,
        'independent_source_custody':False,
        'independent_test':'NO_GO',
        'r19_R23_efficacy_study':'NOT_RUN',
        'id_note':'A dataid is a home-resident pair, not necessarily a unique building',
        'exposure_note':'Provider availability %/date span does not demonstrate complete synchronized BESS + PV + grid samples',
        'no_household_identifiers_exported':True,
    }
    return result

def run_file(path:Path,mode:str):
    binary=path.read_bytes()
    if len(binary)>MAX_BYTES:raise IntakeError('INPUT_BYTES_LIMIT')
    try:text=binary.decode('utf-8-sig')
    except UnicodeDecodeError:raise IntakeError('INPUT_ENCODING')
    result=evaluate_public_metadata(text,mode,provenance='LOCAL_PUBLIC_METADATA_NOT_INDEPENDENTLY_PUBLISHER_ATTESTED')
    result['local_input_sha256']=hashlib.sha256(binary).hexdigest()
    result['local_hash_scope']='EXACT_LOCAL_INPUT_ONLY; SOURCE_ORIGIN_NOT_PROVEN'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--mode',choices=['original_csv','normalized_extractor_text'],required=True);p.add_argument('--out',required=True)
    a=p.parse_args(); out=Path(a.out)
    if out.exists():raise SystemExit('R30_REFUSE_OVERWRITE')
    result=run_file(Path(a.input),a.mode)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
    print('R30_PUBLIC_ONLY_NO_GO')
if __name__=='__main__':main()
