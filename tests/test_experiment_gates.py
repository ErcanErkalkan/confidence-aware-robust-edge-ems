from datetime import datetime,timezone
import pytest
from crmt_edge_ems.contracts import ContractError,canonical
from crmt_edge_ems.gates import inspect_external_receipt,require_scientific_execution,gate_report

@pytest.mark.parametrize('command',['discovery','archive-build','shortlist-select','audit','analyze','independent-test','report'])
def test_scientific_commands_cannot_bypass_no_go(command):
    with pytest.raises(ContractError,match='NO_GO'): require_scientific_execution(command)

def envelope():
    return {'binding':{'protocol':'draft','source':'hash'},'issued_at':'2026-01-01T00:00:00+00:00',
        'expires_at':'2027-01-01T00:00:00+00:00','reviewer':'synthetic test reviewer',
        'public_key_hex':'00'*32,'signature_hex':'00'*64,'origin':'EXTERNAL_INDEPENDENT'}

@pytest.mark.parametrize('fault',['forged','expired','mismatch','internal','naive','future'])
def test_forged_expired_internal_receipts_rejected(fault):
    e=envelope(); binding=e['binding'].copy()
    if fault=='expired': e['expires_at']='2026-02-01T00:00:00+00:00'
    if fault=='mismatch': e['binding']={'protocol':'other'}
    if fault=='internal': e['origin']='LOCAL_TEST_KEY'
    if fault=='naive': e['issued_at']='2026-01-01T00:00:00'
    if fault=='future': e['issued_at']='2026-12-01T00:00:00+00:00'
    with pytest.raises(ContractError): inspect_external_receipt(e,expected_binding=binding,now=datetime(2026,10,27,tzinfo=timezone.utc))

def test_even_valid_local_signature_cannot_approve():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    # Ephemeral fixture only; never saved as independent evidence or authority.
    key=Ed25519PrivateKey.generate();e=envelope()
    e['public_key_hex']=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    e['signature_hex']=key.sign(canonical({k:v for k,v in e.items() if k!='signature_hex'})).hex()
    with pytest.raises(ContractError,match='untrusted key'): inspect_external_receipt(e,expected_binding=e['binding'],now=datetime(2026,10,27,tzinfo=timezone.utc))
    report=gate_report()
    assert report['CONFIRMATORY_STATUS']=='NO_GO' and report['locked'] is False
    assert all(g['status']=='BLOCKED_EXTERNAL' for g in report['gates'])
