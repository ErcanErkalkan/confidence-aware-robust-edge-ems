#!/usr/bin/env python3
"""Audit ONLY public Pecan Street metadata CSV; NO electricity time series.

Two input modes: original comma-delimited CSV with actual newlines; normalized
public CSV text returned by a text-extractor that replaced row breaks with spaces
and escaped underscores. Both require exact stable public schema, full row length,
unique numeric site IDs, and no raw power/SOC series columns. This program returns
ONLY anonymous aggregate counts and explicit NO-GO flags.
"""
from __future__ import annotations
import argparse, collections, csv, datetime as dt, hashlib, io, json, math, re
from pathlib import Path

REQUIRED = ('dataid','pv','grid','solar','egauge_1min_min_time',
            'egauge_1min_max_time','egauge_1min_data_availability')
EXTRA = ('battery1','energy_storage_system','energy_storage_system_l1','energy_storage_system_l2','active_record','state')
FORBIDDEN = {'battery_soc_pct','contractual_grid_cap_kw','control_flip_event','load_kw','grid_kw','pv_kw'}
# Record starts recognizable only for the reviewed public metadata 2026-10-25
BUILDING_CLASSES = r'(?:Single-Family|Town Home|Apartment|Commercial|Duplex|Condo|Multi-Family|Mobile Home|Sales|,)'
BOUNDARY = re.compile(r' (?=\d{1,7},(?:yes|no)?,'+BUILDING_CLASSES+r')')
class MetadataError(ValueError): pass

def _parse_one(s: str):
    try: return next(csv.reader([s],strict=True))
    except csv.Error as e: raise MetadataError('CSV_ERROR') from e

def load_public_csv(text: str, mode: str):
    if mode not in {'original','text_extractor_flattened'}: raise MetadataError('BAD_INPUT_MODE')
    if not text or len(text)>26_000_000: raise MetadataError('BAD_INPUT_SIZE')
    if mode=='text_extractor_flattened':
        if '\n' in text.strip() or '\r' in text.strip():raise MetadataError('UNEXPECTED_NEWLINES_IN_FLAT_TEXT')
        parts=BOUNDARY.split(text.replace('\\_','_'))
        if len(parts)<2:raise MetadataError('NO_EXTRACTABLE_RECORDS')
        fields=_parse_one(parts[0]); data=[_parse_one(x) for x in parts[1:]]
    else:
        rows=list(csv.reader(io.StringIO(text),strict=True))
        if len(rows)<2:raise MetadataError('EMPTY_TABLE')
        fields,data=rows[0],rows[1:]
    if len(fields)!=len(set(fields)) or not set(REQUIRED).issubset(fields):raise MetadataError('MISSING_REQUIRED_OR_DUPLICATE_FIELDS')
    if FORBIDDEN.intersection(fields):raise MetadataError('RAW_LIKE_COLUMNS_NOT_PUBLIC_METADATA')
    if any(len(row)!=len(fields) for row in data):raise MetadataError('BAD_ROW_WIDTH')
    result=[dict(zip(fields,row)) for row in data]
    ids=[x['dataid'].strip() for x in result]
    if len(ids)!=len(set(ids)) or not all(re.fullmatch(r'\d{1,7}',x) for x in ids): raise MetadataError('DUPLICATE_OR_INVALID_ID')
    return fields,result

def _one_min(x):
    s=x['egauge_1min_min_time'].strip();e=x['egauge_1min_max_time'].strip()
    if not (s and e):return False
    try:
        # Distinct date-times required but deliberately not inferred to be continuous
        ts=dt.datetime.fromisoformat(re.sub(r'([+-]\d{2})$',r'\1:00',s))
        te=dt.datetime.fromisoformat(re.sub(r'([+-]\d{2})$',r'\1:00',e))
        if ts.utcoffset() is None or te.utcoffset() is None or ts>=te:return False
        a=x['egauge_1min_data_availability'].strip()
        if not a.endswith('%'):return False
        v=float(a[:-1]);return math.isfinite(v) and 0<v<=100
    except (ValueError, TypeError):return False

def screen(text: str, mode: str):
    fields,rows=load_public_csv(text,mode)
    yes=lambda x,k:x.get(k,'').strip().lower()=='yes'
    cand=[x for x in rows if yes(x,'pv') and yes(x,'grid') and yes(x,'solar') and _one_min(x)]
    getpct=lambda x:float(x['egauge_1min_data_availability'].strip()[:-1])
    percent={str(v):sum(getpct(x)>=v for x in cand) for v in (1,50,80,90,95,99,100)}
    extras={k:{'all_public_rows_yes':sum(yes(x,k) for x in rows),
               'within_metadata_candidate_yes':sum(yes(x,k) for x in cand)}
            for k in ('battery1','energy_storage_system','energy_storage_system_l1','energy_storage_system_l2','active_record')}
    states={k:sum(x.get('state','').strip()==k for x in cand) for k in sorted({x.get('state','').strip() for x in cand})}
    return {'schema':'R29_ANONYMIZED_PUBLIC_METADATA_AGGREGATES_V1',
            'row_count':len(rows),'column_count':len(fields),'unique_public_metadata_ids':len(rows),
            'pv_yes':sum(yes(x,'pv') for x in rows),'grid_yes':sum(yes(x,'grid') for x in rows),
            'solar_yes':sum(yes(x,'solar') for x in rows),
            'pv_grid_solar_positive_1min_metadata_candidates':len(cand),
            'candidate_reported_availability_at_least_pct':percent,
            'optional_metadata_fields':extras, 'candidate_state_aggregates':states,
            'original_csv_byte_integrity_confirmed':False if mode=='text_extractor_flattened' else None,
            'actual_joint_measured_grid_pv_SOC_at_same_timestamps':None,
            'battery_chemistry_LFP_proven':False,'contractual_grid_cap_proven':False,
            'controller_flip_action_proven':False,'independent_source_custody_proven':False,
            'approved_r19_R23_experiment':False,'independent_new_TEST':'NO_GO',
            'source_restriction':'PUBLIC_METADATA_ONLY_NO_RAW_HOUSEHOLD_TIME_SERIES',
            'method_note':'Binary circuit flags and 1min-window availability are metadata, not a verified synchronized series.'}

def main():
    p=argparse.ArgumentParser(description='Public provider metadata only; never authorizes new TEST')
    p.add_argument('input');p.add_argument('--mode',choices=['original','text_extractor_flattened'],default='original');p.add_argument('--out',required=True)
    a=p.parse_args(); path=Path(a.input)
    if path.stat().st_size>26_000_000:raise MetadataError('FILE_TOO_LARGE')
    out=screen(path.read_text(encoding='utf-8-sig'),a.mode)
    out['source_input_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    out['sha256_qualifier']='HASH_OF_LOCAL_TEXT_DERIVATIVE_NOT_PROVIDER_ORIGINAL' if a.mode=='text_extractor_flattened' else 'HASH_OF_LOCAL_FILE_NOT_PROVEN_PUBLISHER_ORIGINAL'
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf-8') as f: json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
    print('R29_PUBLIC_METADATA_ONLY_NOGO',out['pv_grid_solar_positive_1min_metadata_candidates'])
if __name__=='__main__':main()
