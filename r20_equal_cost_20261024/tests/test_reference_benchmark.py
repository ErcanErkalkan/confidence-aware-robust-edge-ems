import sys,zipfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from cost_audit import AuditBlocked
from reference_benchmark import validate_source_snapshots,load_records,run_one
from live_profiler import PhaseProfiler,InstrumentationError,environment_fingerprint

def test_three_actual_git_source_blob_shas():
    validate_source_snapshots()

def test_replay_on_real_train_rows():
    source=ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip'
    with zipfile.ZipFile(source) as z:r,_=load_records(z,1004,8)
    a=run_one(r,'F0',200)
    b=run_one(r,'F1',200)
    assert b['confidence_bootstrap_calls']>0
    assert b['bootstrap_resamples_total']==b['confidence_bootstrap_calls']*2*200
    assert a['confidence_bootstrap_calls']==0
    assert b['replayed_archive_count']>=1

def test_profiler_rejects_claim_without_optin():
    with pytest.raises(InstrumentationError,match='benchmark_mode'):PhaseProfiler(2001,'F0','a'*40)

def test_profiler_nested_guard():
    p=PhaseProfiler(2001,'F0','a'*40,benchmark_mode=True)
    with p.measure('sim'):
        p.reserve_actual_evaluation('a','D0')
        with pytest.raises(InstrumentationError,match='nest'): 
            with p.measure('archive'):pass
    assert len(p.eval_ids)==1

def test_profiler_eval_duplicates_block():
    p=PhaseProfiler(2001,'F0','a'*40,benchmark_mode=True)
    with p.measure('sim'):
        p.reserve_actual_evaluation('a','D0')
        with pytest.raises(InstrumentationError,match='duplicated'):
            p.reserve_actual_evaluation('a','D0')

def test_profiler_cannot_emit_fake_complete():
    p=PhaseProfiler(2001,'F0','a'*40,benchmark_mode=True)
    with pytest.raises(InstrumentationError,match='incomplete'):p.emit(input_ledger_sha256='b'*64,environment_sha256='c'*64)

def test_profiler_pair_telemetry_is_arm_specific():
    p=PhaseProfiler(2001,'F0','a'*40,benchmark_mode=True)
    with p.measure('archive'):
        p.record_archive_candidate_count(14)
        p.record_pair_test(confidence=False)
        with pytest.raises(InstrumentationError,match='bootstrap'):
            p.record_pair_test(confidence=True,bootstrap_draws_per_pair=200)
    assert p.max_native_archive_members==14

def test_profiler_f1_telemetry():
    p=PhaseProfiler(2001,'F1','a'*40,benchmark_mode=True)
    with p.measure('archive'):
        p.record_pair_test(confidence=True,bootstrap_draws_per_pair=200)
        with pytest.raises(InstrumentationError,match='mixed'):
            p.record_pair_test(confidence=True,bootstrap_draws_per_pair=500)
    assert p.confidence_pair_calls==1

def test_fingerprint_is_deterministic():
    x,env=environment_fingerprint()
    y,_=environment_fingerprint()
    assert len(x)==64 and x==y and env['measurement_clock']
