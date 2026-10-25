"""Non-promotional R27 rights/equivalence gate based on reviewed publisher metadata.
Always fails closed for unseen dataset / physics mapping until independent review.
"""
from __future__ import annotations
import copy,json
from pathlib import Path

PUBLISHER_URLS={
  'BRAZIL_STAR':'https://zenodo.org/records/3959739',
  'PECAN_STREET':'https://www.pecanstreet.org/dataport/licenses/'
}

def rights_matrix()->dict:
 return {
 'BRAZIL_STAR':{
  'published_data_file':'Brazil_STAR_Microgrid_Monitoring.zip',
  'published_md5':'b4f4bad22ba1d896937cfe555f41b25c',
  'license':'RECORD_RIGHTS_NOT_RESOLVED_FOR_THIS_AUDIT',
  'officially_documented_sensors':['Battery: current, Ah, SOC, cycles, voltage, power, charge/discharge energy','PV: voltage, power, energy, operating-state code','IAM: real/reactive power, voltage, meter ID'],
  'grid_kw':'NOT_DOCUMENTED','contracted_grid_cap':'NOT_DOCUMENTED',
  'total_site_load_from_all_IAM':'UNVERIFIED_COVERAGE',
  'sampling_frequency':'NOT_VERIFIED_FROM_RAW',
  'physical_objectives':'NOT_EQUIVALENT_TO_4_ORIGINAL_CRMT_LOSSES',
  'reuse_status':'REQUEST_RECORD_LICENSE_AND_RAW_RIGHTS_BEFORE_AI_INGEST',
  'source_url':PUBLISHER_URLS['BRAZIL_STAR']},
 'PECAN_STREET':{
  'free_university_scope':'75 homes: Austin 25, New York 25, California 25, plus ISO data',
  'free_university_price':'$0','free_university_funded_research':'NOT_PERMITTED',
  'faculty_funded_tier_price_listed':'$10,000 (publisher public pricing page, subject to current agreement)',
  'institutional_tier_price_listed':'$15,000 (publisher public pricing page, subject to current agreement)',
  'university_access_process':'institutional email and affiliation evidence, provider review',
  'ai_processing_sharing':'NOT_PREAPPROVED_BY_PUBLIC_WEBPAGE',
  'battery_soc_per_site':'CHECK_PROVIDER_COHORT','grid_meter_per_site':'CHECK_PROVIDER_COHORT',
  'requested_native_cadence':'<=2min measured native (not interpolation)',
  'physical_objectives':'NOT_VALIDATED','source_url':PUBLISHER_URLS['PECAN_STREET'],
  'rights_decision':'AWAIT_PERSONAL_INSTITUTIONAL_LICENSE_APPROVAL'
 }
 }

def evaluate(rows:dict, external:dict|None=None)->dict:
    # No unsigned/user-controlled approval can mark real data accepted.
    _=external
    return {'stage':'R27_PUBLISHER_METADATA_RIGHTS_AND_SENSOR_AUDIT','sources':copy.deepcopy(rows),
            'raw_brazil_star_downloaded':False,'pecan_account_verified':False,
            'publisher_license_verified_for_ai_use':False,'new_dataset_accepted':False,
            'physical_four_objective_equivalence_verified':False,
            'independent_pre_registration':'NOT_VERIFIED','r19_30_seed_runs':'NOT_RUN',
            'unseen_independent_TEST':'NO_GO',
            'next_actions':['obtain express license and permitted AI-analysis terms for Brazil STAR before raw inspection','confirm Pecan Street research funding category and request academic data access','verify native site sensors, split/exposure history, and >=2-minute frequency on real raw samples','obtain independent human/external protocol preregistration before new optimizer runs']}

if __name__=='__main__':
    print(json.dumps(evaluate(rights_matrix()),indent=2,ensure_ascii=False))
