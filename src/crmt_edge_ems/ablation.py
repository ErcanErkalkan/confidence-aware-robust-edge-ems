"""Matched factorial diagnostics; component benefit is not assumed."""
from itertools import product
from .contracts import ContractError,identifiers,digest

def factorial_design(capacities=(10,20),strategies=('linf_l1','l1_linf')):
    from .contracts import integer
    if not capacities or not strategies or len(set(capacities))!=len(capacities) or len(set(strategies))!=len(strategies): raise ContractError('nonempty unique factor levels required')
    for b in capacities: integer(b,'capacity',1)
    if not set(strategies)<={'linf_l1','l1_linf'}: raise ContractError('unsupported candidate selection strategy')
    return [{'implementation_id':'CRMT-FACTORIAL-DIAGNOSTIC-v1','confidence':f,'adaptive':a,'risk_calibration':c,
             'output_capacity':b,'strategy':s} for f,a,c,b,s in product((False,True),(False,True),(False,True),capacities,strategies)]

def matched_diagnostics(left,right):
    binding=('data_partition_sha256','candidate_pool_sha256','optimizer_seed','simulation_seed','train_budget')
    if any(left.get(k)!=right.get(k) or left.get(k) is None for k in binding): raise ContractError('unmatched data/candidates/seeds/budget')
    a=set(identifiers(left['archive_ids'],'left archive',allow_empty=True));b=set(identifiers(right['archive_ids'],'right archive',allow_empty=True))
    return {'schema_version':1,'selected_controller_agreement':left['selected_parameter_sha256']==right['selected_parameter_sha256'],
        'archive_intersection':len(a&b),'archive_jaccard':len(a&b)/len(a|b) if a|b else 1.0,
        'allocation_left':left['allocation_counts'],'allocation_right':right['allocation_counts'],
        'independent_adaptive_benefit':'UNSUPPORTED_WITHOUT_HELD_OUT_EFFECT_AND_UNCERTAINTY',
        'matched_binding_sha256':digest({k:left[k] for k in binding})}