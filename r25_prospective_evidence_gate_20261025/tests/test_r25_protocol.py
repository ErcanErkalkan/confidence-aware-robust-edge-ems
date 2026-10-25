"""R25 negative-control tests: fail closed without independent source evidence."""
import copy, datetime as dt, hashlib, json, sys
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'reference_snapshot'))
from r25_protocol_gate import (Blocked,R19_SHA,R16_SOURCE_SHA,canonical,digest,assert_reference_source,
    historical_coverage,create_split_reservation,lock_receipt_envelope,verify_external_signature,
    local_gate_report,blockday)
from primary_hypothesis_R19 import selection_lock,score_audit

@pytest.fixture(scope='module')
def fixture():
    ids=[f'CRMT-c{i:04d}' for i in range(256)]
    discovery=[f'opencem:inv{inv}:2027-01-{day:02d}' for day in range(1,26) for inv in (1,2)]
    audit=[f'opencem:inv{inv}:{(dt.date(2027,2,2)+dt.timedelta(days=day)).isoformat()}' for day in range(30) for inv in (1,2)]
    sha=hashlib.sha256(b'UNVERIFIED_NEW_SOURCE_INVENTORY').hexdigest()
    req=dict(role='NEW_SOURCE_RESERVATION_UNVERIFIED',source_id='new_dataset_NOT_YET_ATTESTED',seed=2001,
             candidate_ids=ids,discovery_block_ids=discovery,audit_block_ids=audit,
             embargo_days=7,source_inventory_sha256=sha,source_exposure='CLAIMED_UNEXPOSED_NOT_INDEPENDENTLY_CHECKED')
    plan=create_split_reservation(req)
    blocks=[{'block_id':x,'group_id':x.rsplit(':',1)[-1],'split':('DISCOVERY' if x in discovery else 'AUDIT')} for x in discovery+audit]
    # 256*49 + 56 = 12600; every controller has 49-50 discovery records.
    pairs=[[cid,discovery[b]] for b in range(49) for cid in ids]+[[cid,discovery[49]] for cid in ids[:56]]
    by={cid:{} for cid in ids}
    for cid,bid in pairs:
        index=int(cid[-4:]);by[cid][bid]=[1+index*.0001,2+index*.0001,3+index*.0001,4+index*.0001]
    lock_input=dict(seed=2001,run_git_sha='a'*40,source_manifest_sha256=sha,
        candidate_ids=ids,blocks=blocks,archives={'F0':ids[:20],'F1':ids[:6]+ids[-30:]},
        discovery_objectives=by,evaluation_pairs={'F0':pairs,'F1':pairs})
    conf=json.loads((ROOT/'config/R19_PRIMARY_PROTOCOL_UNCHANGED.json').read_text())
    lock=selection_lock(conf,lock_input)
    envelope=lock_receipt_envelope(lock,plan)
    return req,plan,lock,envelope,conf

@pytest.fixture(scope='module')
def signer():
    # Ephemeral TEST-ONLY key: never pinned for the real study.
    k=Ed25519PrivateKey.generate()
    pub=k.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw).hex()
    return k,pub

def signed_receipt(envelope,k):
    receipt={'envelope_sha256':digest(envelope),'attestor_claim':'TEST_ONLY_UNTRUSTED',
             'registered_at':'2026-10-25T08:00:00+03:00','external_artifact_url':'https://example.org/test-not-a-register'}
    receipt['signature_hex']=k.sign(canonical(receipt)).hex()
    return receipt

def test_01_exact_historical_sources():
    z=assert_reference_source();assert z['r19_source_sha256']==R19_SHA and z['r16_original_SHA256']==R16_SOURCE_SHA

def test_02_historical_days_and_no_fake_audit():
    r=historical_coverage()
    assert [x['observed_full_common_days'] for x in r['rows']]==[9,5,5]
    assert [x['day_shortfall_vs_planned'] for x in r['rows']]==[21,25,25]
    assert all(not x['r19_prospective_run_eligible'] for x in r['rows'])

def test_03_new_source_reservation_is_never_approved(fixture):
    _,p,_,_,_=fixture
    assert p['status'].startswith('SPLIT_RESERVED_LOCALLY_')
    assert p['independent_source_attestation_verified'] is False
    assert p['original_r19_locked'] is False

