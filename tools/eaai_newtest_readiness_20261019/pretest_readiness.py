#!/usr/bin/env python3
"""Metadata-only, fail-closed eligibility preflight; never evaluates TEST outcomes.

No writes. An ELIGIBLE_FOR_MANUAL_REVIEW verdict is NOT permission to claim
that a blind test has been registered, executed, or scientifically valid.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

HEX64 = re.compile(r'^[0-9a-f]{64}$')
REQUIRED_CSV = ('block_id', 'source_family', 'dataset_version', 'site_id', 'start_utc', 'end_utc', 'split', 'raw_sha256')
REQUIRED_META = ('dataset_name', 'dataset_version', 'source_family', 'source_url', 'license',
                 'site_id', 'timezone', 'sampling_seconds', 'measurement_units',
                 'physical_objectives_supported', 'adapter_version', 'previously_inspected_outcomes',
                 'embargo_hours', 'raw_files', 'prior_external_inventory_complete')

class GateError(Exception):
    pass

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def check(cond, msg):
    if not cond:
        raise GateError(msg)

def dt(value):
    s = value.strip()
    check(s.endswith('Z'), f'UTC timestamp must end in Z: {s!r}')
    try:
        v = datetime.fromisoformat(s[:-1] + '+00:00')
    except (ValueError, TypeError) as e:
        raise GateError(f'Invalid UTC timestamp {s!r}') from e
    check(v.utcoffset() == timedelta(0), 'Timestamp not UTC')
    return v

def inventory(path, expected_split):
    with Path(path).open('r', newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        check(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)),
              'Missing or duplicate inventory headers')
        check(set(REQUIRED_CSV).issubset(reader.fieldnames), 'Missing inventory columns: ' +
              str(sorted(set(REQUIRED_CSV) - set(reader.fieldnames))))
        rows = list(reader)
    check(rows, f'Empty {expected_split} inventory')
    ids=set(); out=[]
    for row in rows:
        bid=row['block_id'].strip()
        check(bool(bid) and bid not in ids, f'Duplicate/empty block ID: {bid}')
        ids.add(bid)
        for field in ('source_family','dataset_version','site_id','split'):
            check(bool(row[field].strip()), f'Empty {field} at {bid}')
        if expected_split:
            check(row['split']=='new_test',f'Non-new_test row: {bid}')
        else:
            check(row['split'] in ('train', 'validation', 'internal_test', 'historical_external'),
                  f'Invalid historical split: {bid}')
        start,end=dt(row['start_utc']),dt(row['end_utc'])
        check(start < end, f'Invalid window ordering: {bid}')
        digest=row['raw_sha256'].strip().lower()
        check(bool(HEX64.fullmatch(digest)),f'Invalid raw sha256: {bid}')
        out.append(dict(row, block_id=bid, start=start, end=end, raw_sha256=digest))
    return out

def make_report(meta_path, proposed_path, history_path, raw_root, expected_history_sha,
                counts=(210,118,78), require_external=True):
    check(bool(HEX64.fullmatch(str(expected_history_sha).lower())),
          'Provide previously frozen expected_history_sha256, not a computed new hash')
    hhash=sha(history_path)
    check(hhash==expected_history_sha.lower(), 'Historical registry hash mismatch')
    history=inventory(history_path, expected_split=False)
    counts_actual=Counter(r['split'] for r in history)
    for split,n in zip(('train','validation','internal_test'), counts):
        check(counts_actual[split]==n,f'Expected {n} {split} rows, got {counts_actual[split]}')
    if require_external:
        check(counts_actual['historical_external'] > 0, 'Missing historical OPSD/external exposure registry')
    meta=json.loads(Path(meta_path).read_text(encoding='utf-8'))
    check(isinstance(meta,dict),'Manifest must be an object')
    for field in REQUIRED_META:
        check(field in meta, f'Missing provenance field: {field}')
    for field in ('dataset_name','dataset_version','source_family','source_url','license','site_id',
                  'timezone','adapter_version'):
        check(isinstance(meta[field],str) and meta[field].strip() and
              'TODO' not in meta[field].upper() and meta[field].lower() not in ('unknown','tbd','none'),
              f'Provenance not frozen: {field}')
    check(meta['timezone'] in ('UTC','Etc/UTC') or '/' in meta['timezone'], 'Invalid named timezone')
    check(type(meta['sampling_seconds']) is int and meta['sampling_seconds']>0, 'Invalid sampling seconds')
    check(type(meta['embargo_hours']) is int and meta['embargo_hours']>=0,
          'Invalid embargo hours')
    check(meta['previously_inspected_outcomes'] is False,
          'New data outcomes have already been inspected: no blind status')
    check(meta['prior_external_inventory_complete'] is True,
          'Prior external exposure completeness has not been attested')
    units=meta['measurement_units']
    check(isinstance(units,dict) and all(isinstance(v,str) and v.strip() for v in units.values())
          and {'pv','load','battery','soc','grid'}.issubset(units), 'Incomplete physical unit dictionary')
    objectives=meta['physical_objectives_supported']
    needed=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
    check(isinstance(objectives,dict) and all(objectives.get(k) is True for k in needed),
          'All four objectives and measurement adapters must be supported')
    raws=meta['raw_files']
    check(isinstance(raws,list) and raws, 'No raw files in manifest')
    root=Path(raw_root).resolve()
    digests=set(); paths=set()
    for item in raws:
        check(isinstance(item,dict) and {'path','sha256'}<=item.keys(),
              'Raw file must give relative path and sha256')
        p=Path(item['path'])
        check(not p.is_absolute() and '..' not in p.parts,
              'Raw file reference must be relative and cannot traverse parents')
        final=(root/p).resolve()
        check(final.is_relative_to(root), 'Symlink escapes raw root')
        check(final.is_file(), f'Raw file absent: {item["path"]}')
        check(item['path'] not in paths,'Repeated raw file path')
        paths.add(item['path'])
        digest=str(item['sha256']).lower()
        check(bool(HEX64.fullmatch(digest)), 'Invalid raw-file sha256')
        check(sha(final)==digest, f'Raw SHA256 mismatch: {item["path"]}')
        digests.add(digest)
    proposed=inventory(proposed_path,expected_split=True)
    hist_ids={r['block_id'] for r in history}
    hist_raw={r['raw_sha256'] for r in history}
    check(digests.isdisjoint(hist_raw), 'Proposed raw bytes reused from prior evidence')
    for row in proposed:
        check(row['block_id'] not in hist_ids,'Historical block ID reused: '+row['block_id'])
        for k in ('source_family','dataset_version','site_id'):
            check(row[k]==meta[k], f'Metadata mismatch for {k}: {row["block_id"]}')
        check(row['raw_sha256'] in digests, 'Unknown raw hash for block '+row['block_id'])
    guard=timedelta(hours=meta['embargo_hours'])
    for row in proposed:
        for old in history:
            if (row['source_family'].casefold(), row['site_id'].casefold()) != (old['source_family'].casefold(),old['site_id'].casefold()):
                continue
            check(row['end']+guard <= old['start'] or old['end']+guard <= row['start'],
                  f'Leakage or embargo overlap: {row["block_id"]} / {old["block_id"]}')
    grouped={}
    for row in proposed:
        key=(row['source_family'].casefold(),row['site_id'].casefold())
        grouped.setdefault(key,[]).append(row)
    for rows in grouped.values():
        for prev,cur in zip(sorted(rows,key=lambda z:z['start']),sorted(rows,key=lambda z:z['start'])[1:]):
            check(prev['end'] <= cur['start'], 'Proposed blocks overlap: '+prev['block_id']+' / '+cur['block_id'])
    return {'status':'ELIGIBLE_FOR_MANUAL_REVIEW_ONLY','test_performance':'NOT_COMPUTED',
            'independent_blind_test':'NOT_YET_AUTHORIZED','history_sha256':hhash,
            'manifest_sha256':sha(meta_path),'proposed_inventory_sha256':sha(proposed_path),
            'historic_windows':len(history),'historic_split_counts':dict(counts_actual),
            'proposed_windows':len(proposed),'raw_files_hashed':len(raws),'embargo_hours':meta['embargo_hours'],
            'warnings':['Metadata checks cannot prove access history, calibration, physical simulator compatibility or external site independence.',
                        'Do not run TEST without frozen selection, normalization and out-of-range policy.']}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',required=True)
    ap.add_argument('--proposed-windows',required=True)
    ap.add_argument('--historical-windows',required=True)
    ap.add_argument('--raw-root',required=True)
    ap.add_argument('--expected-history-sha256',required=True)
    args=ap.parse_args()
    try:
        result=make_report(args.manifest,args.proposed_windows,args.historical_windows,
                           args.raw_root,args.expected_history_sha256)
    except (GateError,ValueError,OSError,KeyError,TypeError,UnicodeError,json.JSONDecodeError) as ex:
        print('NEW_TEST_GATE_BLOCKED:',str(ex))
        raise SystemExit(2)
    print(json.dumps(result,indent=2,sort_keys=True))
    print('NEW_TEST_METADATA_PREFLIGHT_PASS_ONLY; NO TEST SCORES COMPUTED')

if __name__=='__main__': main()
