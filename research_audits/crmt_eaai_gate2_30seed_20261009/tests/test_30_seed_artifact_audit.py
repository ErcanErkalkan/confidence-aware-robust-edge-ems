from __future__ import annotations
import csv, hashlib, io, json, sys, zipfile
from pathlib import Path
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'cache_code'/'src'))
from crmt_p0.gate2_validation import load_gate1_shortlist
from crmt_p0.equal_quota import GateClosed
from prepare_30seed import MANIFEST, ARTIFACTS, execute

STORE=ROOT/'outputs'/'locked_30seed'
HISTORY=ROOT/'outputs'/'historical_cache_30seed'/'historical_validation_cache_coverage_30seeds.csv'
JOBS=ROOT/'outputs'/'replay_worklist'
ZIP=Path('/mnt/data/CRMT_EAAI_GATE2_ENGINEERING_PILOT_2026-10-08.zip')


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

@pytest.fixture(scope='session')
def index():return pd.read_csv(STORE/'train_only_30seed_5method_shortlist_index.csv')

@pytest.fixture(scope='session')
def coverage():return pd.read_csv(HISTORY)


def test_150_complete_methods_seeds(index):
 assert len(index)==150
 assert set(index.seed)==set(range(1001,1031))
 assert all(set(index[index.seed==s].method)==set(ARTIFACTS) for s in range(1001,1031))
 assert not index[['seed','method']].duplicated().any()


def test_frozen_sources_and_budget(index):
 assert set(index.source_manifest_sha256)=={MANIFEST}
 assert set(index.source_train_budget)=={12600}
 assert set(index.selected_candidates)=={20}
 assert set(index.planned_val_blocks)=={2360}
 assert set(index[index.method!='MODE'].source_train_git_sha)=={'be5756321617087ca421a639d60a99513f29d889'}
 assert set(index[index.method=='MODE'].source_train_git_sha)=={'897a9875dbbe7bd46520c9f91c4c7ee633d189fe'}


def test_150_source_hashes(index):
 for row in index.itertuples(index=False):
  p=STORE/'shortlists'/f'seed{row.seed}'/row.method
  csvp=p/'train_only_shortlist.csv';lockp=p/'train_only_shortlist_lock.json'
  assert digest(csvp)==row.train_shortlist_csv_sha256
  assert digest(lockp)==row.train_shortlist_lock_sha256
  lock=json.loads(lockp.read_text('utf-8'))
  assert lock['shortlist_sha256']==digest(csvp)


def test_all_150_frozen_load_gate2(index):
 for row in index.itertuples(index=False):
  frame,lock=load_gate1_shortlist(STORE/'shortlists'/f'seed{row.seed}'/row.method,
                                method=row.method,seed=int(row.seed),expected_manifest_sha256=MANIFEST)
  assert len(frame)==20
  assert list(frame['rank'])==list(range(1,21))


def test_25_previous_pilot_byte_identical():
 with zipfile.ZipFile(ZIP) as z:
  for seed in range(1001,1006):
   for method in ARTIFACTS:
    old=z.read(f'outputs/pilot_shortlists/seed{seed}/{method}/train_only_shortlist.csv')
    new=(STORE/'shortlists'/f'seed{seed}'/method/'train_only_shortlist.csv').read_bytes()
    assert new==old


def test_500_previous_cache_identical(coverage):
 with zipfile.ZipFile(ZIP) as z:
  old=pd.read_csv(io.BytesIO(z.read('outputs/cache_coverage/historical_validation_cache_coverage_5seeds.csv')))
 new=coverage[coverage.seed<=1005]
 cols=list(old.columns)
 sort=['seed','method','rank']
 pd.testing.assert_frame_equal(old[cols].sort_values(sort).reset_index(drop=True),
                               new[cols].sort_values(sort).reset_index(drop=True))


def test_3000_coverage_cardinality(coverage):
 assert len(coverage)==3000
 assert not coverage[['seed','method','rank']].duplicated().any()
 assert sorted(coverage.cache_status.unique())==sorted([
 'CACHED_HISTORICAL_FULL_118','MISSING_REPLAY_REQUIRED','AMBIGUOUS_REPLAY_REQUIRED'])
 assert int((coverage.cache_status=='CACHED_HISTORICAL_FULL_118').sum())==2193
 assert int((coverage.cache_status=='MISSING_REPLAY_REQUIRED').sum())==805
 assert int((coverage.cache_status=='AMBIGUOUS_REPLAY_REQUIRED').sum())==2


def test_ambiguous_never_count_as_cached(coverage):
 ambiguous=coverage[coverage.cache_status=='AMBIGUOUS_REPLAY_REQUIRED']
 assert len(ambiguous)==2
 assert ambiguous.candidate_block_rows_available.eq(0).all()


