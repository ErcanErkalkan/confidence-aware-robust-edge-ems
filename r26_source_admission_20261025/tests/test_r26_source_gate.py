import copy,hashlib,json,sys,zipfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from r26_source_gate import *
@pytest.fixture(scope='module')
def sample():return json.loads((ROOT/'config/R26_SOURCE_CANDIDATES.json').read_text())
@pytest.fixture(scope='module')
def report(sample):return audit_catalog(sample)
def test_01_r25_archive_has_true_historic_sources():assert check_reference()['verified_as']=='SEEN_HISTORICAL_TRAIN_ONLY'
def test_02_eight_source_records(sample):assert len(sample)==8
def test_03_no_candidate_passes(report):assert report['source_approved_count']==0 and all(not x['independent_test_eligible'] for x in report['candidates'])
def test_04_no_raw_sha_claims(sample):assert all(x['raw_sha256'] is None and x['raw_retrieved'] is False for x in sample)
def test_05_full_publisher_evidence_links(sample):assert all(x['source_evidence'] for x in sample)
def test_06_edp_ai_tool_terms_enforced(sample):
 x=screen(next(x for x in sample if x['candidate_id']=='UNSW_ENERGY_DATA_PLATFORM'))
 assert 'DATA_USE_IN_THIS_ENV_UNVERIFIED_OR_PROHIBITED' in x['reasons']
def test_07_mcut_restricted(sample):
 x=screen(next(x for x in sample if x['candidate_id']=='MCUT_ISLANDED'))
 assert 'SOURCE_ACCESS_NOT_OPEN' in x['reasons']
def test_08_porto_hourly_not_upscaled(sample):
 x=screen(next(x for x in sample if x['candidate_id']=='PORTO_DAILY_EMS'))
 assert 'NATIVE_CADENCE_TOO_COARSE_OR_UNKNOWN_FOR_2MIN_CONTROL' in x['reasons']
def test_09_brazil_island_grid_mismatch(sample):
 x=screen(next(x for x in sample if x['candidate_id']=='BRAZIL_STAR'))
 assert 'MISSING_VERIFIED_HAS_GRID_BOUNDARY' in x['reasons']
def test_10_pvdaq_no_full_microgrid(sample):
 x=screen(next(x for x in sample if x['candidate_id']=='PVDAQ_NLR'))
 assert 'MISSING_VERIFIED_HAS_LOAD' in x['reasons']
def test_11_legacy_exposed_refused(sample):
 s=dict(sample[0],candidate_id='OPSD_REPLAY_2026')
 with pytest.raises(Blocked,match='HISTORIC'):screen(s)
def test_12_duplicate_ids_refused(sample):
 with pytest.raises(Blocked,match='DUPLICATE'):audit_catalog(sample+[sample[0]])
def test_13_schema_extra_refused(sample):
 with pytest.raises(Blocked,match='SCHEMA'):screen(dict(sample[0],real_test=True))
def test_14_no_forged_license_success(sample):
 x=dict(sample[0],license_status='verified_permissive',data_use_ai_allowed=True)
 assert not screen(x)['independent_test_eligible']
def test_15_all_self_declarations_cannot_go(sample):
 x=dict(sample[0],raw_sha256='f'*64,raw_retrieved=True,raw_source_audit=True,previous_exposure_audit=True,source_independence_attested=True,has_grid_boundary=True,documented_objective_mapping=True,sampling_minutes=1,license_status='verified_permissive',data_use_ai_allowed=True)
 assert screen(x)['status'].startswith('NO_GO')
def test_16_hash_change_rejected(tmp_path):
 p=tmp_path/'raw.csv';p.write_bytes(b'original');withsha=sha(p.read_bytes());p.write_bytes(b'altered')
 with pytest.raises(Blocked,match='MISMATCH'):verify_raw(p,withsha)
def test_17_good_sha_is_only_integrity(tmp_path):
 p=tmp_path/'raw.csv';p.write_bytes(b'original')
 assert verify_raw(p,sha(p.read_bytes()))['status'].startswith('HASH_ONLY')
def test_18_invalid_digest(sample):
 x=dict(sample[0],raw_sha256='bad');
 with pytest.raises(Blocked,match='SHA'):screen(x)
def test_19_bad_date_not_automatic_approval(sample):
 x=dict(sample[0],published='1999-01-01')
 assert screen(x)['status'].startswith('NO_GO')
