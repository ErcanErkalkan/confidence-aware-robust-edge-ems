#!/usr/bin/env python3
"""Fail-closed coverage gate for a future common-block F archive reference.

Does NOT calculate a Pareto result or run the simulator. Historical VALIDATION
can only be exploratory and never counts as independent new TEST.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from collections import defaultdict
from pathlib import Path
OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
EXPECTED={f'CRMT-c{i:04d}' for i in range(1,257)}

def hashfile(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()

def inspect(path,blocks=118,expected_ids=EXPECTED):
 seen=defaultdict(set); counters=defaultdict(int); duplicates=0;invalid=[]; splits=set()
 with Path(path).open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f); cols=reader.fieldnames or []
  missing=sorted(set(['candidate_id','block_id','split',*OBJ])-set(cols))
  if missing: raise ValueError('Missing required columns: '+','.join(missing))
  for row in reader:
   id=row['candidate_id'].strip();bid=row['block_id'].strip();part=row['split'].strip();splits.add(part)
   if not id or not bid or part not in {'train','validation'}:invalid.append((id,bid,'id/block/split'))
   counters[(id,bid)]+=1
   if counters[(id,bid)]>1:duplicates+=1
   seen[id].add(bid)
   try:values=[float(row[o]) for o in OBJ]
   except (ValueError,TypeError): values=[float('nan')]
   if not all(math.isfinite(v) for v in values):invalid.append((id,bid,'objective'))
 present=set(seen)
 common=set.intersection(*map(set,seen.values())) if seen else set()
 union=set().union(*seen.values()) if seen else set()
 status={
  'stage':'FULL256_EQUAL_REFERENCE_PREFLIGHT_ONLY',
  'source_csv_sha256':hashfile(path),'rows':sum(counters.values()),
  'present_controllers':len(present),'required_controllers':len(expected_ids),
  'expected_blocks_per_candidate':int(blocks),'common_blocks':len(common),'union_blocks':len(union),
  'missing_controllers':sorted(expected_ids-present),
  'unexpected_controllers':sorted(present-expected_ids),
  'incomplete_controllers':sorted(id for id,b in seen.items() if len(b)!=blocks or b!=common),
  'duplicate_candidate_block_rows':duplicates,'invalid_rows':len(invalid),
  'split_values':sorted(splits),
  'new_independent_test_authorized':False,
  'claim_boundary':'Eligibility/coverage only. No TRAIN/VAL/TEST optimization or F efficacy outcome.'
 }
 status['eligible_for_manual_reference_review_only']=(present==expected_ids and len(common)==blocks and union==common and
    not status['incomplete_controllers'] and duplicates==0 and not invalid and len(splits)==1 and len(counters)==len(expected_ids)*blocks)
 return status

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--metrics',required=True,type=Path)
 ap.add_argument('--expected-blocks',type=int,default=118)
 a=ap.parse_args()
 if a.expected_blocks<1:raise SystemExit('EXPECTED_BLOCKS_INVALID')
 try:state=inspect(a.metrics,blocks=a.expected_blocks)
 except (ValueError,OSError) as e:print('FULL256_REFERENCE_BLOCKED:',str(e));raise SystemExit(2)
 print(json.dumps(state,indent=2))
 if not state['eligible_for_manual_reference_review_only']:
  print('FULL256_REFERENCE_BLOCKED_INCOMPLETE; NO TEST');raise SystemExit(2)
 print('FULL256_REFERENCE_COVERAGE_PASS_FOR_MANUAL_REVIEW_ONLY; NO TEST')
if __name__=='__main__':main()
