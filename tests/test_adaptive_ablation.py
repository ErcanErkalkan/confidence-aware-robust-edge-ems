import pytest
from crmt_edge_ems.ablation import factorial_design,matched_diagnostics
from crmt_edge_ems.contracts import ContractError

def test_factorial_separates_all_factors():
    rows=factorial_design();assert len(rows)==32
    assert len({tuple(sorted(r.items())) for r in rows})==32
    assert {r['output_capacity'] for r in rows}=={10,20}

def test_matched_comparison_rejects_different_partitions():
    a={'data_partition_sha256':'x','candidate_pool_sha256':'y','optimizer_seed':1,'simulation_seed':2,'train_budget':40,
       'archive_ids':['a','b'],'selected_parameter_sha256':'c','allocation_counts':{'a':20,'b':20}}
    b={**a,'archive_ids':['b','d'],'allocation_counts':{'a':10,'b':30}}
    r=matched_diagnostics(a,b);assert r['archive_jaccard']==pytest.approx(1/3) and r['selected_controller_agreement']
    b['simulation_seed']=3
    with pytest.raises(ContractError): matched_diagnostics(a,b)
