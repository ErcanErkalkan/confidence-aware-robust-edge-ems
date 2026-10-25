import copy,hashlib,io,json,sys,zipfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from brazil_zip_audit import (check_zip,inspect_file,text_shape,EvidenceBlocked,safe_name,PUBLISHED_MD5,MAX_ARCHIVE_BYTES)
from access_gate import evaluate,rights_matrix

@pytest.fixture
def fake_original(tmp_path):
    inner=io.BytesIO()
    with zipfile.ZipFile(inner,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('2018-01-01-STAR-A_Battery.csv','timestamp,current,Ah,SOC,cycles,discharges,voltage,power,discharge,charge\n2018-01-01T00:00:00,2,4,80,1,0,1200,100,0,0\n')
        z.writestr('2018-01-01-STAR-A_PV.csv','timestamp,V,P,E,mode\n2018-01-01T00:00:00,100,150,0,1\n')
        z.writestr('2018-01-01-STAR-A_IAM.csv','timestamp,W,reactive,voltage,meterid\n2018-01-01T00:00:00,180,0,120,iam_1\n')
    path=tmp_path/'synthetic_fixture_not_publisher.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as o:o.writestr('CSVs.zip',inner.getvalue())
    return path,hashlib.md5(path.read_bytes()).hexdigest()


def test_01_metadata_has_publisher_source():assert rights_matrix()['BRAZIL_STAR']['source_url'].startswith('https://zenodo.org/')
def test_02_published_md5_fixed():assert PUBLISHED_MD5=='b4f4bad22ba1d896937cfe555f41b25c'
def test_03_brazil_3_systems():assert len(rights_matrix()['BRAZIL_STAR']['officially_documented_sensors'])==3
def test_04_brazil_grid_not_documented():assert rights_matrix()['BRAZIL_STAR']['grid_kw']=='NOT_DOCUMENTED'
def test_05_brazil_total_load_not_assumed():assert rights_matrix()['BRAZIL_STAR']['total_site_load_from_all_IAM']=='UNVERIFIED_COVERAGE'
def test_06_brazil_unknown_cadence():assert rights_matrix()['BRAZIL_STAR']['sampling_frequency']=='NOT_VERIFIED_FROM_RAW'
def test_07_pecan_university_75():assert '75 homes' in rights_matrix()['PECAN_STREET']['free_university_scope']
def test_08_pecan_funded_prohibited_free():assert rights_matrix()['PECAN_STREET']['free_university_funded_research']=='NOT_PERMITTED'
def test_09_pecan_ai_sharing_unverified():assert 'NOT_PREAPPROVED' in rights_matrix()['PECAN_STREET']['ai_processing_sharing']
def test_10_no_auto_go():
    r=evaluate(rights_matrix())
    assert r['unseen_independent_TEST']=='NO_GO' and not r['new_dataset_accepted']
def test_11_forged_review_no_go():
    r=evaluate(rights_matrix(),{'all_approved':True,'licensing_officer':'fake','source_independent':True})
    assert not r['new_dataset_accepted']
def test_12_inspection_not_test(fake_original):
    p,md5=fake_original;r=inspect_file(p,published_md5=md5)
    assert r['nested_zip_members']==1 and r['files_by_system']=={'Battery':1,'IAM':1,'PV':1}
    assert r['site_file_counts']=={'STAR-A':3}
    assert not r['is_independent_new_TEST'] and not r['is_confirmatory_R19_AUDIT']
    assert not r['license_use_permission_verified'] and not r['measured_grid_import_export_verified']
def test_13_raw_md5_rejects_not_publisher(fake_original):
    p,_=fake_original
    with pytest.raises(EvidenceBlocked,match='MD5_MISMATCH'):inspect_file(p)
def test_14_missing_zip(tmp_path):
    with pytest.raises(EvidenceBlocked,match='RAW_NOT_PRESENT'):inspect_file(tmp_path/'missing.zip')
def test_15_safe_member_names():
    assert safe_name('dir/file.csv') and not safe_name('../evil.csv') and not safe_name('/etc/passwd')
    assert not safe_name('C:/temp/data.csv')
def test_16_path_traversal_reject(tmp_path):
    p=tmp_path/'zip.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('../evil.csv','x')
    with zipfile.ZipFile(p) as z:
        with pytest.raises(EvidenceBlocked,match='TRAVERSAL'):check_zip(z)
def test_17_nested_corruption_block(tmp_path):
    p=tmp_path/'zip.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('CSVs.zip',b'not_zip')
    m=hashlib.md5(p.read_bytes()).hexdigest()
    with pytest.raises(EvidenceBlocked,match='INVALID_NESTED_ZIP'):inspect_file(p,published_md5=m)
def test_18_non_utf8_csv_not_claimed():assert text_shape(b'\xff\x80\n',5)['parse_status']=='NON_UTF8_SAMPLE'
def test_19_empty_csv_not_claimed():assert text_shape(b'',10)['parse_status']=='EMPTY_SAMPLE'
def test_20_variable_columns_not_certified():
    z=text_shape(b'a,b,c\n1,2\n3,4,5\n',5)
    assert z['parse_status']=='SAMPLE_ONLY_NOT_SCHEMA_CERTIFIED'
def test_21_no_extraction_to_disk(fake_original,tmp_path):
    p,h=fake_original;inspect_file(p,published_md5=h)
    assert not (tmp_path/'CSVs.zip').exists()
def test_22_R26_eight_sources_remain_blocked():
    r=json.loads((ROOT/'reference/R26_SOURCE_GATE_ORIGINAL.json').read_text())
    assert r['candidate_count']==8 and r['source_approved_count']==0
def test_23_R26_metadata_preserved():
    r=json.loads((ROOT/'reference/R26_SOURCE_CANDIDATES_ORIGINAL.json').read_text())
    assert len(r)==8 and next(z for z in r if z['candidate_id']=='BRAZIL_STAR')['raw_sha256'] is None
def test_24_original_dataset_never_renamed_new_test():
    assert evaluate(rights_matrix())['r19_30_seed_runs']=='NOT_RUN'
def test_25_original_body_reader_limits(fake_original):
    p,h=fake_original;d=inspect_file(p,published_md5=h)
    assert len(d['sampled_files'])==3 and all(z['sampled_rows']>=1 for z in d['sampled_files'])
def test_26_license_default_unverified():assert rights_matrix()['BRAZIL_STAR']['license'].startswith('RECORD_RIGHTS_NOT_RESOLVED')
def test_27_grid_cap_separate_from_power():assert rights_matrix()['BRAZIL_STAR']['contracted_grid_cap']=='NOT_DOCUMENTED'
def test_28_free_not_all_datasets():assert '75 homes' in rights_matrix()['PECAN_STREET']['free_university_scope']
def test_29_malicious_windows_path():assert not safe_name('..\\evil')
def test_30_fake_responses_not_authorization():
    x=evaluate(rights_matrix(),{'from_provider':'yes','approved':True,'public_key':'0'*64})
    assert x['independent_pre_registration']=='NOT_VERIFIED'
