import csv,io,sys,pytest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from metadata_gate import screen_csv_text,screen_file,MetadataBlocked
FIELDS=['dataid','pv','grid','solar','egauge_1min_min_time','egauge_1min_max_time','egauge_1min_data_availability']
def dataset(records,fields=FIELDS):
    t=io.StringIO();w=csv.DictWriter(t,fieldnames=fields);w.writeheader()
    for record in records:w.writerow(record)
    return t.getvalue()
def row(**kw):return dict({'dataid':'100','pv':'yes','grid':'yes','solar':'yes','egauge_1min_min_time':'2024-03-01 00:00:00-06','egauge_1min_max_time':'2024-04-01 23:59:00-05','egauge_1min_data_availability':'97%'},**kw)
def test_candidate_metadata_still_not_test():
    x=screen_csv_text(dataset([row()]));assert x['plausible_grid_solar_1min_site_metadata_count']==1
    r=x['rows'][0];assert r['metadata_joint_grid_solar_1min_candidate'] and not r['native_battery_SOC_verified'] and not r['new_unseen_TEST_eligible']
def test_missing_grid_blocks_candidate():assert screen_csv_text(dataset([row(grid='')]))['plausible_grid_solar_1min_site_metadata_count']==0
def test_missing_solar_blocks_candidate():assert screen_csv_text(dataset([row(solar='')]))['plausible_grid_solar_1min_site_metadata_count']==0
def test_missing_pv_blocks_candidate():assert screen_csv_text(dataset([row(pv='')]))['plausible_grid_solar_1min_site_metadata_count']==0
def test_missing_window_blocks_candidate():assert screen_csv_text(dataset([row(egauge_1min_min_time='',egauge_1min_max_time='',egauge_1min_data_availability='')]))['plausible_grid_solar_1min_site_metadata_count']==0
def test_zero_availability_no_candidate():assert screen_csv_text(dataset([row(egauge_1min_data_availability='0%')]))['plausible_grid_solar_1min_site_metadata_count']==0
def test_duplicate_dataid_rejected():
    with pytest.raises(MetadataBlocked,match='DUPLICATE'):screen_csv_text(dataset([row(),row()]))
def test_missing_fields_rejected():
    with pytest.raises(MetadataBlocked,match='MISSING'):screen_csv_text(dataset([{k:v for k,v in row().items() if k in FIELDS[:-1]}],FIELDS[:-1]))
def test_raw_forged_columns_rejected():
    with pytest.raises(MetadataBlocked,match='RAW_LIKE'):screen_csv_text(dataset([dict(row(),battery_soc_pct='50')],FIELDS+['battery_soc_pct']))
def test_bad_time_rejected():
    with pytest.raises(MetadataBlocked,match='TIMESTAMP'):screen_csv_text(dataset([row(egauge_1min_min_time='2024-02-30 00:00:00-05')]))
def test_naive_time_rejected():
    with pytest.raises(MetadataBlocked,match='TIMESTAMP_NO_TZ'):screen_csv_text(dataset([row(egauge_1min_min_time='2024-02-29 00:00:00')]))
def test_reverse_time_rejected():
    with pytest.raises(MetadataBlocked,match='INVERTED'):screen_csv_text(dataset([row(egauge_1min_max_time='2020-01-01 23:59:00-05')]))
def test_wrong_availability_rejected():
    with pytest.raises(MetadataBlocked,match='AVAILABILITY_UNIT'):screen_csv_text(dataset([row(egauge_1min_data_availability='99')]))
def test_over100_rejected():
    with pytest.raises(MetadataBlocked,match='AVAILABILITY_RANGE'):screen_csv_text(dataset([row(egauge_1min_data_availability='110%')]))
def test_blank_catalog_rejected():
    with pytest.raises(MetadataBlocked,match='EMPTY_CATALOG'):screen_csv_text(dataset([]))
def test_actual_file_is_not_test(tmp_path):
    p=tmp_path/'public_metadata.csv';p.write_text(dataset([row()]))
    r=screen_file(p);assert len(r['local_metadata_sha256'])==64 and r['approved_r19_sources']==0
