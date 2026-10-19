import csv,hashlib,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pretest_readiness import make_report, GateError, sha
from archive_fidelity import reference,compute,read_ids,FidelityError

BASE_FIELDS=['block_id','source_family','dataset_version','site_id','start_utc','end_utc','split','raw_sha256']

def csvout(p,rows,fields=BASE_FIELDS):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(rows)

def row(b,split,t0,t1,dig,site='a'):
    return dict(block_id=b,source_family='provider',dataset_version='v2',site_id=site,start_utc=t0,end_utc=t1,split=split,raw_sha256=dig)

def case(tmp_path):
    raw=tmp_path/'raw';raw.mkdir()
    (raw/'new.bin').write_bytes(b'new data')
    digest=sha(raw/'new.bin')
    h=tmp_path/'hist.csv';q=tmp_path/'proposal.csv';meta=tmp_path/'meta.json'
    old='0'*64
    csvout(h,[row('train1','train','2020-01-01T00:00:00Z','2020-01-02T00:00:00Z',old),
              row('val1','validation','2020-01-03T00:00:00Z','2020-01-04T00:00:00Z',old),
              row('test1','internal_test','2020-01-05T00:00:00Z','2020-01-06T00:00:00Z',old),
              row('prior_ext','historical_external','2019-01-01T00:00:00Z','2019-01-02T00:00:00Z','f'*64,site='b')])
    csvout(q,[row('new1','new_test','2021-01-01T00:00:00Z','2021-01-02T00:00:00Z',digest)])
    m={'dataset_name':'open microgrid','dataset_version':'v2','source_family':'provider',
       'source_url':'https://data.example/test','license':'CC-BY-4.0','site_id':'a',
       'timezone':'Etc/UTC','sampling_seconds':120,
       'measurement_units':{'pv':'kW','load':'kW','battery':'kW','soc':'%','grid':'kW'},
       'physical_objectives_supported':dict.fromkeys(('cap_violation_pct_total',
           'lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day'),True),
       'adapter_version':'frozen-v2','previously_inspected_outcomes':False,
       'embargo_hours':48,'raw_files':[{'path':'new.bin','sha256':digest}],
       'prior_external_inventory_complete':True}
    meta.write_text(json.dumps(m))
    return meta,q,h,raw,m,sha(h)

def run(case_):
    meta,q,h,raw,m,sha_hist=case_
    return make_report(meta,q,h,raw,sha_hist,counts=(1,1,1))

def test_clean_metadata_is_review_only(tmp_path):
    r=run(case(tmp_path))
    assert r['status']=='ELIGIBLE_FOR_MANUAL_REVIEW_ONLY'
    assert r['test_performance']=='NOT_COMPUTED'

def test_frozen_history_sha(tmp_path):
    x=case(tmp_path)
    with pytest.raises(GateError,match='registry hash mismatch'):
        make_report(*x[:4],'a'*64,counts=(1,1,1))

def test_overlapping_windows_blocked(tmp_path):
    x=list(case(tmp_path));q=x[1];rows=list(csv.DictReader(q.open()));rows[0]['start_utc']='2020-01-03T10:00:00Z';rows[0]['end_utc']='2020-01-04T10:00:00Z'
    csvout(q,rows)
    with pytest.raises(GateError,match='overlap'):
        run(x)

def test_raw_hash_fail_closed(tmp_path):
    x=list(case(tmp_path)); (x[3]/'new.bin').write_bytes(b'changed')
    with pytest.raises(GateError,match='Raw SHA256 mismatch'):
        run(x)

def test_inspected_outcomes_blocked(tmp_path):
    x=list(case(tmp_path));m=x[4];m['previously_inspected_outcomes']=True;x[0].write_text(json.dumps(m))
    with pytest.raises(GateError,match='already been inspected'):
        run(x)

def test_objective_equivalence_missing(tmp_path):
    x=list(case(tmp_path));m=x[4];m['physical_objectives_supported']['flip_per_day']=False;x[0].write_text(json.dumps(m))
    with pytest.raises(GateError,match='four objectives'):
        run(x)

def test_archive_diagnostic_correct(tmp_path):
    csvout(tmp_path/'ref.csv',[
        dict(candidate_id='a',cap_violation_pct_total=0,lfp_cycle_loss_pct=3,ramp95_kw_per_min=0,flip_per_day=0),
        dict(candidate_id='b',cap_violation_pct_total=1,lfp_cycle_loss_pct=4,ramp95_kw_per_min=1,flip_per_day=1),
        dict(candidate_id='c',cap_violation_pct_total=3,lfp_cycle_loss_pct=0,ramp95_kw_per_min=3,flip_per_day=3)],
        fields=['candidate_id','cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day'])
    f0=tmp_path/'f0.csv';f1=tmp_path/'f1.csv'
    csvout(f0,[{'candidate_id':'a'},{'candidate_id':'b'}],fields=['candidate_id'])
    csvout(f1,[{'candidate_id':'a'},{'candidate_id':'c'}],fields=['candidate_id'])
    r=compute(reference(tmp_path/'ref.csv'),read_ids(f0),read_ids(f1))
    assert r['F0']['false_retained']==1
    assert r['F1']['false_retained']==0
    assert r['F1']['false_eliminated']==0

def test_archive_unknown_rejected(tmp_path):
    ref=({'a':(0,0,0,0)},{'a'})
    with pytest.raises(FidelityError,match='without common reference'):
        compute(ref,{'x'},{'a'})
