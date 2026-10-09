#!/usr/bin/env python3
"""Fail-closed, read-only CRMT Gate2 pilot readiness inspection.

No downloads, model evaluation, train/test execution, overwrites of baseline or
Github changes. Writes only an explicit new report path.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, subprocess, sys
from pathlib import Path

COMMIT='5884d253a5267fb240b7a8df6fa9e4d49a905167'
REPO_COMMIT='be5756321617087ca421a639d60a99513f29d889'
MODE_ORCHESTRATION_COMMIT='897a9875dbbe7bd46520c9f91c4c7ee633d189fe'
BLOCK_MANIFEST='3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1'
METHODS=('CRMT','SOBOL','NSGAII','MOPSO','MODE')
SEEDS=tuple(range(1001,1031))
GIT_SHAS={
 'tools/opencem_confirmatory_train.py':'2075e5e0376f9a785332b7d2541632c5e2733317',
 'tools/opencem_qa.py':'0f00cdb5770ddd248763f5d038b1edb782630482',
 'src/crmt_edge_ems/study.py':'789e4bd7c8d2f5b4617c7f6934129e4c192b14a3',
 'src/crmt_edge_ems/replay.py':'a2e0ca052beb1f4767038e1cb390e0f721747e84',
 'src/crmt_edge_ems/risk.py':'edee0d3361691535330419d0203757d0b3624638',
 'src/crmt_edge_ems/selection.py':'121e4bbf27c6690919e3c49e47da7d40f14dc0c3',
 'src/crmt_edge_ems/indicators.py':'c0aa880dba9f632f48115129aee8727da6f9201a',
 'src/crmt_edge_ems/site_model.py':'a68de7e7ba0309a10578f982b375bfd35631cf0e',
 'src/crmt_edge_ems/parameter_space.py':'e92678ec1adbc3f4c7cea30c6be09fec883bc65a',
 'src/data_adapters/opencem.py':'21d21efcf60e8d11928321d559aa5cc6784cec71',
}

def sha256(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  while block:=f.read(1024*1024):h.update(block)
 return h.hexdigest()

def git_blob(p:Path)->str:
 length=p.stat().st_size
 h=hashlib.sha1(f'blob {length}\0'.encode('ascii'))
 with p.open('rb') as f:
  while block:=f.read(1024*1024):h.update(block)
 return h.hexdigest()

def json_file(p:Path)->dict:
 obj=json.loads(p.read_text('utf-8-sig'))
 if not isinstance(obj,dict):raise ValueError('Expected a JSON object')
 return obj

def audit_source_lock(path:Path)->dict:
 lock=json_file(path)
 if (lock.get('repository'),lock.get('commit_sha'),lock.get('tree_sha'))!=('OpenCEM-platform/opencem-dataset',COMMIT,'5471f4cf87c3d4bcf0fe590c6cad69433cb5535b'):
  raise ValueError('Wrong upstream repository/commit/tree')
 parts=lock.get('partitions',[])
 if len(parts)!=19 or lock.get('partition_count')!=19:raise ValueError('Expected exactly 19 immutable parts')
 names=[row['path'] for row in parts]
 if len(set(names))!=19 or any(not re.fullmatch(r'data/measurements/20\d\d-(?:0[1-9]|1[0-2])-[ab]\.csv',n) for n in names):raise ValueError('Unsafe/duplicate partition')
 if sum(int(r['size_bytes']) for r in parts)!=883382698 or lock.get('total_measurement_bytes')!=883382698:raise ValueError('Source total bytes conflict')
 if any(not re.fullmatch(r'[0-9a-f]{40}',r['git_blob_sha1']) for r in parts):raise ValueError('Bad blob SHA')
 return {'lock_sha256':sha256(path),'parts':parts,'source_total_bytes':883382698}

def audit_shortlists(root:Path)->dict:
 checked=0; errors=[]
 for seed in SEEDS:
  for method in METHODS:
   folder=root/f'seed{seed}'/method
   csvpath=folder/'train_only_shortlist.csv'
   lockpath=folder/'train_only_shortlist_lock.json'
   if not csvpath.is_file() or not lockpath.is_file():
    errors.append(f'Absent {seed}/{method}');continue
   try:
    lock=json_file(lockpath)
    if (lock.get('seed'),lock.get('method'),lock.get('k'))!=(seed,method,20):raise ValueError('Identity/K mismatch')
    if lock.get('input_train_manifest_sha256')!=BLOCK_MANIFEST:raise ValueError('Source block manifest mismatch')
    expected_source=(MODE_ORCHESTRATION_COMMIT if method=='MODE' else REPO_COMMIT)
    if lock.get('source_train_git_sha')!=expected_source:raise ValueError('Source TRAIN commit mismatch; MODE recovery commit is an explicitly audited exception')
    if lock.get('source_training_budget')!=12600 or lock.get('planned_validation_controller_block_evaluations')!=2360:raise ValueError('Budget mismatch')
    if lock.get('shortlist_sha256')!=sha256(csvpath):raise ValueError('CSV content hash mismatch')
    with csvpath.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=20 or [int(r['rank']) for r in rows]!=list(range(1,21)):raise ValueError('Rank/cardinality mismatch')
    if set(r['method'] for r in rows)!={method} or set(int(r['seed']) for r in rows)!={seed}:raise ValueError('CSV source identity mismatch')
    if len(set(r['candidate_id'] for r in rows))!=20:raise ValueError('Repeated candidate ID')
    checked+=1
   except Exception as e:errors.append(f'{seed}/{method}: {type(e).__name__}: {e}')
 return {'expected_shortlists':150,'verified_shortlists':checked,'errors':errors,'passed':checked==150 and not errors}

def audit_repository(path:Path)->dict:
 if not path.is_dir():return {'passed':False,'reason':'Local canonical repository directory absent'}
 try:
  cp=subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True,text=True,timeout=15)
  sha=cp.stdout.strip()
  if cp.returncode!=0 or sha!=REPO_COMMIT:return {'passed':False,'actual_sha':sha,'expected_sha':REPO_COMMIT,'reason':'Must use isolated checkout of frozen code commit'}
  dirty=subprocess.run(['git','-C',str(path),'status','--porcelain','--untracked-files=no'],capture_output=True,text=True,timeout=15)
  if dirty.returncode or dirty.stdout.strip():return {'passed':False,'reason':'Tracked source files are modified; require clean checkout'}
  mismatched=[p for p,v in GIT_SHAS.items() if not (path/p).is_file() or git_blob(path/p)!=v]
  return {'passed':not mismatched,'actual_sha':sha,'files_checked':len(GIT_SHAS),'mismatched_files':mismatched}
 except (OSError,subprocess.TimeoutExpired) as exc:return {'passed':False,'reason':str(exc)}

def audit_blocks(path:Path)->dict:
 if not path.is_file():return {'passed':False,'reason':'Canonical derived block_lock.json missing (split lock is not a substitute)'}
 try:
  lock=json_file(path)
  if lock.get('canonical_csv_sha256')!=BLOCK_MANIFEST:raise ValueError('Canonical block CSV hash mismatch')
  if int(lock.get('split_counts',{}).get('validation',-1))!=118:raise ValueError('Expected 118 validation blocks')
  if int(lock.get('split_counts',{}).get('train',-1))!=210:raise ValueError('Unexpected train count')
  return {'passed':True,'sha256':sha256(path)}
 except Exception as e:return {'passed':False,'reason':str(e)}

def audit_data(raw_root:Path,lock:dict,verification_csv:Path)->dict:
 parts=lock['parts']; statuses=[]; verified={}; observed_bytes=0
 for row in parts:
  dest=raw_root/row['path']; ident=row['path']
  if not dest.is_file():statuses.append({'path':ident,'state':'MISSING'});continue
  if dest.stat().st_size!=int(row['size_bytes']):statuses.append({'path':ident,'state':'SIZE_MISMATCH'});continue
  actual=git_blob(dest)
  if actual!=row['git_blob_sha1']:statuses.append({'path':ident,'state':'GIT_BLOB_MISMATCH'});continue
  val=sha256(dest);verified[ident]=val;observed_bytes+=dest.stat().st_size
  statuses.append({'path':ident,'state':'VERIFIED','sha256':val})
 check_csv=False;csv_error='CSV manifest missing'
 if verification_csv.is_file():
  try:
   with verification_csv.open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
   if len(csvrows)!=19 or set(r['path'] for r in csvrows)!=set(r['path'] for r in parts):raise ValueError('Verification CSV path coverage not exactly 19')
   for r in csvrows:
    if str(r['verified']).strip().lower() not in {'true','1'} or r['sha256']!=verified.get(r['path']):raise ValueError('Verification CSV SHA or verified flag conflicts with current raw bytes')
   check_csv=True;csv_error=''
  except Exception as e:csv_error=str(e)
 passed=len(verified)==19 and check_csv and observed_bytes==883382698
 return {'passed':passed,'verified_files':len(verified),'missing_or_corrupt':[x for x in statuses if x['state']!='VERIFIED'],'verified_bytes':observed_bytes,'verification_csv_passed':check_csv,'verification_csv_error':csv_error}

def run(args:argparse.Namespace)->dict:
 lock=audit_source_lock(args.recovery_root/'locks'/'opencem_git_tree_lock_v1.json')
 candidates=audit_shortlists(args.gate2_root/'outputs'/'locked_30seed'/'shortlists')
 repo=audit_repository(args.repo_root)
 blocks=audit_blocks(args.block_lock_json)
 dataset=audit_data(args.raw_root,lock,args.verification_csv)
 checks={'source_lock':{'passed':True,'sha256':lock['lock_sha256']},'shortlists':candidates,'frozen_repository':repo,'canonical_block_lock':blocks,'local_raw_data':dataset}
 return {'status':'READY_TO_RUN_GATE2_30SEED' if all(x['passed'] for x in checks.values()) else 'BLOCKED_DO_NOT_RUN','stage':'PREFLIGHT_30SEED_ONLY_NO_REPLAY','protocol':'CRMT-EAAI-E2-30SEED-FULL-IMMUTABLE-2026-10-09','source_commit':COMMIT,'code_commit':REPO_COMMIT,'mode_source_orchestration_commit':MODE_ORCHESTRATION_COMMIT,'required_manifest_sha256':BLOCK_MANIFEST,'checks':checks,'claim_boundary':'No new TRAIN, VALIDATION, TEST, or EAAI performance result was produced.'}

def main()->int:
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('recovery-root','gate2-root','repo-root','raw-root','verification-csv','block-lock-json','report-json'):
  p.add_argument('--'+name,required=True,type=Path)
 a=p.parse_args()
 if a.report_json.exists():p.error('Refusing to overwrite existing preflight report: '+str(a.report_json))
 report=run(a)
 a.report_json.parent.mkdir(parents=True,exist_ok=True)
 a.report_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':report['status'],'shortlists':report['checks']['shortlists']['verified_shortlists'],'verified_data_files':report['checks']['local_raw_data']['verified_files'],'repo':report['checks']['frozen_repository'].get('actual_sha'),'report':str(a.report_json)},indent=2))
 return 0 if report['status']=='READY_TO_RUN_GATE2_30SEED' else 2

if __name__=='__main__':raise SystemExit(main())