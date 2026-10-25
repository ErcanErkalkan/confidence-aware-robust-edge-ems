"""CRMT R26: fail-closed metadata/review gate. Never attests source novelty.

No metadata field or caller-supplied reviewer flag can transform candidate status into
real-world TEST approval. Its role is to produce a reproducible *blocked* source
inventory and review checklist while preserving the original R19/R25 constraints.
"""
from __future__ import annotations
import hashlib,json,re,csv,zipfile,datetime as dt
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
SHA_R25='15a1a6aff3ca4410ccad420b261f50480d89d5effb3038a461dab04fb44255bc' # R16 inside R25
R25_ZIP_EXPECTED=hashlib.sha256((ROOT/'reference_inputs/R25_ORIGINAL_EVIDENCE.zip').read_bytes()).hexdigest() if (ROOT/'reference_inputs/R25_ORIGINAL_EVIDENCE.zip').exists() else None
REQUIRED={'candidate_id','source_url','publisher','published','access','license_status','terms','raw_sha256','raw_retrieved','raw_source_audit','previous_exposure_audit','source_independence_attested','physical_schema','sampling_minutes','has_grid_boundary','has_pv','has_load','has_battery_soc','site_level','documented_objective_mapping','data_use_ai_allowed','decision_note','source_evidence'}
ALLOWED_ACCESS={'open','registration_required','restricted','unknown'}
ALLOWED_LICENSE={'verified_permissive','unverified','restricted','prohibited'}
HISTORIC_IDS={'OPENCEM_INTERNAL_2026','OPSD_REPLAY_2026'}
OBJECTIVES=('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day')
class Blocked(ValueError):pass

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def canonical(x:Any)->bytes:return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=True).encode()

def check_reference(zip_path:Path|None=None)->dict:
    target=zip_path or ROOT/'reference_inputs/R25_ORIGINAL_EVIDENCE.zip'
    with zipfile.ZipFile(target) as z:
        ref=z.read('crmt_r25_prospective/reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip')
        if sha(ref)!=SHA_R25:raise Blocked('R16_ORIGINAL_SOURCE_CORRUPTED')
        proto=z.read('crmt_r25_prospective/config/R19_PRIMARY_PROTOCOL_UNCHANGED.json')
        if sha(proto)!='47815ffe56921e11c2272341ce9320e7bd45c9337e1c5cb90cff57dde63a1a88':raise Blocked('R19_CHANGED')
        p=json.loads(proto)
        if p['locked'] is not False or (p['c'],p['a'],p['b'],p['k'])!=(1,1,10,10):raise Blocked('R19_PROTOCOL_NOT_ORIGINAL')
    return {'R16_inside_R25_sha256':sha(ref),'R19_sha256':sha(proto),'R25_container_sha256':sha(target.read_bytes()),'verified_as':'SEEN_HISTORICAL_TRAIN_ONLY'}

