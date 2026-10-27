import pytest
from crmt_edge_ems.contracts import ContractError
from data_adapters.external_source_gate import REQUIRED,source_admission

def unknown():
    return {'source_id':'UNADMITTED_METADATA_ONLY',
        'evidence':{f:{'value':'','basis':'UNKNOWN','evidence_sha256':''} for f in REQUIRED},
        'objective_mapping':{'cap_violation_pct_total':['load_measurement','pv_measurement','grid_contract_limits'],
            'lfp_cycle_loss_pct':['battery_chemistry','battery_power','battery_soc'],
            'ramp95_kw_per_min':['timestamp_resolution','grid_measurement'],'flip_per_day':['controller_action_observability']}}

def test_metadata_cannot_supply_invented_physical_measurements():
    r=source_admission(unknown());assert r['classification']=='INSUFFICIENT_EVIDENCE' and not r['independent_test_ready']

def test_prohibited_license_and_unavailable_download():
    r=unknown();r['evidence']['ai_cloud_permissions']['basis']='PROHIBITED'
    assert source_admission(r)['classification']=='LICENSE_BLOCKED'
    r=unknown();r['evidence']['official_download']['basis']='UNAVAILABLE'
    assert source_admission(r)['classification']=='DOWNLOAD_BLOCKED'

def test_unsupported_physical_objectives_rejected():
    r=unknown();del r['objective_mapping']['flip_per_day']
    with pytest.raises(ContractError): source_admission(r)