def test_04_complete_date_pairs_held_out(fixture):
    _,p,_,_,_=fixture
    assert p['embargo_full_days']==7 and p['expected_AUDIT_evaluations']==15360
    assert p['audit_first_day']=='2027-02-02' and p['audit_last_day']=='2027-03-03'

def test_05_lock_matches_r19_unmodified(fixture):
    _,p,l,e,_=fixture
    assert e['selection_lock_sha256']==l['selection_lock_sha256']
    assert l['B']==10 and l['F0_selected_ids']!=l['F1_selected_ids']
    assert e['split_reservation_sha256']==p['reservation_sha256']

def test_06_reject_outcome_or_extra_field(fixture):
    req,*_=fixture;r={**req,'audit_results':[]}
    with pytest.raises(Blocked,match='RESERVATION_SCHEMA_OR_OUTCOMES_PRESENT'):create_split_reservation(r)

def test_07_reject_seen_source_role(fixture):
    req,*_=fixture;r={**req,'role':'HISTORICAL_SEEN_TRAIN'}
    with pytest.raises(Blocked,match='HISTORICAL_OR_MISLABELED'):create_split_reservation(r)

def test_08_reject_fake_exposure_proof(fixture):
    req,*_=fixture;r={**req,'source_exposure':'INDEPENDENTLY_PROVEN_BY_USER'}
    with pytest.raises(Blocked,match='EXPOSURE'):create_split_reservation(r)

def test_09_bad_seed(fixture):
    req,*_=fixture
    with pytest.raises(Blocked,match='SEED'):create_split_reservation({**req,'seed':1001})

def test_10_bad_embargo(fixture):
    req,*_=fixture
    with pytest.raises(Blocked,match='EMBARGO'):create_split_reservation({**req,'embargo_days':0})

def test_11_real_embargo_calendar_short(fixture):
    req,*_=fixture;new={**req,'audit_block_ids':[x.replace('2027-02-02','2027-01-26') for x in req['audit_block_ids']]}
    with pytest.raises(Blocked,match='EMBARGO'):create_split_reservation(new)

def test_12_same_day_overlap_rejected(fixture):
    req,*_=fixture;new={**req,'audit_block_ids':req['audit_block_ids'][:-2]+req['discovery_block_ids'][-2:]}
    with pytest.raises(Blocked,match='DISCOVERY_AUDIT_SAME_DAY'):create_split_reservation(new)

def test_13_bad_inverter_day_pair(fixture):
    req,*_=fixture;items=list(req['audit_block_ids']);items[-1]=items[-1].replace('inv2','inv1')
    with pytest.raises(Blocked,match='AUDIT_BLOCK_COUNT'):create_split_reservation({**req,'audit_block_ids':items})

def test_14_bad_day(fixture):
    req,*_=fixture;items=list(req['audit_block_ids']);items[-1]='opencem:inv2:2026-11-31'
    with pytest.raises(Blocked,match='BAD_CALENDAR_DAY'):create_split_reservation({**req,'audit_block_ids':items})

def test_15_candidate_255(fixture):
    req,*_=fixture
    with pytest.raises(Blocked,match='CANDIDATE_POOL'):create_split_reservation({**req,'candidate_ids':req['candidate_ids'][:-1]})

def test_16_duplicate_candidate(fixture):
    req,*_=fixture;items=list(req['candidate_ids']);items[-1]=items[0]
    with pytest.raises(Blocked,match='CANDIDATE_POOL'):create_split_reservation({**req,'candidate_ids':items})

def test_17_tamper_plan_sha(fixture):
    _,p,l,*_=fixture;d={**p,'embargo_full_days':100}
    with pytest.raises(Blocked,match='SPLIT_PLAN_TAMPERED'):lock_receipt_envelope(l,d)

def test_18_tamper_selection_sha(fixture):
    _,p,l,*_=fixture;d={**l,'F0_selected_ids':l['F1_selected_ids']}
    with pytest.raises(Blocked,match='R19_LOCK_TAMPERED'):lock_receipt_envelope(d,p)

def test_19_mismatch_source_sha(fixture):
    _,p,l,*_=fixture;d={**p,'source_inventory_sha256':'f'*64};d.pop('reservation_sha256');d['reservation_sha256']=digest(d)
    with pytest.raises(Blocked,match='SOURCE_MANIFEST_MISMATCH'):lock_receipt_envelope(l,d)

