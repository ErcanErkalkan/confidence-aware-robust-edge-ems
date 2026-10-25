from pathlib import Path
import sys,csv,io,pytest,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from public_cohort_audit import load_public_csv,screen,MetadataError
FIELDS=['dataid','active_record','building_type','pv','grid','solar','state','egauge_1min_min_time','egauge_1min_max_time','egauge_1min_data_availability','battery1','energy_storage_system']
def row(id='1',**kwargs):
    r=dict(dataid=id,active_record='yes',building_type='Single-Family Home 001 (Master)',pv='yes',grid='yes',solar='yes',state='Texas',egauge_1min_min_time='2025-01-01 00:00:00-06',egauge_1min_max_time='2025-03-01 00:00:00-06',egauge_1min_data_availability='95%',battery1='',energy_storage_system='')
    r.update(kwargs);return r
def rows(data,fields=FIELDS):
    buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(data);return buf.getvalue()
def flat(data):return rows(data).replace('_','\\_').replace('\n',' ')

def test_01_exact_metadata_1min_count():assert screen(rows([row('1'),row('2',grid='')]),'original')['pv_grid_solar_positive_1min_metadata_candidates']==1
def test_02_no_new_test():assert screen(rows([row()]),'original')['independent_new_TEST']=='NO_GO'
def test_03_flat_public_transform():assert screen(flat([row('1'),row('2')]),'text_extractor_flattened')['row_count']==2
def test_04_flat_and_original_counts_agree():assert screen(flat([row('1'),row('2',pv='')]),'text_extractor_flattened')['pv_yes']==screen(rows([row('1'),row('2',pv='')]),'original')['pv_yes']
def test_05_battery_not_SOC():assert screen(rows([row(battery1='yes')]),'original')['battery_chemistry_LFP_proven'] is False
def test_06_grid_no_contract_cap():assert not screen(rows([row()]),'original')['contractual_grid_cap_proven']
def test_07_no_controller_actions():assert not screen(rows([row()]),'original')['controller_flip_action_proven']
def test_08_no_date():assert screen(rows([row(egauge_1min_min_time='')]),'original')['pv_grid_solar_positive_1min_metadata_candidates']==0
def test_09_nonpositive_pct():assert screen(rows([row(egauge_1min_data_availability='0%')]),'original')['pv_grid_solar_positive_1min_metadata_candidates']==0
def test_10_invalid_pct():assert screen(rows([row(egauge_1min_data_availability='hello')]),'original')['pv_grid_solar_positive_1min_metadata_candidates']==0
def test_11_future_to_past():assert screen(rows([row(egauge_1min_max_time='2024-01-01 00:00:00-06')]),'original')['pv_grid_solar_positive_1min_metadata_candidates']==0
def test_12_90_threshold():assert screen(rows([row(egauge_1min_data_availability='89%')]),'original')['candidate_reported_availability_at_least_pct']['90']==0
def test_13_95_threshold():assert screen(rows([row(egauge_1min_data_availability='95%')]),'original')['candidate_reported_availability_at_least_pct']['95']==1
def test_14_99_threshold():assert screen(rows([row(egauge_1min_data_availability='98%')]),'original')['candidate_reported_availability_at_least_pct']['99']==0
def test_15_active_record_not_source_proof():assert screen(rows([row(active_record='yes')]),'original')['independent_source_custody_proven'] is False
def test_16_duplicates_block():
    with pytest.raises(MetadataError,match='DUPLICATE'):screen(rows([row(),row()]),'original')
def test_17_bad_row_length():
    with pytest.raises(MetadataError,match='WIDTH'):screen(rows([row()])+'1,2\n','original')
def test_18_missing_columns():
    with pytest.raises(MetadataError,match='MISSING'):load_public_csv(rows([row()]).replace(',solar,',',not_solar,'), 'original')
def test_19_forbidden_raw():
    with pytest.raises(MetadataError,match='RAW_LIKE'):
        fields=FIELDS+['battery_soc_pct'];load_public_csv(rows([dict(row(),battery_soc_pct='90')],fields),'original')
def test_20_blank():
    with pytest.raises(MetadataError):load_public_csv('','original')
def test_21_invalid_mode():
    with pytest.raises(MetadataError):load_public_csv(rows([row()]),'whatever')
def test_22_wrong_flat_newline():
    with pytest.raises(MetadataError,match='UNEXPECTED'):load_public_csv(rows([row()]),'text_extractor_flattened')
def test_23_no_parse_flat():
    with pytest.raises(MetadataError,match='NO_EXTRACTABLE'):load_public_csv('dataid,pv,grid,solar,egauge_1min_min_time,egauge_1min_max_time,egauge_1min_data_availability', 'text_extractor_flattened')
def test_24_numeric_site_id():
    with pytest.raises(MetadataError,match='DUPLICATE_OR_INVALID_ID'):screen(rows([row(id='site1')]),'original')
def test_25_ess_flag_only():
    a=screen(rows([row(energy_storage_system='yes')]),'original');assert a['optional_metadata_fields']['energy_storage_system']['within_metadata_candidate_yes']==1 and not a['approved_r19_R23_experiment']
def test_26_state_counts():assert screen(rows([row('1',state='Texas'),row('2',state='New York')]),'original')['candidate_state_aggregates']=={'New York':1,'Texas':1}
def test_27_quote_csv():assert screen(rows([row(building_type='Single-Family, Home')]),'original')['row_count']==1
def test_28_no_new_raw():assert screen(rows([row()]),'original')['actual_joint_measured_grid_pv_SOC_at_same_timestamps'] is None
