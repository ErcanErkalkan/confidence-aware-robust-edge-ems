import copy,json,sys,zipfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from r24_audit import run,check_sources,parse,audit_seed,_load_arm,AuditBlocked,OBJ
from r24_preflight import validate_planned_audit,synthetic_planning_fixture,PreflightBlocked

@pytest.fixture(scope='module')
def report():return run()

@pytest.fixture(scope='module')
def fake():return synthetic_planning_fixture()

def test_orig_source_snapshot_sha():assert len(check_sources())==3

def test_three_historical_only(report):
    assert [r['seed'] for r in report['rows']]==[1001,1004,1005]
    assert report['n_new_seed_runs']==0

def test_12_600_verified_pairs(report):
    assert all(r['n_candidate_block_events']==12600 and r['paired_objectives_match'] for r in report['rows'])

def test_real_B10_no_backfill(report):
    assert all(len(r['F0_selected_B10'])==len(r['F1_selected_B10'])==10 for r in report['rows'])
    assert all(r['natural_archive_F0']>=10 and r['natural_archive_F1']>=10 for r in report['rows'])

def test_actual_B10_overlap(report):
    assert [r['B10_shared'] for r in report['rows']]==[6,9,7]
    assert [r['B10_arm_specific'] for r in report['rows']]==[4,1,3]

def test_real_common_day_coverage(report):
    assert [r['global_complete_two_inverter_days_256'] for r in report['rows']]==[9,5,5]
    assert [r['global_common_blocks_256'] for r in report['rows']]==[18,10,10]

def test_never_pretend_future_audit_exists(report):
    assert all(r['R19_future_TRAIN_AUDIT'].startswith('NOT_EXECUTED') for r in report['rows'])
    assert report['claims']['new_AUDIT_score'] is None

def test_old_missing_commit_preserved(report):
    assert report['rows'][0]['original_git_sha_F1']=='UNRECORDED_LOCAL_SHA'
    assert report['gates']['original_seed1001_F1_git_sha']=='UNRECORDED_LOCAL_SHA'

def test_R23_not_falsely_certified(report):
    assert all(r['R23_real_certification'].startswith('BLOCKED_') for r in report['rows'])

def test_observed_extrema_not_usable_support(report):
    assert all(len(r['observed_loss_extrema_not_prospective_bounds'])==4 for r in report['rows'])
    assert all(not z['support_prospectively_justified'] for r in report['rows'] for z in r['observed_loss_extrema_not_prospective_bounds'].values())

def test_plan_arithmetic(report):
    p=report['future_30_seed_plan'];assert p['audit_events_per_seed']==15360
    assert p['audit_events_all_30_seeds']==460800
    assert p['discovery_events_per_arm_all_30_seeds']==378000

def test_date_parser():
    assert parse('opencem:inv2:2025-08-02')==('2025-08-02','inv2')
    for b in ('o:inv1:2025-01-01','opencem:inv3:2025-01-01','opencem:inv1:2025-02-30'):
        with pytest.raises(AuditBlocked):parse(b)

def test_fake_sha_corrupt_source_rejected():
    class Corrupt:
        def __init__(self,z):self.z=z
        def read(self,name):
            b=self.z.read(name)
            if name.endswith('optimizer_front.csv'):return b+b'\n'
            return b
    with zipfile.ZipFile(ROOT/'reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip') as z:
        with pytest.raises(AuditBlocked,match='RAW_SHA_MISMATCH'):_load_arm(Corrupt(z),1004,'F0')

def test_r19_draft_unchanged():
    p=json.loads((ROOT/'config/R19_PRIMARY_PROTOCOL_UNCHANGED.json').read_text())
    assert not p['locked'] and p['planned_seeds']==list(range(2001,2031))

def test_synthetic_fixture_not_proof(fake):
    v=validate_planned_audit(fake)
    assert v['audit_events_n']==15360 and v['audit_day_n']==30
    assert not v['r23_certificate_eligible'] and not v['external_immutable_pre_registration_verified']

def test_bad_dry_run_role(fake):
    q={**fake,'role':'REAL_CERTIFIED'}
    with pytest.raises(PreflightBlocked,match='DISALLOWED_SOURCE_ROLE'):validate_planned_audit(q)

def test_duplicate_plan_row(fake):
    q={**fake,'audit_rows':list(fake['audit_rows'])}
    q['audit_rows'][-1]=q['audit_rows'][0]
    with pytest.raises(PreflightBlocked,match='DUPLICATE'):validate_planned_audit(q)

def test_missing_candidate_row(fake):
    q={**fake,'audit_rows':fake['audit_rows'][:-1]}
    with pytest.raises(PreflightBlocked,match='INCOMPLETE'):validate_planned_audit(q)

def test_candidate_pool_less_than_256(fake):
    q={**fake,'candidate_ids':fake['candidate_ids'][:-1]}
    with pytest.raises(PreflightBlocked,match='CANDIDATE_POOL'):validate_planned_audit(q)

def test_day_split_leak_rejected(fake):
    q={**fake,'discovery_block_ids':[fake['audit_block_ids'][0]]}
    with pytest.raises(PreflightBlocked,match='BLOCK_LEAKAGE'):validate_planned_audit(q)

def test_day_level_leak_rejected(fake):
    q={**fake,'discovery_block_ids':[fake['audit_block_ids'][0].replace('inv1','inv2')]}
    with pytest.raises(PreflightBlocked,match='BLOCK_LEAKAGE'):validate_planned_audit(q)

def test_nonfinite_loss(fake):
    q={**fake,'audit_rows':list(fake['audit_rows'])};q['audit_rows'][-1]={**q['audit_rows'][-1],'losses':{**q['audit_rows'][-1]['losses'],'flip_per_day':float('nan')}}
    with pytest.raises(PreflightBlocked,match='NONFINITE'):validate_planned_audit(q)

def test_audit_missing_second_inverter(fake):
    q={**fake,'audit_block_ids':fake['audit_block_ids'][:-1]+[fake['audit_block_ids'][0].replace('2027-01-01','2027-02-01')]}
    with pytest.raises(PreflightBlocked,match='AUDIT_NEEDS'):validate_planned_audit(q)

def test_artifact_results_still_recompute(report):
    p=ROOT/'results/R24_REAL_TRAIN_BRIDGE.json'
    if p.exists():
        saved=json.loads(p.read_text())
        assert saved==report
