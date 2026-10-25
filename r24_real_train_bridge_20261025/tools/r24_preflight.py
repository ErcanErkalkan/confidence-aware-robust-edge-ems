"""R24 prospective TRAIN-AUDIT shape and split audit.

A schema check is not an authenticated source provenance, ex-ante experiment
registration, independent TEST, finite-m theorem witness or deployment approval.
"""
from __future__ import annotations
import datetime as dt
import hashlib,json,math
from collections import Counter

OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')

class PreflightBlocked(ValueError):pass

def _date_and_inverter(block_id):
    p=block_id.split(':')
    if len(p)!=3 or p[0]!='opencem' or p[1] not in ('inv1','inv2'):
        raise PreflightBlocked('INVALID_BLOCK_ID')
    try:day=dt.date.fromisoformat(p[2])
    except ValueError:raise PreflightBlocked('INVALID_DAY')
    return day,p[1]

def validate_planned_audit(payload:dict)->dict:
    """Validate complete candidate×60 block shape, but do not claim an actual experiment.

    No external receipt can be self-certified by this input. The returned status
    is PLAN_SHAPE_ONLY even if all rows are present and hash-consistent.
    """
    if not isinstance(payload,dict) or set(payload)!= {'role','seed','candidate_ids','discovery_block_ids','audit_block_ids','audit_rows'}:
        raise PreflightBlocked('INVALID_SCHEMA')
    if payload['role']!='HYPOTHETICAL_PROSPECTIVE_TRAIN_AUDIT_DRY_RUN':
        raise PreflightBlocked('DISALLOWED_SOURCE_ROLE')
    if type(payload['seed'])!=int or payload['seed'] not in range(2001,2031):
        raise PreflightBlocked('SEED_NOT_IN_DRAFT')
    ids=payload['candidate_ids']; disc=payload['discovery_block_ids']; blocks=payload['audit_block_ids']
    if not isinstance(ids,list) or len(ids)!=256 or len(set(ids))!=256 or not all(isinstance(x,str) and x for x in ids):
        raise PreflightBlocked('CANDIDATE_POOL_NOT_256')
    if not isinstance(disc,list) or not isinstance(blocks,list) or len(blocks)!=60 or len(set(blocks))!=60 or not disc or len(set(disc))!=len(disc):
        raise PreflightBlocked('BLOCK_SPLIT_SCHEMA')
    if set(disc)&set(blocks):raise PreflightBlocked('BLOCK_LEAKAGE')
    dd,aa={},{}
    for b in disc:
        day,inv=_date_and_inverter(b);dd.setdefault(day,set()).add(inv)
    for b in blocks:
        day,inv=_date_and_inverter(b);aa.setdefault(day,set()).add(inv)
    if set(dd)&set(aa):raise PreflightBlocked('SAME_DAY_SPLIT_LEAKAGE')
    if len(aa)!=30 or any(v!={'inv1','inv2'} for v in aa.values()):
        raise PreflightBlocked('AUDIT_NEEDS_30_TWO_INVERTER_DAYS')
    rows=payload['audit_rows'];
    if not isinstance(rows,list) or len(rows)!=15360:raise PreflightBlocked('INCOMPLETE_AUDIT_CANDIDATE_EVENTS')
    id_set=set(ids); block_set=set(blocks);found=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'candidate_id','block_id','losses'}:
            raise PreflightBlocked('AUDIT_ROW_SCHEMA')
        k=(row['candidate_id'],row['block_id']); loss=row['losses']
        if k[0] not in id_set or k[1] not in block_set or k in found:
            raise PreflightBlocked('DUPLICATE_OR_UNKNOWN_AUDIT_ROW')
        if not isinstance(loss,dict) or set(loss)!=set(OBJ) or not all(type(x) in (float,int) and math.isfinite(x) for x in loss.values()):
            raise PreflightBlocked('NONFINITE_OR_MISSING_OBJECTIVE')
        found.add(k)
    if len(found)!=256*60:raise PreflightBlocked('GRID_NOT_COMPLETE')
    checksum=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return {'status':'PLAN_SHAPE_VALID_EXTERNAL_EVIDENCE_STILL_REQUIRED',
            'role':'HYPOTHETICAL_DRY_RUN_NOT_NEW_REAL_AUDIT',
            'local_payload_sha256':checksum,'seed':payload['seed'],
            'candidate_n':len(ids),'audit_block_n':len(blocks),'audit_day_n':len(aa),
            'audit_events_n':len(rows),'discovery_and_audit_days_disjoint':True,
            'external_immutable_pre_registration_verified':False,
            'actual_prospective_source_SHA_verified':False,
            'stationarity_proven':False,'finite_m_proven':False,
            'r23_certificate_eligible':False,
            'physical_deployment_authorized':False,
            'warning':'A syntactically valid ledger can be fabricated; time-of-creation, real data collection, independence and prospective lock require external verification.'}

def synthetic_planning_fixture()->dict:
    """Small in-memory generate *form* of 15360 rows; NEVER observational evidence."""
    ids=[f'PLAN_ONLY_c{i:04d}' for i in range(256)]
    disc=[f'opencem:inv1:2025-06-{i:02d}' for i in range(1,6)]
    blocks=[f'opencem:inv{v}:2027-01-{day:02d}' for day in range(1,31) for v in (1,2)]
    losses={obj:0.0 for obj in OBJ}
    return {'role':'HYPOTHETICAL_PROSPECTIVE_TRAIN_AUDIT_DRY_RUN','seed':2001,
            'candidate_ids':ids,'discovery_block_ids':disc,'audit_block_ids':blocks,
            'audit_rows':[{'candidate_id':c,'block_id':b,'losses':losses.copy()} for c in ids for b in blocks]}

if __name__=='__main__':
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser(description='Prospective AUDIT SHAPE dry run, not a real data registration')
    p.add_argument('--dry-run',action='store_true',help='synthetic 15360-row schema example only')
    p.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'results/R24_PREFLIGHT_DRY_RUN.json')
    args=p.parse_args()
    if not args.dry_run:raise SystemExit('Specify --dry-run; no actual source verified in this prototype')
    result=validate_planned_audit(synthetic_planning_fixture())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print(result['status'],result['audit_events_n'],'never deploy')
