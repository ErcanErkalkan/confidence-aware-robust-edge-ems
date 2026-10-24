from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from primary_hypothesis import (Blocked,selection_lock,score_audit,summarise,
    paired_two_sided_signflip,nondominated_ids,canonical_hash,config_validate)

CONFIG=json.loads((ROOT/'config/R19_PRIMARY_PROTOCOL_DRAFT.json').read_text())

@pytest.fixture(scope='module')
def selection_example():
    ids=[f'cand{i:03d}' for i in range(256)]
    blocks=[{'block_id':f'D{i:02d}','group_id':f'dayD{i:02d}','split':'DISCOVERY'} for i in range(50)]
    blocks += [{'block_id':f'A{i:02d}','group_id':f'dayA{i:02d}','split':'AUDIT'} for i in range(8)]
    metrics={cid:{f'D{j:02d}':[i/100 +j/10000,1+i/100 +j/10000,2+i/100+j/10000,3+i/100+j/10000] for j in range(49+(i<56))} for i,cid in enumerate(ids)}
    events=[[cid,f'D{i:02d}'] for cid in ids for i in range(49)]
    events += [[cid,'D49'] for cid in ids[:56]]
    assert len(events)==12600
    src={'seed':2001,'run_git_sha':'a'*40,'source_manifest_sha256':'c'*64,
         'candidate_ids':ids,'blocks':blocks,
         'archives':{'F0':ids[:25],'F1':ids[:150]},
         'discovery_objectives':metrics,
         'evaluation_pairs':{'F0':events,'F1':copy.deepcopy(events)}}
    return src

@pytest.fixture
def locked(selection_example):
    return selection_lock(CONFIG,selection_example)

@pytest.fixture
def audit_input(locked):
    ids=locked['candidate_ids'];blocks=locked['audit_block_ids']
    data={cid:{bid:[1+i/100]*4 for bid in blocks} for i,cid in enumerate(ids)}
    return {'seed':2001,'candidate_block_objectives':data,
            'independent_lock_receipt':{'selection_lock_sha256':locked['selection_lock_sha256'],
             'external_commit_url':'https://github.com/example/repo/commit/abc',
             'committed_before_audit':True}}


def test_config_scope():
    config_validate(CONFIG)
    bad=copy.deepcopy(CONFIG);bad['locked']=True
    with pytest.raises(Blocked):config_validate(bad)


def test_selection_is_reproducible_and_no_backfill(locked):
    assert len(locked['F0_selected_ids'])==len(locked['F1_selected_ids'])==10
    assert locked['F0_selected_ids']==locked['F1_selected_ids']
    assert locked['audit_outcomes_seen'] is False
    assert locked['discovery_block_count']==50
    assert locked['audit_block_count']==8


def test_unrecorded_sha_rejected(selection_example):
    bad=copy.deepcopy(selection_example);bad['run_git_sha']='UNRECORDED_LOCAL_SHA'
    with pytest.raises(Blocked,match='execution SHA'):selection_lock(CONFIG,bad)


def test_different_eval_ledger_blocked(selection_example):
    bad=copy.deepcopy(selection_example);bad['evaluation_pairs']['F1'][-1]=['cand255','D49']
    with pytest.raises(Blocked,match='different TRAIN'):selection_lock(CONFIG,bad)


def test_discovery_audit_leakage_rejected(selection_example):
    bad=copy.deepcopy(selection_example);bad['evaluation_pairs']['F0'][-1]=['cand055','A00']
    with pytest.raises(Blocked,match='AUDIT block leakage'):selection_lock(CONFIG,bad)


def test_split_group_crossing_rejected(selection_example):
    bad=copy.deepcopy(selection_example);bad['blocks'][-1]['group_id']='dayD00'
    with pytest.raises(Blocked,match='group crosses'):selection_lock(CONFIG,bad)


def test_unknown_selection_field_blocks_audit_injection(selection_example):
    bad=copy.deepcopy(selection_example);bad['audit_scores']={'cand000':[0]*4}
    with pytest.raises(Blocked,match='schema mismatch'):selection_lock(CONFIG,bad)


def test_native_below_capacity_rejected(selection_example):
    bad=copy.deepcopy(selection_example);bad['archives']['F0']=bad['archives']['F0'][:9]
    with pytest.raises(Blocked,match='no-backfill capacity'):selection_lock(CONFIG,bad)


def test_incomplete_discovery_scores_rejected(selection_example):
    bad=copy.deepcopy(selection_example);del bad['discovery_objectives']['cand000']['D00']
    with pytest.raises(Blocked,match='discovery metrics do not match'):selection_lock(CONFIG,bad)