def test_20_missing_pinned_key_fails(fixture):
    *_,e,_=fixture
    r=verify_external_signature(e,{},None)
    assert r['status'].startswith('BLOCKED_') and not r['audit_can_run_confirmatory']

def test_21_test_signature_passes_but_independent_not_proven(fixture,signer):
    *_,e,_=fixture;k,pub=signer
    status=verify_external_signature(e,signed_receipt(e,k),pub)
    assert status['signature_verified'] and status['independent_attestor_identity_approved'] is False
    assert status['audit_can_run_confirmatory'] is False

def test_22_tampered_signed_receipt_rejected(fixture,signer):
    *_,e,_=fixture;k,pub=signer
    receipt=signed_receipt(e,k);receipt['external_artifact_url']='https://bad.example.org/'
    with pytest.raises(Blocked,match='SIGNATURE_INVALID'):verify_external_signature(e,receipt,pub)

def test_23_different_public_key_rejected(fixture,signer):
    *_,e,_=fixture;k,_=signer
    rogue=Ed25519PrivateKey.generate().public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw).hex()
    with pytest.raises(Blocked,match='SIGNATURE_INVALID'):verify_external_signature(e,signed_receipt(e,k),rogue)

def test_24_wrong_lock_hash_rejected(fixture,signer):
    *_,e,_=fixture;k,pub=signer
    receipt=signed_receipt(e,k);receipt['envelope_sha256']='0'*64
    with pytest.raises(Blocked,match='EXTERNAL_LOCK_HASH_MISMATCH'):verify_external_signature(e,receipt,pub)

def test_25_naive_time_rejected(fixture,signer):
    *_,e,_=fixture;k,pub=signer
    receipt=signed_receipt(e,k);receipt['registered_at']='2026-10-25T08:00:00'
    with pytest.raises(Blocked,match='NAIVE_TIMESTAMP'):verify_external_signature(e,receipt,pub)

def test_26_real_gate_remains_closed():
    d=local_gate_report()
    assert d['r19_confirmatory_result']=='NO_GO' and d['new_2001_2030_runs']=='NOT_RUN'
    assert d['external_pre_registration']=='NOT_VERIFIED'

def test_27_no_silent_R19_legacy_receipt_trust(fixture):
    _,_,lock,_,conf=fixture
    # Contrast R19's legacy trust in user-editable boolean+URL against R25 gate.
    forged={'selection_lock_sha256':lock['selection_lock_sha256'],'external_commit_url':'https://example.org/forged',
            'committed_before_audit':True}
    assert set(forged)=={'selection_lock_sha256','external_commit_url','committed_before_audit'}
    assert verify_external_signature({'schema':'R25_ED25519_SIGNATURE_REQUEST_V1'},forged,None)['audit_can_run_confirmatory'] is False


def test_28_source_manifest_sha_not_proof_of_external_capture(fixture):
    _,p,*_=fixture
    assert len(p['source_inventory_sha256'])==64 and not p['independent_source_attestation_verified']

def test_29_legacy_r19_url_boolean_is_forgeable(fixture):
    # Demonstrates WHY R25 cannot rely on the legacy R19 receipt's boolean+URL.
    _,_,lock,_,conf=fixture
    forged_receipt={'selection_lock_sha256':lock['selection_lock_sha256'],
                    'external_commit_url':'https://example.org/does-not-exist',
                    'committed_before_audit':True}
    fake_measurements={c:{b:[1.0,1.0,1.0,1.0] for b in lock['audit_block_ids']}
                       for c in lock['candidate_ids']}
    legacy=score_audit(conf,lock,dict(seed=lock['seed'],candidate_block_objectives=fake_measurements,
                                      independent_lock_receipt=forged_receipt))
    assert legacy['stage']=='EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST'
    assert verify_external_signature({'schema':'R25_ED25519_SIGNATURE_REQUEST_V1'},forged_receipt,None)['audit_can_run_confirmatory'] is False


def test_30_cli_status_exclusive_output(tmp_path):
    import subprocess
    cli=ROOT/'tools/r25_cli.py';target=tmp_path/'first.json'
    r=subprocess.run([sys.executable,str(cli),'status','--out',str(target)],capture_output=True,text=True)
    assert r.returncode==0 and target.exists()
    d=json.loads(target.read_text());assert d['r19_confirmatory_result']=='NO_GO'
    second=subprocess.run([sys.executable,str(cli),'status','--out',str(target)],capture_output=True,text=True)
    assert second.returncode!=0
