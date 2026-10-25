import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_receipt_has_no_data_promotion():
    x=json.loads((ROOT/'results/R28_PUBLIC_METADATA_EVIDENCE.json').read_text())
    assert x['source_admission']=='NO_GO'
    assert x['verified_new_raw_time_series']==0
    assert x['metadata_csv_original_bytes_acquired'] is False
    assert x['independent_new_TEST']=='NO_GO'

def test_funded_column_is_not_assumed_clear():
    x=json.loads((ROOT/'results/R28_PUBLIC_METADATA_EVIDENCE.json').read_text())
    assert x['provider_pecan_license_contradiction']['resolution'].startswith('WRITTEN_PROVIDER')

def test_email_was_only_drafted():
    x=json.loads((ROOT/'results/R28_PUBLIC_METADATA_EVIDENCE.json').read_text())
    assert x['pecan_email']['draft_created_in_connected_gmail']
    assert x['pecan_email']['email_sent'] is False

def test_brazil_license_not_guessed():
    x=json.loads((ROOT/'results/R28_PUBLIC_METADATA_EVIDENCE.json').read_text())
    assert x['brazil_star']['license_verification']=='UNRESOLVED'