def test_cache_method_distribution(coverage):
 a=coverage.assign(is_cached=coverage.cache_status.eq('CACHED_HISTORICAL_FULL_118')).groupby('method').is_cached.sum().to_dict()
 assert a=={'CRMT':599,'MODE':165,'MOPSO':600,'NSGAII':229,'SOBOL':600}


def test_worklist_counts():
 a=pd.read_csv(JOBS/'HISTORICAL_MISSING_807_REPLAY_WORKLIST.csv')
 b=pd.read_csv(JOBS/'REPLAY_QUOTA_150_METHOD_SEED_JOBS.csv')
 assert len(a)==807 and len(b)==150
 assert a.required_blocks.eq(118).all()
 assert b.incremental_block_evaluations_to_fill.sum()==95226
 assert b.uniform_fresh_block_evaluations.sum()==354000
 assert a[['seed','method','candidate_id']].duplicated().sum()==0


def test_report_integrity():
 r=json.loads((JOBS/'WORKLIST_AUDIT.json').read_text('utf-8'))
 assert r['worklist_sha256']==digest(JOBS/'HISTORICAL_MISSING_807_REPLAY_WORKLIST.csv')
 assert r['source_coverage_csv_sha256']==digest(HISTORY)
 assert r['no_test_used'] is True
 assert r['unresolved_candidates']==807


def test_no_heldout_columns():
 for p in (STORE/'shortlists').rglob('train_only_shortlist.csv'):
  with p.open() as f: cols=next(csv.reader(f))
  assert not any(token in str(col).lower() for col in cols for token in ['validation','internal_test','holdout','test_','_ood','ood_'])


def test_refuse_existing_destination():
 with pytest.raises(GateClosed,match='Destination exists'):
  execute(Path('/mnt/data'),STORE)


def test_refuse_tampered_csv(tmp_path):
 p=STORE/'shortlists'/'seed1001'/'CRMT'
 target=tmp_path/'seed1001'/'CRMT';target.mkdir(parents=True)
 for name in ('train_only_shortlist.csv','train_only_shortlist_lock.json'):
  (target/name).write_bytes((p/name).read_bytes())
 (target/'train_only_shortlist.csv').write_bytes((target/'train_only_shortlist.csv').read_bytes()+b'\n')
 with pytest.raises(GateClosed,match='SHA-256'):
  load_gate1_shortlist(target,method='CRMT',seed=1001,expected_manifest_sha256=MANIFEST)


def test_historical_stage_report():
 r=json.loads((STORE/'stage_report.json').read_text('utf-8'))
 assert r['train_source_runs']==150 and r['candidate_slots']==3000
 assert r['planned_val_block_evaluations']==354000
 assert r['index_sha256']==digest(STORE/'train_only_30seed_5method_shortlist_index.csv')


def test_23_action_zip_checksums_match_preserved_manifest():
 from zipfile import ZipFile
 now=json.loads((ROOT/'SOURCE_ARTIFACT_LOCK_23_TRAIN_VAL.json').read_text())
 with ZipFile('/mnt/data/CRMT_OPENCEM_RAW_RECOVERY_TOOLS_2026-10-08.zip') as z:
  original=json.loads(z.read('locks/CRMT_EAAI_ACTIONS_ARCHIVE_BACKUP_MANIFEST_2026-10-08.json'))
 ref={r['artifact_id']:r for r in original['files']}
 assert len(now['artifacts'])==23
 for r in now['artifacts']:
  old=ref[r['artifact_id']]
  assert (old['sha256'],old['size_bytes'],old['zip_member_count'])==(r['sha256'],r['bytes'],r['entries'])
  assert r['zip_crc_pass'] is True


def test_full_preflight_refuses_missing_raw_and_source(tmp_path):
 import importlib.util
 loc=ROOT/'tools'/'preflight_30seeds.py'
 spec=importlib.util.spec_from_file_location('preflight_30',loc)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 from argparse import Namespace
 report=module.run(Namespace(recovery_root=ROOT,gate2_root=ROOT,
   repo_root=tmp_path/'not_present',raw_root=tmp_path/'not_present',
   verification_csv=tmp_path/'verify.csv',block_lock_json=tmp_path/'block_lock.json'))
 assert report['status']=='BLOCKED_DO_NOT_RUN'
 assert report['checks']['shortlists']['verified_shortlists']==150
 assert report['checks']['shortlists']['passed'] is True
 assert report['checks']['local_raw_data']['verified_files']==0
 assert report['checks']['canonical_block_lock']['passed'] is False
 assert report['checks']['frozen_repository']['passed'] is False
