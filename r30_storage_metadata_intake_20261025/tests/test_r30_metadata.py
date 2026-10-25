import csv, io, json, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from r30_metadata_gate import evaluate_public_metadata,run_file,IntakeError
FIELDS=['dataid','active_record','building_type','pv','grid','solar','battery1','energy_storage_system','egauge_1min_min_time','egauge_1min_max_time','egauge_1min_data_availability']
def row(id='1',**override):
 d={'dataid':id,'building_type':'Single-Family Home 001 (Master)','pv':'yes','grid':'yes','solar':'yes','battery1':'','energy_storage_system':'','egauge_1min_min_time':'2025-01-01 00:00:00-06','egauge_1min_max_time':'2025-05-01 00:00:00-05','egauge_1min_data_availability':'96%','active_record':'yes'};d.update(override);return d
def make(rows,fields=FIELDS):
 out=io.StringIO();w=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows);return out.getvalue()
def gate(rows):return evaluate_public_metadata(make(rows),'original_csv',provenance='SYNTHETIC_FIXTURE')
def test_positive_candidate():assert gate([row()])['groups']['pv_grid_solar_one_min']['public_home_resident_records']==1
def test_dataid_not_house():assert gate([row()])['unique_physical_houses_count'] is None
def test_empty_grid():assert gate([row(grid='')])['groups']['pv_grid_solar_one_min']['public_home_resident_records']==0
def test_empty_pv():assert gate([row(pv='')])['groups']['pv_grid_solar_one_min']['public_home_resident_records']==0
def test_empty_solar():assert gate([row(solar='')])['groups']['pv_grid_solar_one_min']['public_home_resident_records']==0
def test_no_interval():assert gate([row(egauge_1min_min_time='',egauge_1min_max_time='',egauge_1min_data_availability='')])['groups']['pv_grid_solar_one_min']['public_home_resident_records']==0
def test_zero_availability():assert gate([row(egauge_1min_data_availability='0%')])['groups']['pv_grid_solar_one_min']['public_home_resident_records']==0
def test_only_battery():assert gate([row(battery1='yes')])['groups']['storage_flag_union']['public_home_resident_records']==1
def test_only_ess():assert gate([row(energy_storage_system='yes')])['groups']['storage_flag_union']['public_home_resident_records']==1
def test_joint_storage_union_not_sum():
 r=gate([row('1',battery1='yes',energy_storage_system='yes'),row('2',battery1='yes')]);assert r['storage_flag_intersection_count']==1 and r['groups']['storage_flag_union']['public_home_resident_records']==2
def test_no_approved_dataset():assert gate([row()])['independent_test']=='NO_GO'
def test_no_physics_claim():assert gate([row()])['physically_valid_CRMT_objectives']==0
def test_no_identifiers_output():assert '12345' not in json.dumps(gate([row(id='12345')]))
def test_90_cutoff():assert gate([row(egauge_1min_data_availability='89%')])['groups']['pv_grid_solar_one_min']['advertised_one_min_availability_ge90']==0
def test_95_cutoff():assert gate([row(egauge_1min_data_availability='95%')])['groups']['pv_grid_solar_one_min']['advertised_one_min_availability_ge95']==1
def test_30day_window():assert gate([row()])['groups']['pv_grid_solar_one_min']['metadata_window_span_ge30days']==1
def test_short_window():assert gate([row(egauge_1min_max_time='2025-01-03 00:00:00-06')])['groups']['pv_grid_solar_one_min']['metadata_window_span_ge30days']==0
def test_bad_reverse_dates():
 with pytest.raises(IntakeError,match='NONPOSITIVE_WINDOW'):gate([row(egauge_1min_max_time='2024-12-01 00:00:00-06')])
def test_bad_timezone():
 with pytest.raises(IntakeError,match='TIMESTAMP_WITHOUT_TIMEZONE'):gate([row(egauge_1min_min_time='2025-01-01 00:00:00')])
def test_bad_avail_pct():
 with pytest.raises(IntakeError,match='AVAILABILITY_NOT_PERCENT'):gate([row(egauge_1min_data_availability='95')])
def test_bad_avail_over100():
 with pytest.raises(IntakeError,match='AVAILABILITY_RANGE'):gate([row(egauge_1min_data_availability='105%')])
def test_duplicate_id():
 with pytest.raises(IntakeError,match='DUPLICATE'):gate([row(),row()])
def test_non_numeric_id():
 with pytest.raises(IntakeError,match='DUPLICATE'):gate([row(id='site')])
def test_missing_header():
 with pytest.raises(IntakeError,match='MISSING'):evaluate_public_metadata(make([row()]).replace('battery1,','missing_battery,'), 'original_csv',provenance='fixture')
def test_untested_raw_col():
 fields=FIELDS+['battery_soc_pct'];rr=dict(row(),battery_soc_pct='95')
 with pytest.raises(IntakeError,match='PRIVATE'):evaluate_public_metadata(make([rr],fields), 'original_csv',provenance='fixture')
def test_header_duplicate():
 with pytest.raises(IntakeError,match='MISSING'):evaluate_public_metadata(make([row()]).replace('battery1,','pv,'), 'original_csv',provenance='fixture')
def test_flat_text():
 s=make([row(id='100'),row(id='200')]).replace('_','\\_').replace('\n',' ')
 x=evaluate_public_metadata(s,'normalized_extractor_text',provenance='fixture');assert x['public_metadata_record_count']==2
def test_flat_text_bad_newlines():
 with pytest.raises(IntakeError,match='EXTRACTOR_BOUNDARIES'):evaluate_public_metadata(make([row()]),'normalized_extractor_text',provenance='fixture')
def test_unsupported_mode():
 with pytest.raises(IntakeError,match='INPUT_MODE'):evaluate_public_metadata(make([row()]),'unknown',provenance='fixture')
def test_load_from_local_file(tmp_path):
 p=tmp_path/'public.csv';p.write_text(make([row()]))
 x=run_file(p,'original_csv');assert len(x['local_input_sha256'])==64 and not x['provider_original_bytes_authenticated']
def test_report_receipt_remains_no_go():
 p=ROOT/'results/R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json';x=json.loads(p.read_text());assert x['raw_homes_time_series_read']==0 and x['independent_new_TEST']=='NO_GO'
def test_report_battery_union_7():
 x=json.loads((ROOT/'results/R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json').read_text());assert x['storage_flag_union']['n']==7 and x['storage_flag_intersection']==0
def test_R29_counts_unmodified():
 x=json.loads((ROOT/'results/R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json').read_text());assert x['n_public_records']==2072 and x['n_metadata_candidates']==385
