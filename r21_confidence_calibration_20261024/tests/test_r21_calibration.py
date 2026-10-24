from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from calibrate import (
  validate_source,risk,generate,oracle_front,assess,wilson,run_experiment,
  CalibrationBlocked,KAPPA,SCENARIOS,METHODS,complete_subpanel,_legacy)
from real_train_diagnostic import run as run_historical


def test_original_unchanged_source_blobs():validate_source()

def test_topk_function_is_actual_crmt_mean_plus_half_tail():
 a=np.arange(20,dtype=float).reshape(1,5,4)
 target=np.mean(a,axis=1)+.5*np.max(a,axis=1)
 assert np.allclose(risk(a),target)

def test_oracle_includes_tail_baseline_weight():
 p=generate('clear_iid',133)
 sigma=(.36**2+.28**2)**.5
 assert p.oracle[0,0]==pytest.approx(1.5*6+.5*KAPPA*sigma)

def test_five_candidates_four_objectives():
 for s in SCENARIOS:
  p=generate(s,124)
  assert p.values.shape==(5,48,4)
  assert p.oracle.shape==(5,4)

def test_clear_front_has_three_true_members():
 assert oracle_front(generate('clear_iid',7).oracle)=={0,1,2}

def test_near_front_has_three_true_members():
 assert oracle_front(generate('near_iid',7).oracle)=={0,1,2}

def test_flat_true_front_is_five_and_cannot_fit_three():
 assert oracle_front(generate('flat_serial',7).oracle)==set(range(5))

def test_no_missing_in_clean_cases():
 for s in SCENARIOS[:-1]:
  assert np.isfinite(generate(s,11).values).all()

def test_missing_panel_rejects_maxT():
 p=generate('near_serial_partial',15)
 for m in ('maxT_shared_iid','maxT_shared_moving_block'):
  result=assess(p,m,12,n_boot=200)
  assert result['status'].startswith('BLOCKED_')
  assert result['false_removal'] is None

def test_missing_panel_reference_still_executes_but_no_dependence_guarantee():
 r=assess(generate('near_serial_partial',16),'legacy_reference_iid',12,n_boot=200)
 assert r['status']=='MEASURED'

def test_legacy_unmodified_reference_counts():
 p=generate('clear_iid',2)
 dom,under,_=_legacy(p,200)
 assert dom.shape==(5,5) and not np.diag(dom).any()
 assert isinstance(under,bool)

def test_shared_maxT_iid_runs():
 r=assess(generate('near_iid',18),'maxT_shared_iid',102,n_boot=200)
 assert r['status']=='MEASURED'
 assert r['critical_value']>0

def test_shared_maxT_block_runs():
 r=assess(generate('near_serial',18),'maxT_shared_moving_block',102,n_boot=200)
 assert r['status']=='MEASURED' and r['critical_value']>0

def test_blocklength_must_be_feasible():
 p=generate('near_serial',18)
 r=assess(p,'maxT_shared_moving_block',102,n_boot=200,block_len=16)
 assert r['status']=='BLOCKED_BLOCK_LENGTH'

def test_degenerate_noise_refuses_unjustified_se():
 p=generate('clear_iid',3)
 p.values=np.repeat(p.oracle[:,None,:],48,axis=1)
 r=assess(p,'maxT_shared_iid',16,n_boot=200)
 assert r['status']=='BLOCKED_DEGENERATE_BOOTSTRAP_SE'

def test_reproducible_per_seed():
 a=generate('near_serial',2026);b=generate('near_serial',2026)
 assert np.array_equal(a.values,b.values)
 assert assess(a,'maxT_shared_iid',123,n_boot=200)==assess(b,'maxT_shared_iid',123,n_boot=200)

def test_outcome_status_not_safety_certificate():
 r=assess(generate('clear_iid',200),'legacy_reference_iid',65,n_boot=200)
 assert r['status']=='MEASURED' and 'safe' not in r

def test_wilson_zero_is_not_zero_upper():
 lo,hi=wilson(0,80)
 assert lo==0 and .04<hi<.05

def test_wilson_full_is_at_most_one():
 _,hi=wilson(80,80)
 assert hi<=1+1e-14

def test_wilson_invalid_n():
 with pytest.raises(CalibrationBlocked):wilson(0,0)

def test_illegal_experiment_parameters():
 with pytest.raises(CalibrationBlocked):run_experiment(repetitions=1,n_boot=200)
 with pytest.raises(CalibrationBlocked):run_experiment(repetitions=2,n_boot=199)

def test_short_experiment_has_all_methods_cases_and_no_faked_coverage():
 d=run_experiment(repetitions=2,n_boot=200)
 assert len(d['rows'])==len(SCENARIOS)*len(METHODS)*2
 assert len(d['summary'])==len(SCENARIOS)*len(METHODS)
 assert d['metadata']['run_class'].startswith('SYNTHETIC_')
 assert all(r['family_undercoverage_rate'] is None for r in d['summary'] if r['method']=='point_pareto')

def test_80rep_real_experiment_preserved():
 results=json.loads((ROOT/'results/R21_EXPERIMENT.json').read_text())
 assert len(results['rows'])==5*4*80
 assert results['metadata']['n_boot']==350
 assert results['metadata']['archive_capacity']==3
 assert sum(r['status']!='MEASURED' for r in results['rows'])==2*80

def test_historical_train_3_seeds_is_genuine_source_integrity():
 r=run_historical()
 assert len(r['rows'])==3
 assert all(x['arm_metrics_identical'] and x['n_records']==12600 for x in r['rows'])
 assert {x['seed'] for x in r['rows']}=={1001,1004,1005}
 assert all(x['unique_calendar_days_per_controller_min']<x['candidate_block_count_min'] for x in r['rows'])

def test_no_test_leakage():
 r=run_historical()
 assert 'HISTORICAL_SEEN_OPEN_CEM_TRAIN_ONLY' in r['source_kind']
 assert all(x['conclusion'].endswith('NOT_NEW_TEST') for x in r['rows'])

def test_legacy_decisions_match_exact_frozen_confidence_archive():
 from crmt_edge_ems.archive import ConfidenceArchive,CandidateRecord
 from crmt_edge_ems.risk import RiskConfig
 p=generate('near_serial',89)
 dom,_,_=_legacy(p,200)
 derived={i for i in range(5) if not np.any(dom[:,i])}
 archive=ConfidenceArchive(risk=RiskConfig(),n_boot=200,alpha=.05)
 for i,cid in enumerate(p.labels):
  rec=CandidateRecord(cid,{},p.values[i],risk(p.values[i][None,:,:])[0],
                      tuple(f'block-{j}' for j in range(p.values.shape[1])))
  archive.add(rec)
 selected=archive.confidently_nondominated_ids()
 assert derived=={p.labels.index(x) for x in selected}