def screen(x:dict)->dict:
    if not isinstance(x,dict) or set(x)!=REQUIRED:raise Blocked('INVENTORY_SCHEMA')
    id=x['candidate_id']
    if not isinstance(id,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{2,60}',id):raise Blocked('ID')
    if id in HISTORIC_IDS:raise Blocked('HISTORIC_EXPOSED_NOT_NEW')
    if not isinstance(x['source_url'],str) or not x['source_url'].startswith('https://'):raise Blocked('SOURCE_URL')
    if x['access'] not in ALLOWED_ACCESS or x['license_status'] not in ALLOWED_LICENSE:raise Blocked('ACCESS_OR_LICENSE')
    if x['data_use_ai_allowed'] not in (True,False,None):raise Blocked('TERMS_FLAG')
    numeric=x['sampling_minutes']
    if numeric is not None and (type(numeric) not in (int,float) or numeric<=0):raise Blocked('CADENCE')
    digest=x['raw_sha256']
    if digest is not None and (not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest)):raise Blocked('SHA_FORMAT')
    for k in ('raw_retrieved','raw_source_audit','previous_exposure_audit','source_independence_attested','has_grid_boundary','has_pv','has_load','has_battery_soc','site_level','documented_objective_mapping'):
        if x[k] not in (True,False,None):raise Blocked('EVIDENCE_FIELD_'+k)
    if not isinstance(x['source_evidence'],list) or not x['source_evidence'] or any(not isinstance(v,str) or not v.startswith('https://') for v in x['source_evidence']):raise Blocked('EVIDENCE_URLS')
    reasons=[]
    if x['access']!='open':reasons.append('SOURCE_ACCESS_NOT_OPEN')
    if x['license_status']!='verified_permissive':reasons.append('LICENSE_NOT_ACCEPTED')
    if x['data_use_ai_allowed'] is not True:reasons.append('DATA_USE_IN_THIS_ENV_UNVERIFIED_OR_PROHIBITED')
    if not x['raw_retrieved'] or not digest or not x['raw_source_audit']:reasons.append('RAW_BYTES_AND_CHECKSUM_NOT_VERIFIED')
    if x['previous_exposure_audit'] is not True or x['source_independence_attested'] is not True:reasons.append('INDEPENDENT_EXPOSURE_AND_SOURCE_NOT_ATTESTED')
    if numeric is None or numeric>2:reasons.append('NATIVE_CADENCE_TOO_COARSE_OR_UNKNOWN_FOR_2MIN_CONTROL')
    for k in ('has_grid_boundary','has_pv','has_load','has_battery_soc','documented_objective_mapping','site_level'):
        if x[k] is not True:reasons.append('MISSING_VERIFIED_'+k.upper())
    reasons.append('R25_EXTERNAL_PREREGISTRATION_AND_INDEPENDENT_REVIEW_NOT_VERIFIED')
    # No user-written data, signatures or dates alone unlock this case.
    return {'candidate_id':id,'status':'NO_GO_EXTERNAL_SOURCE_AND_PROTOCOL_EVIDENCE','source_url':x['source_url'],
       'reasons':reasons,'native_cadence_minutes':numeric,'source_downloaded_and_locally_sha_verified':bool(digest and x['raw_retrieved'] and x['raw_source_audit']),
       'raw_sha256':digest,'source_metadata_fingerprint_sha256':sha(canonical(x)),
       'independent_test_eligible':False,'prospective_R19_AUDIT_eligible':False,
       'claim':'PUBLIC_METADATA_REVIEW_NOT_ACTUAL_DATA_ADMISSION'}

def audit_catalog(items:list[dict])->dict:
    if not isinstance(items,list) or len(items)<1:raise Blocked('EMPTY_REGISTRY')
    ids=[x.get('candidate_id') if isinstance(x,dict) else None for x in items]
    if len(set(ids))!=len(ids):raise Blocked('DUPLICATE_CANDIDATE')
    results=[screen(x) for x in items]
    return {'stage':'R26_SOURCE_CANDIDATE_PUBLIC_METADATA_REVIEW','date':'2026-10-25',
     'catalog_sha256':sha(canonical(items)),'candidate_count':len(items),'source_approved_count':0,
     'candidates':results,'historical_excluded_sources':sorted(HISTORIC_IDS),
     'original_r19_B10_unchanged':True,'actual_new_sources_ingested':0,
     'new_independent_test':'NO_GO','prospective_optimization':'NOT_RUN',
     'external_preregistration':'NOT_VERIFIED',
     'disclaimer':'The license, independence, cadence and engineering semantics need independent documentary/raw-byte review; no caller flags can certify these.'}

def verify_raw(file:Path, declared_sha:str)->dict:
    if not re.fullmatch('[0-9a-f]{64}',declared_sha or ''):raise Blocked('DECLARED_SHA_INVALID')
    data=Path(file).read_bytes();actual=sha(data)
    if actual!=declared_sha:raise Blocked('SOURCE_SHA_MISMATCH')
    return {'sha256':actual,'size_bytes':len(data),'status':'HASH_ONLY_NOT_PROVEN_INDEPENDENCE_OR_RIGHTS'}

def reject_prelock_until_external_evidence(register:dict,external_review:dict|None=None)->dict:
    if register.get('source_approved_count') != 0:raise Blocked('CATALOG_STATUS_TAMPER')
    return {'status':'BLOCKED_EXTERNAL_INDEPENDENT_EVIDENCE_REQUIRED',
      'local_catalog_sha256':register['catalog_sha256'],
      'independent_preregistration_verified':False,'external_reviewer_approved':False,
      'new_SOURCE':False,'new_TEST':False,'new_R19_optimizer':False,
      'reason':'No trusted registry, reviewed source rights and genuinely unexposed compatible raw data; self-declared approval does not unlock.'}

def main():
    ref=check_reference();cat=json.loads((ROOT/'config/R26_SOURCE_CANDIDATES.json').read_text())
    result=audit_catalog(cat);result['historical_source_receipt']=ref
    out=ROOT/'results/R26_SOURCE_GATE.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'candidates':len(cat),'approved':0,'historical_referenced':True,'status':'NO_GO'},ensure_ascii=False))
if __name__=='__main__':main()
