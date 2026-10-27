import copy
import pytest
from crmt_edge_ems.contracts import ContractError,digest
from crmt_edge_ems.provenance import source_manifest,validate_manifest,EXECUTION_EXCEPTIONS

def test_source_manifest_tamper_and_execution_exception(tmp_path):
    (tmp_path/'a.py').write_bytes(b'original\r\n')
    m=source_manifest(tmp_path,['a.py'])
    assert validate_manifest(tmp_path,m)['files_verified']==1
    assert EXECUTION_EXCEPTIONS[0]['resolved'] is False
    (tmp_path/'a.py').write_bytes(b'original\n')
    with pytest.raises(ContractError,match='hash mismatch'): validate_manifest(tmp_path,m)

@pytest.mark.parametrize('path',['../escape.py','/absolute','C:/outside','a\\b',''])
def test_manifest_rejects_unsafe_paths(tmp_path,path):
    with pytest.raises(ContractError): source_manifest(tmp_path,[path])

def test_manifest_rejects_duplicates_and_digest_change(tmp_path):
    (tmp_path/'a').write_text('x')
    with pytest.raises(ContractError): source_manifest(tmp_path,['a','a'])
    m=source_manifest(tmp_path,['a']); m['content_sha256']='0'*64
    with pytest.raises(ContractError): validate_manifest(tmp_path,m)