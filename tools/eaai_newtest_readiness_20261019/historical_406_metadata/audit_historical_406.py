#!/usr/bin/env python3
"""Integrity-bound OpenCEM window inventory builder. Metadata-only; not a TEST gate."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

EXPECTED_SHA = '3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1'
SOURCE_COMMIT = '5884d253a5267fb240b7a8df6fa9e4d49a905167'
EXPECTED_SPLITS = {'train': 210, 'validation': 118, 'internal_test': 78}
FIELDS = ('block_id','source_family','dataset_version','site_id','start_utc','end_utc_exclusive',
          'split','original_timestamp_utc_max','n_ticks','cadence_minutes','raw_file_sha256_status')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''):
            h.update(part)
    return h.hexdigest()


def timestamp(txt):
    t = datetime.fromisoformat(txt.replace('Z','+00:00'))
    if t.tzinfo is None or t.utcoffset() != timedelta(0):
        raise ValueError(f'Timestamp lacks UTC offset: {txt!r}')
    return t.astimezone(timezone.utc)


def build(source, out_dir):
    source = Path(source)
    if sha256(source) != EXPECTED_SHA:
        raise ValueError('Canonical manifest SHA-256 mismatch; nothing written')
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f)
        required={'block_id','inverter_id','local_date','split','cadence_minutes',
                  'n_ticks','timestamp_utc_min','timestamp_utc_max','source_commit'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError('Canonical fields missing')
        rows=list(reader)
    if len(rows)!=406 or Counter(r['split'] for r in rows)!=EXPECTED_SPLITS:
        raise ValueError('Block inventory split/count mismatch')
    if len({r['block_id'] for r in rows})!=406 or any(not r['block_id'] for r in rows):
        raise ValueError('Duplicate/empty block ID')
    out=[]
    groups={}
    for r in rows:
        if r['source_commit']!=SOURCE_COMMIT:
            raise ValueError('Source commit mismatch')
        cadence=int(r['cadence_minutes'])
        n=int(r['n_ticks'])
        if cadence!=2 or n<=0 or n>720:
            raise ValueError('Bad cadence or tick count')
        start=timestamp(r['timestamp_utc_min'])
        last=timestamp(r['timestamp_utc_max'])
        end=last+timedelta(minutes=cadence)
        if not start<=last or n>int((end-start).total_seconds()/(60*cadence)):
            raise ValueError('Bad start/end or coverage')
        if r['inverter_id'] not in ('1','2'):
            raise ValueError('Unexpected inverter identifier; revise only with frozen source evidence')
        item={
            'block_id':r['block_id'],
            'source_family':'OpenCEM-platform/opencem-dataset',
            'dataset_version':SOURCE_COMMIT,
            'site_id':'opencem_inv'+r['inverter_id'],
            'start_utc':start.isoformat().replace('+00:00','Z'),
            'end_utc_exclusive':end.isoformat().replace('+00:00','Z'),
            'split':r['split'],
            'original_timestamp_utc_max':r['timestamp_utc_max'],
            'n_ticks':n,
            'cadence_minutes':cadence,
            'raw_file_sha256_status':'UNRESOLVED_NOT_IN_CANONICAL_BLOCK_MANIFEST'
        }
        out.append(item)
        groups.setdefault(item['site_id'],[]).append((start,end,r['block_id']))
    for site,intervals in groups.items():
        ints=sorted(intervals)
        for a,b in zip(ints,ints[1:]):
            if a[1]>b[0]:
                raise ValueError(f'Overlapping distinct blocks for {site}: {a[2]} / {b[2]}')
    out.sort(key=lambda x:(x['split'],x['site_id'],x['start_utc'],x['block_id']))
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest=out_dir/'HISTORICAL_406_WINDOWS_METADATA_ONLY.csv'
    if dest.exists() or (out_dir/'HISTORICAL_406_AUDIT_STATUS.json').exists():
        raise FileExistsError('Output already exists; no overwrite')
    with dest.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f, fieldnames=FIELDS,lineterminator='\n')
        w.writeheader()
        w.writerows(out)
    intervals_by_split={}
    for k in EXPECTED_SPLITS:
        subset=[r for r in out if r['split']==k]
        intervals_by_split[k]={ 'blocks':len(subset),
          'earliest_start_utc':min(r['start_utc'] for r in subset),
          'latest_end_utc_exclusive':max(r['end_utc_exclusive'] for r in subset)}
    status={
      'protocol':'CRMT-EAAI-OPEN_CEM-406-HISTORICAL-WINDOWS-ONLY-20261020-v1',
      'canonical_source_sha256':EXPECTED_SHA,
      'canonical_source_commit':SOURCE_COMMIT,
      'input_provenance':'canonical OpenCEM 406-row manifest; provider file hashes absent from its columns',
      'metadata_inventory_sha256':sha256(dest),
      'row_count':len(out),
      'split_counts':dict(Counter(r['split'] for r in out)),
      'coverage_by_split':intervals_by_split,
      'inverter_ids':sorted(groups),
      'end_utc_method':'last observed tick + frozen 2-minute cadence; half-open bounds',
      'known_missing':['block_to_raw_sha256_mapping','complete prior OPSD/external exposure windows',
                      'verified independent NEW TEST raw inputs, physical adapter, and eligibility decision'],
      'dataset_eligibility':'BLOCKED',
      'new_blind_test':'NOT_RUN',
      'WARNING':'This CSV intentionally lacks raw_sha256 and is NOT a valid pretest_readiness.py historical registry.'
    }
    (out_dir/'HISTORICAL_406_AUDIT_STATUS.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return status

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--canonical',required=True)
    p.add_argument('--output-dir',required=True)
    a=p.parse_args()
    result=build(a.canonical,a.output_dir)
    print('HISTORICAL_406_METADATA_AUDIT_PASS blocks=406 split=210,118,78; NEW_TEST_BLOCKED')
    print('METADATA_CSV_SHA256 '+result['metadata_inventory_sha256'])
