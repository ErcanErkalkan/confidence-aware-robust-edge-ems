from __future__ import annotations

import csv
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd
import pytest

import opencem_ingest as ingest
import opencem_qa as qa


def _manifest(path: Path, *, commit='c'*40, tree='t'*40, blob='b'*40, size=3, rel='data/measurements/x.csv'):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['commit_sha','tree_sha','path','git_blob_sha1','size_bytes'])
        w.writeheader()
        w.writerow({'commit_sha':commit,'tree_sha':tree,'path':rel,'git_blob_sha1':blob,'size_bytes':size})


def _raw_two_inverters(n=140, step_seconds=300, start='2025-07-14T00:00:00Z'):
    t0 = pd.Timestamp(start).timestamp()
    rows=[]
    for inv in (1,2):
        for k in range(n):
            rows.append({
                'read_ts': t0 + k*step_seconds,
                'inverter': inv,
                'outsumw': 1000 + 10*inv,
                'pv1power': 200 + inv,
                'gridpowerw_a': 0,
                'battsoc': 50 + inv,
            })
    return pd.DataFrame(rows)


def test_git_blob_sha1_matches_git_object_formula(tmp_path: Path):
    p=tmp_path/'x.bin'; data=b'abc\n'; p.write_bytes(data)
    expected=hashlib.sha1(f'blob {len(data)}\0'.encode('ascii')+data).hexdigest()
    assert ingest.git_blob_sha1(p)==expected


def test_load_manifest_rejects_mixed_commits(tmp_path: Path):
    p=tmp_path/'m.csv'
    with p.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['commit_sha','tree_sha','path','git_blob_sha1','size_bytes'])
        w.writeheader()
        w.writerow({'commit_sha':'a','tree_sha':'x','path':'a','git_blob_sha1':'1','size_bytes':1})
        w.writerow({'commit_sha':'b','tree_sha':'x','path':'b','git_blob_sha1':'2','size_bytes':1})
    with pytest.raises(ValueError, match='exactly one commit'):
        ingest.load_manifest(p)


def test_verify_file_records_sha256_and_git_blob(tmp_path: Path):
    p=tmp_path/'x'; p.write_bytes(b'hello')
    row=ingest.ManifestRow('c','t','x',ingest.git_blob_sha1(p),p.stat().st_size)
    r=ingest.verify_file(p,row)
    assert r.verified and r.status=='VERIFIED'
    assert r.sha256==hashlib.sha256(b'hello').hexdigest()


def test_download_http_resumes_range_request(tmp_path: Path):
    payload=(b'0123456789abcdef'*4096)
    seen_ranges=[]
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            rng=self.headers.get('Range'); seen_ranges.append(rng)
            if rng:
                start=int(rng.split('=')[1].split('-')[0])
                body=payload[start:]
                self.send_response(206)
                self.send_header('Content-Length',str(len(body)))
                self.send_header('Content-Range',f'bytes {start}-{len(payload)-1}/{len(payload)}')
            else:
                body=payload
                self.send_response(200)
                self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def log_message(self, *args):
            pass
    srv=HTTPServer(('127.0.0.1',0),H)
    th=threading.Thread(target=srv.serve_forever,daemon=True); th.start()
    try:
        dest=tmp_path/'payload.bin'
        part=dest.with_suffix('.bin.part')
        part.write_bytes(payload[:777])
        ingest._download_http(f'http://127.0.0.1:{srv.server_port}/x',dest,len(payload),timeout=5)
        assert dest.read_bytes()==payload
        assert seen_ranges and seen_ranges[0]=='bytes=777-'
    finally:
        srv.shutdown(); th.join(timeout=2)


def test_download_one_uses_verified_existing_file(tmp_path: Path):
    root=tmp_path/'raw'; p=root/'d/x.csv'; p.parent.mkdir(parents=True); p.write_bytes(b'123')
    row=ingest.ManifestRow('c','t','d/x.csv',ingest.git_blob_sha1(p),3)
    r=ingest.download_one(row,root,url_template='http://127.0.0.1:9/{path}',retries=1,timeout=1)
    assert r.verified and r.status=='VERIFIED_EXISTING'


def test_train_cadence_selection_uses_train_only():
    raw=_raw_two_inverters(n=140,step_seconds=300)
    # Add validation points with 1-minute cadence; these must not change TRAIN-only selection.
    extra=_raw_two_inverters(n=140,step_seconds=60,start='2026-01-02T00:00:00Z')
    raw=pd.concat([raw,extra],ignore_index=True)
    r=qa.select_train_cadence_minutes(raw,expected_inverters=(1,2))
    assert r['selection_source']=='TRAIN_ONLY'
    assert r['selected_minutes']==5


def test_train_cadence_rejects_missing_expected_inverter():
    raw=_raw_two_inverters(n=140)
    raw=raw[raw['inverter']==1]
    with pytest.raises(ValueError, match='Expected train inverter IDs unavailable'):
        qa.select_train_cadence_minutes(raw,expected_inverters=(1,2))


def test_load_verified_csvs_fails_closed_on_unverified(tmp_path: Path):
    v=tmp_path/'v.csv'
    pd.DataFrame([{'path':'x.csv','verified':False}]).to_csv(v,index=False)
    with pytest.raises(RuntimeError, match='verified first'):
        qa.load_verified_csvs(tmp_path,v)


def test_run_qa_reports_per_inverter_availability_and_missingness(tmp_path: Path):
    raw=_raw_two_inverters(n=140,step_seconds=300)
    raw.loc[raw.index[0],'battsoc']=None
    p=tmp_path/'x.csv'; raw.to_csv(p,index=False)
    report=qa.run_qa([p],expected_inverters=(1,2))
    assert report['train_only_cadence_selection']['selected_minutes']==5
    assert set(report['per_inverter_raw'])=={'1','2'}
    assert report['per_inverter_raw']['1']['rows']==140
    assert report['per_inverter_raw']['1']['missing_fraction']['battsoc']>0
    assert report['per_inverter_raw']['1']['raw_gap_seconds']['median']==300.0
    assert report['per_inverter_raw']['1']['raw_gap_seconds']['p95']==300.0
    assert report['neutral_peak_flag_verified'] is True
    assert report['inverter_ids'] == [1, 2]
    assert all(type(x) is int for x in report['inverter_ids'])
    # QA reports are persisted as JSON artifacts; serialization is part of the contract.
    json.dumps(report)


def test_run_qa_rejects_unexpected_inverter_ids(tmp_path: Path):
    raw=_raw_two_inverters(n=140)
    raw.loc[raw['inverter']==2,'inverter']=3
    p=tmp_path/'x.csv'; raw.to_csv(p,index=False)
    with pytest.raises(ValueError, match='Unexpected inverter IDs'):
        qa.run_qa([p],expected_inverters=(1,2))
