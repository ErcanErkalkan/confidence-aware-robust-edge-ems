import copy
import pytest
from crmt_edge_ems.contracts import ContractError
from data_adapters.validation import validate_partitions

def entries():
    return [{'block_id':'d1','split':'DISCOVERY','site_id':'inv1','local_day':'2025-01-01','group_id':'day1','exposure':'EXPOSED','source_sha256':'a'*64},
            {'block_id':'a1','split':'AUDIT','site_id':'inv1','local_day':'2025-01-10','group_id':'day10','exposure':'UNEXPOSED','source_sha256':'a'*64}]

def test_split_and_embargo_structural_only():
    r=validate_partitions(entries()); assert r['blocks']==2 and 'NOT_EXPOSURE_ATTESTATION' in r['status']

@pytest.mark.parametrize('fault',['group','same_day','embargo','exposed_test','duplicate','unknown_exposure'])
def test_forbidden_overlaps_and_exposure(fault):
    e=entries()
    if fault=='group': e[1]['group_id']='day1'
    if fault=='same_day': e[1]['local_day']='2025-01-01'
    if fault=='embargo': e[1]['local_day']='2025-01-08'
    if fault=='exposed_test': e[1]['split']='EXTERNAL_TEST';e[1]['exposure']='EXPOSED'
    if fault=='duplicate': e[1]['block_id']='d1'
    if fault=='unknown_exposure': e[1]['exposure']='probably unseen'
    with pytest.raises(ContractError): validate_partitions(e)
