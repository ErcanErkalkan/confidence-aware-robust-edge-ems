import copy,io,json,sys,zipfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from cost_audit import audit_pairs,audit_arm,AuditBlocked,parse_cost_record,paired_cost_check

SOURCE=ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip'

@pytest.fixture(scope='module')
def history():
    return audit_pairs(SOURCE)

def test_three_real_c1a1_pairs(history):
    assert {x['pair'] for x in history}=={'seed1001_C1_A1','seed1004_C1_A1','seed1005_C1_A1'}

def test_25000_unique_pair_science_equality(history):
    assert all(x['candidate_block_ledger_match'] and x['scientific_objectives_match'] for x in history)
    assert all(x['budget_F0']==x['budget_F1']==12600 for x in history)

def test_native_archives_unequal(history):
    assert [(x['native_archive_F0'],x['native_archive_F1']) for x in history]==[(18,236),(22,240),(17,237)]
    assert all(x['B10_export_F0']==x['B10_export_F1']==10 for x in history)
    assert all(x['native_archive_capacity_equal'] is False for x in history)

def test_true_cpu_not_available(history):
    assert all(x['cpu_archive_historical']=='NOT_RECORDED' for x in history)
    assert all(x['sim_tick_cpu_proxy_F0_ms']>0 and x['sim_tick_cpu_proxy_F1_ms']>0 for x in history)

def test_missing_original_sha_not_faked(history):
    assert history[0]['source_git_sha_F1']=='UNRECORDED_LOCAL_SHA'

class CorruptedZip:
    def __init__(self,z):self.z=z
    def read(self,name):
        data=self.z.read(name)
        if name.endswith('candidate_metrics.csv'):return data+b'\n'
        return data

def test_hash_tamper_blocks():
    with zipfile.ZipFile(SOURCE) as z:
        with pytest.raises(AuditBlocked,match='SHA mismatch'):
            audit_arm(CorruptedZip(z),'seed1004_C1_A1/F0')

def rec(arm):
    b={k:1_000 for k in ('sim_cpu_ns','optimizer_cpu_ns','archive_cpu_ns','selection_cpu_ns','audit_cpu_ns',
    'sim_wall_ns','optimizer_wall_ns','archive_wall_ns','selection_wall_ns','audit_wall_ns')}
    return dict(seed=2001,arm=arm,run_sha='a'*40,input_ledger_sha256='b'*64,
    n_controller_blocks=12600,peak_rss_bytes=100_000,
    archive_peak_tracemalloc_bytes=1000,peak_native_archive_members=35,
    final_export_members=10,pair_comparisons=77,bootstrap_draws_per_pair=200 if arm=='F1' else 0,
    confidence_pair_calls=77 if arm=='F1' else 0,runtime_environment_sha256='c'*64,**b)

def test_valid_full_cost_contract():
    assert parse_cost_record(rec('F0'))['total_cpu_ns']==5000
    assert paired_cost_check([rec('F0'),rec('F1')])['same_input_ledger']

@pytest.mark.parametrize('field,bad',[
    ('sim_cpu_ns',-1),('peak_rss_bytes',0),('n_controller_blocks',12599),
    ('final_export_members',9),('archive_cpu_ns',0),('seed',True),
    ('input_ledger_sha256','0'),('peak_native_archive_members',9),
])
def test_fail_closed_cost_fields(field,bad):
    a=rec('F1');a[field]=bad
    with pytest.raises(AuditBlocked):parse_cost_record(a)

def test_reject_unpaired_hardware():
    a,b=rec('F0'),rec('F1');b['runtime_environment_sha256']='0'*64
    with pytest.raises(AuditBlocked,match='environment'):paired_cost_check([a,b])

def test_reject_unpaired_ledger():
    a,b=rec('F0'),rec('F1');b['input_ledger_sha256']='0'*64
    with pytest.raises(AuditBlocked,match='ledger'):paired_cost_check([a,b])

def test_f0_bootstrap_impossible():
    a=rec('F0');a['confidence_pair_calls']=5
    with pytest.raises(AuditBlocked):parse_cost_record(a)

def test_f1_missing_bootstrap_impossible():
    a=rec('F1');a['confidence_pair_calls']=0
    with pytest.raises(AuditBlocked):parse_cost_record(a)
