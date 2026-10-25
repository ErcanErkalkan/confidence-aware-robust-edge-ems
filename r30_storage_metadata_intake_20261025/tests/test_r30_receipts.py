import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def receipt(name):return json.loads((ROOT/'results'/name).read_text())
def test_01_R29_original_reference_sha():
 p=ROOT/'results/R29_REFERENCE_AGGREGATES_UNMODIFIED.json';assert hashlib.sha256(p.read_bytes()).hexdigest()=='57dd870c0ca4b964b347f40779dbd9a9d6a87e762359989c6c663595e0b65ea3'
def test_02_R29_previous_count_matches():
 x=receipt('R29_REFERENCE_AGGREGATES_UNMODIFIED.json');y=receipt('R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json')
 assert x['candidate_count']==y['n_metadata_candidates']==385 and x['n_records']==y['n_public_records']==2072
def test_03_storage_sets_are_disjoint():
 x=receipt('R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json');assert x['storage_flag_union']['n']==7 and x['battery1']['n']==6 and x['energy_storage_system']['n']==1 and x['storage_flag_intersection']==0
def test_04_90pct_count_equals_five():
 x=receipt('R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json');assert x['storage_flag_union']['advertised_ge90_percent']==5 and x['storage_flag_union']['advertised_ge95_percent']==4
def test_05_provider_binary_not_retrieved():assert receipt('R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json')['original_csv_sha256'] is None
def test_06_no_raw_access_or_test():
 x=receipt('R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json');assert x['raw_homes_time_series_read']==0 and x['independent_new_TEST']=='NO_GO'
def test_07_brazil_binary_not_retrieved():assert not receipt('R30_ZENODO_LICENSE_AND_DOWNLOAD_STATUS.json')['publisher_raw_zip_direct_download_success']
def test_08_gates_no_promotion():
 x=json.loads((ROOT/'config/R30_DECISION_GATES.json').read_text());assert x['gates']['unseen_independent_TEST']=='NO_GO' and x['gates']['R19_prospective_30_seeds']=='NOT_RUN'
def test_09_not_seven_physical_homes():assert receipt('R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json')['n_distinct_physical_homes_verified'] is None
def test_10_no_locally_published_private_ids():
 x=(ROOT/'results/R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json').read_text()
 assert 'dataid\":' not in x and 'household_id' not in x
