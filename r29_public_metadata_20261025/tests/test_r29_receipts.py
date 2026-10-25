import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def load(name):return json.loads((P/'results'/name).read_text())
def test_01_real_aggregate_2072():assert load('R29_PUBLIC_PECAN_AGGREGATES.json')['n_records']==2072
def test_02_130_columns():assert load('R29_PUBLIC_PECAN_AGGREGATES.json')['n_columns']==130
def test_03_all_row_widths_checked():assert load('R29_PUBLIC_PECAN_AGGREGATES.json')['row_width_failures']==0
def test_04_no_duplicate_ids():assert load('R29_PUBLIC_PECAN_AGGREGATES.json')['duplicate_dataids']==0
def test_05_metadata_385():assert load('R29_PUBLIC_PECAN_AGGREGATES.json')['candidate_count']==385
def test_06_availability_monotonic():
    x=load('R29_PUBLIC_PECAN_AGGREGATES.json')['reported_1min_availability_minimum_percent'];assert list(x.values())==sorted(x.values(),reverse=True)
def test_07_battery_not_automatic_certification():
    x=load('R29_PUBLIC_PECAN_AGGREGATES.json');assert x['additional_metadata_flags']['battery1']['among_385']==6 and not x['battery_LFP_chemistry_verified']
def test_08_ess_not_automatic_certification():
    x=load('R29_PUBLIC_PECAN_AGGREGATES.json');assert x['additional_metadata_flags']['energy_storage_system']['among_385']==1 and not x['native_same_timestep_grid_pv_battery_SOC_verified']
def test_09_states_sum_385():
    x=load('R29_PUBLIC_PECAN_AGGREGATES.json');assert sum(x['candidate_geographic_metadata_aggregates'].values())==x['candidate_count']
def test_10_original_sha_unavailable():
    x=load('R29_PUBLIC_PECAN_AGGREGATES.json');assert x['original_metadata_csv_sha256'] is None and not x['original_metadata_csv_download_successful']
def test_11_physics_gate_remains_closed():assert not load('R29_PUBLIC_PECAN_AGGREGATES.json')['R19_B10_R23_validated_on_data']
def test_12_test_gate_remains_closed():assert load('R29_PUBLIC_PECAN_AGGREGATES.json')['independent_new_TEST']=='NO_GO'
def test_13_zenodo_specific_license_observed():assert load('R29_BRAZIL_STAR_LICENSE_EVIDENCE.json')['license_id_observed_in_extracted_api_content']=='cc-by-4.0'
def test_14_zenodo_raw_not_downloaded():assert not load('R29_BRAZIL_STAR_LICENSE_EVIDENCE.json')['original_zip_bytes_downloaded']
def test_15_zenodo_no_grid_equiv():assert not load('R29_BRAZIL_STAR_LICENSE_EVIDENCE.json')['four_original_R19_objectives_equivalent']