def test_20_catalog_fingerprint_deterministic(sample):
 assert audit_catalog(sample)['catalog_sha256']==audit_catalog(sample)['catalog_sha256']
def test_21_protocol_lock_blocked(report):assert not reject_prelock_until_external_evidence(report)['new_R19_optimizer']
def test_22_user_review_claim_ignored(report):
 assert not reject_prelock_until_external_evidence(report,{'approved':True,'timestamp':'2026-10-25'})['new_TEST']
def test_23_edp_no_ai_false(sample):assert next(x for x in sample if x['candidate_id']=='UNSW_ENERGY_DATA_PLATFORM')['data_use_ai_allowed'] is False
def test_24_all_objectives_four():assert len(OBJECTIVES)==4
def test_25_sha_r16_zip_unchanged():assert check_reference()['R16_inside_R25_sha256']==SHA_R25
def test_26_detect_original_zip_corruption(tmp_path):
 p=tmp_path/'bad.zip';p.write_bytes(b'invalid')
 with pytest.raises(zipfile.BadZipFile):check_reference(p)
def test_27_no_raw_received_for_pvdaq(report):assert next(x for x in report['candidates'] if x['candidate_id']=='PVDAQ_NLR')['raw_sha256'] is None
def test_28_invalid_cadence(sample):
 x=dict(sample[0],sampling_minutes=-1)
 with pytest.raises(Blocked,match='CADENCE'):screen(x)
def test_29_restricted_ai_ingest_fails_closed(sample):
 x=dict(next(i for i in sample if i['candidate_id']=='UNSW_ENERGY_DATA_PLATFORM'),access='open')
 assert not screen(x)['prospective_R19_AUDIT_eligible']
def test_30_existing_exposure_not_ignored(report):assert sorted(report['historical_excluded_sources'])==['OPENCEM_INTERNAL_2026','OPSD_REPLAY_2026']
from r26_schema_probe import probe_csv,SchemaBlocked

def _write_csv(tmp_path,minutes=2,include_soc=True,n=9,dup=False):
 import datetime as dt,csv
 p=tmp_path/'test.csv'
 cols=['timestamp','site_id','load_kw','pv_kw','grid_kw']+(['battery_soc_pct'] if include_soc else [])
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
  for i in range(n):
   t=(dt.datetime(2026,1,1,tzinfo=dt.timezone.utc)+dt.timedelta(minutes=minutes*(i if not dup or i!=n-1 else i-1))).isoformat()
   row={'timestamp':t,'site_id':'site_1','load_kw':2.2,'pv_kw':1.1,'grid_kw':1.1,'battery_soc_pct':51.0}
   w.writerow({k:row[k] for k in cols})
 return p

def test_31_good_2min_schema(tmp_path):assert probe_csv(_write_csv(tmp_path))['sites'][0]['median_native_minutes']==2
def test_32_good_1min_schema(tmp_path):assert probe_csv(_write_csv(tmp_path,minutes=1))['sites'][0]['median_native_minutes']==1
def test_33_coarse_30min_blocked(tmp_path):
 with pytest.raises(SchemaBlocked,match='COARSE'):probe_csv(_write_csv(tmp_path,minutes=30))
def test_34_no_battery_soc_blocked(tmp_path):
 with pytest.raises(SchemaBlocked,match='SOC'):probe_csv(_write_csv(tmp_path,include_soc=False))
def test_35_duplicate_timestamp_blocked(tmp_path):
 with pytest.raises(SchemaBlocked,match='DUPLICATE'):probe_csv(_write_csv(tmp_path,dup=True))
def test_36_minute_mapping_must_be_declared(tmp_path):
 with pytest.raises(SchemaBlocked,match='COARSE'):probe_csv(_write_csv(tmp_path,minutes=1),allow_1min_to_2min=False)
def test_37_schema_cannot_approve_external(tmp_path):assert not probe_csv(_write_csv(tmp_path))['is_independent_new_TEST']
def test_38_test_never_certifies_physical(tmp_path):assert not probe_csv(_write_csv(tmp_path))['source_safety_certified']
def test_39_grid_column_not_contractual_cap(tmp_path):assert probe_csv(_write_csv(tmp_path))['measured_grid_not_necessarily_contract_cap']
def test_40_few_rows_fail(tmp_path):
 with pytest.raises(SchemaBlocked,match='TOO_FEW'):probe_csv(_write_csv(tmp_path,n=1))
