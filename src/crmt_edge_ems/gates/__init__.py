"""Fail-closed prospective gate inspection, with no installed external authority.

R25's signature verification proves key possession, not reviewer independence.
This integration deliberately cannot authorize real execution until an externally
audited authority registry and provider evidence are installed in a later review.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import re
from ..contracts import ContractError, canonical, file_hash, digest

GATES=('G0_SOURCE_INTEGRITY','G1_DATA_SEMANTICS','G2_METHOD_AND_CAPACITY','G3_SPLIT_AND_EXPOSURE',
    'G4_POWER_AND_PREREGISTRATION','G5_DISCOVERY_AUDIT_EXECUTION','G6_INDEPENDENT_TEST','G7_MANUSCRIPT_RELEASE')

def timestamp(text):
    try: value=datetime.fromisoformat(text.replace('Z','+00:00'))
    except (ValueError,TypeError,AttributeError) as exc: raise ContractError('invalid evidence timestamp') from exc
    if value.tzinfo is None: raise ContractError('naive evidence timestamp')
    return value.astimezone(timezone.utc)

def inspect_external_receipt(envelope, *, expected_binding, now=None):
    """Validate binding/time/signature structure; reject untrusted local evidence.

    A cryptographically valid signature from a caller-supplied key is never an
    installed independent authority and never opens a scientific gate.
    """
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ContractError('timezone-aware check time required')
    required={'binding','issued_at','expires_at','reviewer','public_key_hex','signature_hex','origin'}
    if not isinstance(envelope,dict) or set(envelope)!=required: raise ContractError('receipt schema mismatch')
    if envelope['binding']!=expected_binding: raise ContractError('receipt binding mismatch')
    issued=timestamp(envelope['issued_at']); expires=timestamp(envelope['expires_at'])
    if not issued<=now<expires or expires<=issued: raise ContractError('expired/future receipt')
    if envelope['origin']!='EXTERNAL_INDEPENDENT': raise ContractError('internally generated substitute evidence forbidden')
    if not isinstance(envelope['reviewer'],str) or not envelope['reviewer'].strip(): raise ContractError('reviewer absent')
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except ImportError as exc:
        raise ContractError('signature verifier unavailable; independent authorization remains blocked') from exc
    try:
        message={k:v for k,v in envelope.items() if k!='signature_hex'}
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(envelope['public_key_hex'])).verify(bytes.fromhex(envelope['signature_hex']),canonical(message))
    except (ValueError,TypeError,InvalidSignature) as exc:
        raise ContractError('invalid receipt signature') from exc
    raise ContractError('untrusted key: no externally verified authority registry installed; local signature cannot approve experiment')

def gate_report(*, source_validation=None):
    now=datetime.now(timezone.utc).isoformat(); rows=[]
    for gate in GATES:
        source_ok=gate==GATES[0] and source_validation is not None and source_validation.get('status')=='VERIFIED_COMPLETE'
        # Even G0 byte identity does not close the historical execution exception.
        rows.append({'gate':gate,'status':'IMPLEMENTED_NOT_INDEPENDENTLY_VALIDATED' if source_ok else 'BLOCKED_EXTERNAL',
            'required_evidence':{'G0_SOURCE_INTEGRITY':'Current source byte manifest, clean execution commit, environment lock; original execution-SHA exception retained',
                'G1_DATA_SEMANTICS':'Provider measurements, lineage, physical assumptions and independent review',
                'G2_METHOD_AND_CAPACITY':'Approved R19 fixed contract and B10 policy; calibration claim separately justified',
                'G3_SPLIT_AND_EXPOSURE':'Authoritative source/exposure inventory, day/group split and embargo review',
                'G4_POWER_AND_PREREGISTRATION':'Approved effect/SD/power plan, fixed seed list and independent preregistration receipt',
                'G5_DISCOVERY_AUDIT_EXECUTION':'G0–G4 externally passed and authorized immutable protocol',
                'G6_INDEPENDENT_TEST':'New eligible unexposed data, license, safety and independent operational TEST plan',
                'G7_MANUSCRIPT_RELEASE':'Verified claim evidence, completed manuscript review and explicit release authorization'}[gate],
            'verification_method':'Local content hashes and rejection checks; independent authority NOT installed',
            'evidence_hash':digest(source_validation) if source_ok else None,
            'blocking_reason':'Byte identity is not independent execution validation' if source_ok else 'Required independently verifiable evidence/authority absent',
            'reviewer_or_authority':None,'last_checked':now})
    return {'schema_version':1,'CONFIRMATORY_STATUS':'NO_GO','locked':False,'gates':rows}

def require_scientific_execution(command):
    if command not in {'discovery','archive-build','shortlist-select','audit','analyze','independent-test','report'}: raise ContractError('unknown scientific command')
    raise ContractError(f'{command}: CONFIRMATORY_STATUS=NO_GO; verified external authority, data admission, protocol and authorization required')
