"""Evidence completeness screening; never permission to acquire restricted data."""
from __future__ import annotations
from pathlib import Path
from crmt_edge_ems.contracts import ContractError, digest, file_hash
from crmt_edge_ems.provenance import contained_path

REQUIRED=('source_identity','official_download','license','ai_cloud_permissions','timestamp_resolution',
    'pv_measurement','load_measurement','grid_measurement','battery_presence','battery_soc','battery_chemistry',
    'battery_power','grid_contract_limits','controller_action_observability','continuous_coverage','historical_exposure')

def source_admission(record, *, evidence_root=None):
    if not isinstance(record,dict) or set(record)!={'source_id','evidence','objective_mapping'}: raise ContractError('source admission schema')
    evidence=record['evidence']
    if not isinstance(record['source_id'],str) or not record['source_id'].strip() or set(evidence)!=set(REQUIRED): raise ContractError('source evidence fields required')
    missing=[]; rejected=[]; license_blocked=False; download_blocked=False
    for field in REQUIRED:
        e=evidence[field]
        if not isinstance(e,dict) or set(e)!={'value','basis','evidence_sha256'}: raise ContractError('field evidence schema')
        if e['basis'] not in {'MEASURED','PREDECLARED_MODEL','UNKNOWN','PROHIBITED','UNAVAILABLE'}: raise ContractError('unknown evidence basis')
        h=e['evidence_sha256']
        if e['basis'] in {'UNKNOWN','UNAVAILABLE'} or not isinstance(e['value'],str) or not e['value'].strip() or not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h): missing.append(field)
        # A typed hash string alone is not inspected evidence. Evidence files
        # are content-addressed under an explicit root; no network downloads.
        if e['basis'] in {'MEASURED','PREDECLARED_MODEL'}:
            if evidence_root is None or not isinstance(h,str) or len(h)!=64:
                missing.append(field+':uninspected_evidence_bytes')
            else:
                target=contained_path(evidence_root,h)
                if not target.is_file() or file_hash(target)!=h:
                    missing.append(field+':missing_or_mismatched_evidence_bytes')
        if e['basis']=='PROHIBITED':
            rejected.append(field)
            license_blocked |= field in {'license','ai_cloud_permissions'}
        download_blocked |= field=='official_download' and e['basis']=='UNAVAILABLE'
    # Model-only assertions cannot establish real-world source identity,
    # measurement availability, licensing, cloud rights, or exposure history.
    AUTHORITY_FIELDS={'source_identity','official_download','license','ai_cloud_permissions','historical_exposure'}
    MEASUREMENT_FIELDS={'pv_measurement','load_measurement','grid_measurement','battery_presence','battery_soc','battery_chemistry','battery_power','grid_contract_limits','controller_action_observability','timestamp_resolution','continuous_coverage'}
    for field in AUTHORITY_FIELDS|MEASUREMENT_FIELDS:
        if evidence[field]['basis']=='PREDECLARED_MODEL':
            missing.append(field+':independent_primary_evidence_required')
    mappings=record['objective_mapping']
    if set(mappings)!={'cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day'}: raise ContractError('all four objectives must be mapped')
    required_mapping={
        'cap_violation_pct_total':{'grid_measurement','grid_contract_limits'},
        'lfp_cycle_loss_pct':{'battery_soc','battery_chemistry','battery_power'},
        'ramp95_kw_per_min':{'timestamp_resolution','grid_measurement'},
        'flip_per_day':{'timestamp_resolution','controller_action_observability'},
    }
    for objective,fields in mappings.items():
        if not isinstance(fields,list) or not fields or any(f not in REQUIRED for f in fields): raise ContractError('invalid physical objective mapping')
        if any(evidence[f]['basis'] in {'UNKNOWN','UNAVAILABLE','PROHIBITED'} for f in fields): missing.append('objective:'+objective)
        if not required_mapping[objective].issubset(fields): missing.append('objective:'+objective+':physical_dependency_mapping')
    # Until an independent provider/license authenticator exists, an internally
    # hashed document cannot be classified as an accepted external source.
    if not missing and not rejected and not license_blocked and not download_blocked:
        missing.append('independent_provider_authenticity_and_license_attestation')
    status='LICENSE_BLOCKED' if license_blocked else 'DOWNLOAD_BLOCKED' if download_blocked else 'REJECTED' if rejected else 'INSUFFICIENT_EVIDENCE' if missing else 'ACCEPTED'
    return {'schema_version':1,'classification':status,'missing':sorted(set(missing)),'prohibited':rejected,
        'source_id':record['source_id'],'record_sha256':digest(record),
        'scope':'DOCUMENT_COMPLETENESS_ONLY_NOT_PROVIDER_AUTHENTICITY_OR_EXPERIMENT_AUTHORIZATION',
        'independent_test_ready':False}
