"""CRMT R25: prospective split, evidence-bound selection and anti-leakage guard.

No network, timestamp authority, data acquisition or experiment in this module.
An accepted *signature* proves control of a pinned Ed25519 key, not that the
key belonged to an independent preregistrar or that data were collected after
registration. Every software decision therefore remains REVIEW_REQUIRED.

The R19 legacy score_audit trust in {https URL, boolean} is deliberately never
used as a sufficient seal by the R25 verification path.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

ROOT=Path(__file__).resolve().parents[1]
R19_SHA='47815ffe56921e11c2272341ce9320e7bd45c9337e1c5cb90cff57dde63a1a88'
R16_SOURCE_SHA='15a1a6aff3ca4410ccad420b261f50480d89d5effb3038a461dab04fb44255bc'
R24_RECEIPT_SHA='71d4b9cd13c676a0cd8877c46cc2224c426b3881954aecb2e9f7e7152f709979'
VALID_SEEDS=set(range(2001,2031))
OBJ=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
class Blocked(ValueError):pass

def canonical(obj:Any)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(obj:Any)->str:return hashlib.sha256(canonical(obj)).hexdigest()
def file_sha(path:Path)->str:return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def insist(flag,msg):
    if not flag:raise Blocked(msg)
def parse_iso(raw:str)->dt.datetime:
    insist(isinstance(raw,str),'BAD_TIMESTAMP')
    try:t=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
    except ValueError:raise Blocked('BAD_TIMESTAMP')
    insist(t.tzinfo is not None,'NAIVE_TIMESTAMP_FORBIDDEN')
    return t.astimezone(dt.timezone.utc)
def blockday(raw:str)->dt.date:
    insist(isinstance(raw,str),'BAD_BLOCK_ID')
    seg=raw.split(':')
    insist(len(seg)==3 and seg[0]=='opencem' and seg[1] in ('inv1','inv2'),'BAD_BLOCK_ID')
    try:d=dt.date.fromisoformat(seg[2])
    except ValueError:raise Blocked('BAD_CALENDAR_DAY')
    insist(seg[2]==d.isoformat(),'NONCANONICAL_DAY')
    return d

def assert_reference_source()->dict:
    p=ROOT/'config/R19_PRIMARY_PROTOCOL_UNCHANGED.json'
    s=ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip'
    insist(file_sha(p)==R19_SHA,'R19_SOURCE_CHANGED')
    insist(file_sha(s)==R16_SOURCE_SHA,'R16_HISTORICAL_SOURCE_CHANGED')
    insist(file_sha(ROOT/'reference_snapshot/R24_REAL_TRAIN_BRIDGE.json')==R24_RECEIPT_SHA,'R24_HISTORICAL_RECEIPT_CHANGED')
    protocol=json.loads(p.read_text())
    insist(not protocol['locked'] and protocol['planned_seeds']==list(range(2001,2031)),'HISTORICAL_DESIGN_MUTATED')
    return {'r19_source_sha256':R19_SHA,'r16_original_SHA256':R16_SOURCE_SHA,
            'r19_locked':False,'historical_role':'SEEN_TRAIN_ONLY'}

def historical_coverage()->dict:
    assert_reference_source()
    import r24_source_verifier
    d=json.loads((ROOT/'reference_snapshot/R24_REAL_TRAIN_BRIDGE.json').read_text())
    insist(r24_source_verifier.run()==d,'R24_REPLAY_DOES_NOT_MATCH_SOURCE_RECEIPT')
    rows=[]
    for item in d['rows']:
        days=item['global_complete_two_inverter_days_256']
        insist(item['source_raw_SHA_verified'] and item['paired_objectives_match'] and item['n_candidate_block_events']==12600,'BAD_SOURCE_RECEIPT')
        rows.append({'historical_seed':item['seed'],'observed_full_common_days':days,
                     'minimum_planned_audit_days':30,'day_shortfall_vs_planned':max(0,30-days),
                     'B10_shared':item['B10_shared'],'source_role':'SEEN_TRAIN_ONLY',
                     'r19_prospective_run_eligible':False})
    insist([x['observed_full_common_days'] for x in rows]==[9,5,5],'R24_HISTORICAL_RECEIPT_CHANGED')
    return {'status':'DESCRIPTIVE_SEEN_TRAIN_NOT_PROSPECTIVE','rows':rows,
            'future_30_seed_AUDIT_eval_count':256*60*30,
            'future_30_seed_DISCOVERY_eval_count_per_arm':12600*30,
            'r19_locked':False,'new_TEST':'NO_GO'}

def _blocks_complete(blocks:list[str],n_days:int,groupname:str)->set[dt.date]:
    insist(isinstance(blocks,list) and len(blocks)==2*n_days and len(set(blocks))==len(blocks),groupname+'_BLOCK_COUNT')
    days={}
    for bid in blocks:
        day=blockday(bid)
        days.setdefault(day,set()).add(bid.split(':')[1])
    insist(len(days)==n_days and all(x=={'inv1','inv2'} for x in days.values()),groupname+'_PAIRED_DAYS')
    return set(days)

def create_split_reservation(req:dict)->dict:
    """Data-free split reservation: no losses or result file names accepted.

    The caller must supply an externally sourced and authenticated block inventory.
    This function checks only its internal date/split consistency.
    """
    keys={'role','source_id','seed','candidate_ids','discovery_block_ids','audit_block_ids','embargo_days','source_inventory_sha256','source_exposure'}
    insist(isinstance(req,dict) and set(req)==keys,'RESERVATION_SCHEMA_OR_OUTCOMES_PRESENT')
    insist(req['role']=='NEW_SOURCE_RESERVATION_UNVERIFIED','HISTORICAL_OR_MISLABELED_SOURCE')
    insist(req['source_exposure']=='CLAIMED_UNEXPOSED_NOT_INDEPENDENTLY_CHECKED','SOURCE_EXPOSURE_FALSE_CERTIFICATION')
    insist(type(req['seed']) is int and req['seed'] in VALID_SEEDS,'SEED_NOT_IN_R19')
    insist(isinstance(req['source_id'],str) and len(req['source_id'])>=10,'SOURCE_ID_REQUIRED')
    insist(isinstance(req['source_inventory_sha256'],str) and bool(re.fullmatch(r'[0-9a-f]{64}',req['source_inventory_sha256'])),'INVENTORY_SHA')
    ids=req['candidate_ids']
    insist(isinstance(ids,list) and len(ids)==256 and len(set(ids))==256 and all(isinstance(v,str) and v and v.strip()==v for v in ids),'CANDIDATE_POOL_256')
    insist(type(req['embargo_days']) is int and 7<=req['embargo_days']<=180,'EMBARGO_NOT_JUSTIFIED_7_DAY_MINIMUM')
    insist(isinstance(req['discovery_block_ids'],list),'DISCOVERY_BLOCK_SCHEMA')
    disc=_blocks_complete(req['discovery_block_ids'],len(req['discovery_block_ids'])//2,'DISCOVERY')
    audit=_blocks_complete(req['audit_block_ids'],30,'AUDIT')
    insist(not disc&audit,'DISCOVERY_AUDIT_SAME_DAY_LEAK')
    insist(min(audit)>max(disc),'AUDIT_MUST_FOLLOW_DISCOVERY')
    gap=(min(audit)-max(disc)).days-1
    insist(gap>=req['embargo_days'],'EMBARGO_TOO_SHORT')
    plan={'status':'SPLIT_RESERVED_LOCALLY_EXTERNAL_SOURCE_AND_PRELOCK_UNVERIFIED',
          'seed':req['seed'],'source_id':req['source_id'],
          'source_inventory_sha256':req['source_inventory_sha256'],
          'source_exposure':req['source_exposure'],'embargo_full_days':gap,
          'discovery_first_day':min(disc).isoformat(),'discovery_last_day':max(disc).isoformat(),
          'audit_first_day':min(audit).isoformat(),'audit_last_day':max(audit).isoformat(),
          'candidate_ids':sorted(ids),'discovery_block_ids':sorted(req['discovery_block_ids']),
          'audit_block_ids':sorted(req['audit_block_ids']),
          'expected_AUDIT_evaluations':256*60,'original_r19_protocol_sha256':R19_SHA,
          'original_r19_locked':False,
          'independent_source_attestation_verified':False,
          'physical_safety_approved':False,'is_new_TEST':False}
    plan['reservation_sha256']=digest(plan)
    return plan

def lock_receipt_envelope(lock:dict,plan:dict)->dict:
    """Only a *request* for external attestation; cannot sign itself."""
    insist(isinstance(lock,dict) and isinstance(plan,dict),'MISSING_INPUT')
    seal=lock.get('selection_lock_sha256')
    insist(isinstance(seal,str),'R19_SELECTION_LOCK_MISSING')
    unsigned={k:v for k,v in lock.items() if k!='selection_lock_sha256'}
    insist(digest(unsigned)==seal,'R19_LOCK_TAMPERED')
    reservation=plan.get('reservation_sha256')
    insist(isinstance(reservation,str) and digest({k:v for k,v in plan.items() if k!='reservation_sha256'})==reservation,'SPLIT_PLAN_TAMPERED')
    insist(lock['seed']==plan['seed'],'SEED_MISMATCH')
    insist(lock['protocol_sha256']==digest(json.loads((ROOT/'config/R19_PRIMARY_PROTOCOL_UNCHANGED.json').read_text())),'PROTOCOL_MISMATCH')
    insist(sorted(lock['candidate_ids'])==plan['candidate_ids'],'CANDIDATE_MISMATCH')
    insist(sorted(lock['audit_block_ids'])==plan['audit_block_ids'],'AUDIT_BLOCK_MISMATCH')
    # Discovery evidence cannot be replaced after the two locks are bound.
    insist(lock['source_manifest_sha256']==plan['source_inventory_sha256'],'SOURCE_MANIFEST_MISMATCH')
    return {'schema':'R25_ED25519_SIGNATURE_REQUEST_V1','selection_lock_sha256':seal,
            'split_reservation_sha256':reservation,'original_protocol_sha256':R19_SHA,
            'run_git_sha':lock['run_git_sha'],'source_inventory_sha256':plan['source_inventory_sha256']}

def verify_external_signature(envelope:dict,receipt:dict,pinned_public_key_hex:str|None)->dict:
    """Do not infer independence from a valid user-supplied signature or timestamp."""
    insist(isinstance(envelope,dict) and envelope.get('schema')=='R25_ED25519_SIGNATURE_REQUEST_V1','BAD_ENVELOPE')
    if not pinned_public_key_hex:
        return {'status':'BLOCKED_NO_INDEPENDENT_ATTESTOR_PUBLIC_KEY_PINNED','signature_verified':False,
                'independent_attestor_identity_approved':False,'audit_can_run_confirmatory':False}
    insist(isinstance(receipt,dict) and set(receipt)=={'envelope_sha256','attestor_claim','registered_at','external_artifact_url','signature_hex'},'SIGNED_RECEIPT_SCHEMA')
    insist(receipt['envelope_sha256']==digest(envelope),'EXTERNAL_LOCK_HASH_MISMATCH')
    insist(isinstance(pinned_public_key_hex,str) and bool(re.fullmatch('[0-9a-f]{64}',pinned_public_key_hex)),'PINNED_KEY_HEX')
    insist(isinstance(receipt['signature_hex'],str) and bool(re.fullmatch('[0-9a-f]{128}',receipt['signature_hex'])),'SIGNATURE_HEX')
    insist(isinstance(receipt['external_artifact_url'],str) and receipt['external_artifact_url'].startswith('https://'),'EXTERNAL_ARTIFACT_URL')
    insist(isinstance(receipt['attestor_claim'],str) and len(receipt['attestor_claim'])>=8,'ATTESTOR_CLAIM_MISSING')
    parse_iso(receipt['registered_at'])
    signed={k:v for k,v in receipt.items() if k!='signature_hex'}
    try:Ed25519PublicKey.from_public_bytes(bytes.fromhex(pinned_public_key_hex)).verify(bytes.fromhex(receipt['signature_hex']),canonical(signed))
    except (InvalidSignature,ValueError):raise Blocked('SIGNATURE_INVALID')
    return {'status':'SIGNATURE_VALID_INDEPENDENT_CUSTODY_AND_TIMING_STILL_REQUIRE_EXTERNAL_REVIEW',
            'signature_verified':True,'receipt_content_sha256':digest(signed),
            'pinned_public_key_fingerprint_sha256':hashlib.sha256(bytes.fromhex(pinned_public_key_hex)).hexdigest(),
            'independent_attestor_identity_approved':False,
            'audit_can_run_confirmatory':False,
            'new_blind_TEST':'NO_GO',
            'warning':'Signature alone does not prove identity independence, historical timing, actual source acquisition or data nonexposure.'}

def local_gate_report()->dict:
    x=historical_coverage()
    return {'stage':'R25_PROSPECTIVE_HARDENING','date':'2026-10-25',
            'historical_seen_data_status':x['status'],'historical_day_shortfalls':[r['day_shortfall_vs_planned'] for r in x['rows']],
            'old_R19_score_audit_self_declared_receipt':'NOT_A_TRUSTED_INDEPENDENT_SEAL',
            'r25_pinned_independent_attestor_key':None,'external_pre_registration':'NOT_VERIFIED',
            'independent_source_catalog':'NOT_RECEIVED',
            'new_2001_2030_runs':'NOT_RUN','new_AUDIT_events':'NONE',
            'r23_field_certification':'NO_GO', 'r19_confirmatory_result':'NO_GO',
            'blinded_independent_TEST':'NO_GO','hardware_deployment':'NO_GO',
            'R19_B10_unchanged':True,
            'next_required_action':'Independent source inventory and approved preregistration before new optimizer runs.'}

if __name__=='__main__':
    out=ROOT/'results/R25_REAL_SOURCE_GATES.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(local_gate_report(),indent=2,ensure_ascii=False)+'\n')
    print('BLOCKED_EXTERNAL_EVIDENCE: '+str(out))