def test_sealed_audit_success(locked,audit_input):
    r=score_audit(CONFIG,locked,audit_input)
    assert r['reference_nondominated_n']==1
    assert r['F0_miss_rate']==r['F1_miss_rate']==0
    assert r['same_k']
    assert r['delta_F1_minus_F0']==0


def test_missing_external_receipt_blocked(locked,audit_input):
    bad=copy.deepcopy(audit_input);bad['independent_lock_receipt']['committed_before_audit']=False
    with pytest.raises(Blocked,match='not externally locked'):score_audit(CONFIG,locked,bad)


def test_lock_tamper_detected(locked,audit_input):
    bad=copy.deepcopy(locked);bad['F1_selected_ids']=list(reversed(bad['F1_selected_ids']))
    with pytest.raises(Blocked,match='digest mismatch'):score_audit(CONFIG,bad,audit_input)


def test_audit_missing_block_detected(locked,audit_input):
    bad=copy.deepcopy(audit_input);del bad['candidate_block_objectives']['cand002']['A03']
    with pytest.raises(Blocked,match='AUDIT incomplete'):score_audit(CONFIG,locked,bad)


def test_audit_nonfinite_detected(locked,audit_input):
    bad=copy.deepcopy(audit_input);bad['candidate_block_objectives']['cand002']['A03'][1]=float('nan')
    with pytest.raises(Blocked,match='invalid objective'):score_audit(CONFIG,locked,bad)


def test_nondominated_reference():
    p={'a':np.array([1.,1.,1.,1.]),'b':np.array([2.,2.,2.,2.]),
       'c':np.array([0.5,3.,1.,1.])}
    assert nondominated_ids(p)=={'a','c'}


def test_five_seed_two_sided_floor():
    assert paired_two_sided_signflip([-1]*5)==pytest.approx(.0625)
    assert paired_two_sided_signflip([0]*5)==1.0


def test_summary_rejects_duplicate_seeds():
    obj={'stage':'EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST','seed':1,'delta_F1_minus_F0':-.1}
    with pytest.raises(Blocked,match='duplicated seed'):summarise(CONFIG,[obj,obj])


def test_summary_not_confirmatory_with_only_five():
    objs=[{'stage':'EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST','seed':2001+i,'delta_F1_minus_F0':-.2} for i in range(5)]
    r=summarise(CONFIG,objs)
    assert r['target_met'] is False
    assert r['primary_claim_supported_for_exploratory_audit'] is False
    assert r['p_two_sided_signflip']==pytest.approx(.0625)


def test_summary_can_detect_thirty_negative_effects_but_not_newtest():
    objs=[{'stage':'EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST','seed':2001+i,'delta_F1_minus_F0':-.2} for i in range(30)]
    r=summarise(CONFIG,objs)
    assert r['target_met'] is True
    assert r['primary_claim_supported_for_exploratory_audit'] is True
    assert r['status'].endswith('NOT_NEW_TEST')


def test_frozen_config_rejects_changed_alpha():
    bad=copy.deepcopy(CONFIG);bad['primary_alpha_two_sided']=.10
    with pytest.raises(Blocked,match='alpha changed'):config_validate(bad)


def test_hash_repeatability(locked):
    base=dict(locked);expected=base.pop('selection_lock_sha256')
    assert canonical_hash(base)==expected


def test_one_seed_summary_has_null_ci_not_nan():
    objs=[{'stage':'EXPLORATORY_TRAIN_AUDIT_ONLY_NOT_INDEPENDENT_TEST','seed':2001,'delta_F1_minus_F0':-.1}]
    r=summarise(CONFIG,objs)
    assert r['paired_seed_bootstrap_ci95'] is None
    json.dumps(r,allow_nan=False)

def test_unplanned_seed_rejected(selection_example):
    bad=copy.deepcopy(selection_example);bad['seed']=55555
    with pytest.raises(Blocked,match='frozen planned seed'):selection_lock(CONFIG,bad)

def test_paired_normal_approximate_power_is_not_guarantee():
    from power_sensitivity import approximate_required_seeds
    assert approximate_required_seeds(.1)>=31
    assert approximate_required_seeds(.2)>=125
    with pytest.raises(ValueError):approximate_required_seeds(0)


def test_empirical_tail_score_matches_manual_top_decile():
    from primary_hypothesis import topk_cvar
    data=np.arange(10,dtype=float).reshape(1,10,1).repeat(4,axis=2)
    assert np.allclose(topk_cvar(data,.9,.5),[9.0]*4)
