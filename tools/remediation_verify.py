"""Non-mutating verification of canonical historical inputs; new receipts only.

Run from the remediation checkout: python tools/remediation_verify.py audit|tests|manifest|preserve
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime,timezone
import difflib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK/'src'))
from crmt_edge_ems.contracts import file_hash,ContractError
from crmt_edge_ems.provenance import source_manifest,validate_manifest

def save(out,name,value):
    out.mkdir(parents=True,exist_ok=True)
    (out/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))

def audit(root,out):
    catalog=root/'07_REPRODUCIBILITY/05_PARENT_SOURCE_SEARCH_20261027/HISTORICAL_160_SOURCE_CATALOG_RECOVERED.csv'
    rows=list(csv.DictReader(catalog.open(encoding='utf-8-sig',newline='')))
    checks=[{**r,'observed_sha256':file_hash(root/r['origin'])} for r in rows]
    for r in checks: r['passed']=r['observed_sha256']==r['sha256']
    save(out,'HISTORICAL_160_RECHECK.json',{'scope':'NEW_BYTE_REHASH_OF_HISTORICAL_INPUTS_NOT_NEW_EXPERIMENT',
        'expected':len(rows),'passed':sum(r['passed'] for r in checks),'records':checks})
    if len(rows)!=160 or not all(r['passed'] for r in checks): raise ContractError('historical source mismatch')
    packages=root/'03_CODE_AND_CONTROLLER/03_PACKAGE_REPLAY_20261027'
    sys.path.insert(0,str(packages/'R20/crmt_r20_equal_cost/tools'))
    from cost_audit import audit_arm
    sys.path.insert(0,str(packages/'R9_LOCAL_PACKAGE/tools/r9_equal_capacity_20261023'))
    from r9_train_pair_preflight import audit_pair,PreflightBlocked
    recovery=root/'02_DATASETS/05_RECOVERED_HISTORICAL_TRAIN_20261027'
    class Source:
        def read(self,member):
            prefix='crmt_r16/raw/'
            if not member.startswith(prefix): raise ContractError('bad source prefix')
            return (recovery/member[len(prefix):]).read_bytes()
    pairs=[]
    for seed in range(1001,1006):
        for c in (0,1):
            for a in (0,1):
                pair=f'seed{seed}_C{c}_A{a}'
                f0,p0,v0=audit_arm(Source(),pair+'/F0');f1,p1,v1=audit_arm(Source(),pair+'/F1')
                if p0!=p1 or v0!=v1: raise ContractError('scientific pairing mismatch')
                try: audit_pair(recovery/pair/'F0',recovery/pair/'F1',seed=seed,c=c,a=a); status='PASS'; reason=None
                except PreflightBlocked as exc: status='BLOCKED_EXTERNAL'; reason=str(exc)
                pairs.append({'pair':pair,'same_events':p0==p1,'same_objectives':v0==v1,
                    'events_F0':f0['n_candidate_blocks'],'events_F1':f1['n_candidate_blocks'],
                    'strict_status':status,'reason':reason,'original_git_sha_F0':f0['execution_sha_recorded'],
                    'original_git_sha_F1':f1['execution_sha_recorded']})
        print(f'historical seed {seed}: four scientific pairs rechecked',flush=True)
    save(out,'HISTORICAL_PAIR_RECHECK.json',{'scientific_pairs':len(pairs),'strict_pass':sum(p['strict_status']=='PASS' for p in pairs),'pairs':pairs})
    frozen=root/'03_CODE_AND_CONTROLLER/01_FROZEN_SOURCE (1)'
    m=json.loads((frozen/'reproducibility/SOURCE_MANIFEST_SHA256.json').read_text())
    comparisons=[]
    for row in m['files']:
        p=frozen/row['path']; data=p.read_bytes() if p.exists() else None
        import hashlib
        h=hashlib.sha256(data).hexdigest() if data is not None else None
        normalized=hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest() if data is not None else None
        classification='EXACT' if h==row['sha256'] else 'NEWLINE_NORMALIZED' if normalized==row['sha256'] else 'MISSING' if data is None else 'CONTENT_DIFFERENCE'
        item={'path':row['path'],'expected':row['sha256'],'actual':h,'lf_normalized':normalized,'classification':classification}
        # Inspect all historical blob versions of this path, without inferring execution identity.
        if classification=='CONTENT_DIFFERENCE':
            commits=subprocess.run(['git','log','--all','--format=%H','--',row['path']],cwd=WORK,capture_output=True,text=True,check=True).stdout.splitlines()
            matched=[];seen=set()
            for commit in commits:
                result=subprocess.run(['git','show',f'{commit}:{row["path"]}'],cwd=WORK,capture_output=True)
                if result.returncode: continue
                blob=result.stdout
                bh=hashlib.sha256(blob).hexdigest()
                if bh in seen: continue
                seen.add(bh)
                if bh==row['sha256'] or hashlib.sha256(blob.replace(b'\r\n',b'\n')).hexdigest()==row['sha256']:
                    matched.append(commit)
                    before=blob.decode('utf-8-sig',errors='replace').splitlines()
                    after=data.decode('utf-8-sig',errors='replace').splitlines()
                    patch='\n'.join(difflib.unified_diff(before,after,fromfile=commit+'/'+row['path'],tofile='FROZEN/'+row['path'],lineterm=''))
                    patchfile=out/'source_diffs'/Path(row['path']+'.diff');patchfile.parent.mkdir(parents=True,exist_ok=True);patchfile.write_text(patch+'\n',encoding='utf-8')
                    item['difference_lines']=len(patch.splitlines()); break
            item['historical_manifest_blob_found_at']=matched
            item['interpretation']='Historical version drift; inspected diff retained; NOT execution proof' if matched else 'Historical baseline blob not located in checked history; cause unresolved'
        comparisons.append(item)
    save(out,'FROZEN_MANIFEST_RECHECK.json',{'counts':dict(Counter(r['classification'] for r in comparisons)),'records':comparisons})
    print('historical audit complete',flush=True)

def package_tests(root,out):
    index=json.loads((root/'07_REPRODUCIBILITY/04_R18_R30_RECONCILIATION_20261027/REPLAY_PACKAGE_INDEX.json').read_text())
    suites=[(f'R{p["stage"]}',root/p['root']) for p in index['packages']]
    suites += [(name,root/'03_CODE_AND_CONTROLLER/03_PACKAGE_REPLAY_20261027'/name) for name in ('R9_LOCAL_PACKAGE','R20_WINDOWS_DERIVATIVE')]
    def run(item):
        name,cwd=item; env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        env['PYTHONPATH']=os.pathsep.join(str(cwd/p) for p in ('reference_snapshot','tools','.'))
        xml=out/f'{name}.xml';cmd=[sys.executable,'-m','pytest','-p','no:cacheprovider','--override-ini','addopts=','-q','tests',f'--junitxml={xml}']
        start=datetime.now(timezone.utc).isoformat()
        try:
            p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
            text=p.stdout+p.stderr;code=p.returncode
        except subprocess.TimeoutExpired as e: text=str(e);code=None
        (out/f'{name}.log').write_text(text,encoding='utf-8')
        counts={'tests':None,'failures':None,'errors':None,'skipped':None}
        if xml.exists():
            tree=ET.parse(xml).getroot();ss=list(tree) if tree.tag=='testsuites' else [tree]
            counts={k:sum(int(s.get(k,'0')) for s in ss) for k in counts}
        result={'suite':name,'started_utc':start,'exit_code':code,'command':cmd,'cwd':str(cwd),**counts}
        print(json.dumps(result),flush=True)
        return result
    out.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(run,suites))
    save(out,'PACKAGE_TEST_RESULTS.json',results)

def manifest(out):
    relatives=[]
    for folder in ('src','tools','tests','config','.github','experiments'):
        relatives.extend(p.relative_to(WORK).as_posix() for p in (WORK/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.yml','.yaml','.toml'})
    relatives.append('pyproject.toml')
    m=source_manifest(WORK,relatives)
    m['git_head']=subprocess.run(['git','rev-parse','HEAD'],cwd=WORK,capture_output=True,text=True,check=True).stdout.strip()
    m['git_status']=subprocess.run(['git','status','--porcelain=v1'],cwd=WORK,capture_output=True,text=True,check=True).stdout
    m['environment']={'python':sys.version,'dependencies':{name:importlib.metadata.version(name) for name in ('numpy','pandas','scipy','matplotlib','pytest','cryptography')}}
    save(WORK/'reproducibility','current_source_manifest.json',m)
    save(WORK/'reproducibility','provenance_validation.json',validate_manifest(WORK,m))
    (WORK/'reproducibility/requirements-remediation-lock.txt').write_bytes(''.join(f'{k}=={v}\n' for k,v in m['environment']['dependencies'].items()).encode('utf-8'))

def preserve(root,out):
    p=root/'07_REPRODUCIBILITY/06_REMEDIATION_20261027/BASELINE_FILE_INVENTORY.csv'
    records=list(csv.DictReader(p.open(encoding='utf-8'))); changed=[];missing=[]
    for r in records:
        target=root/r['path']
        if not target.exists(): missing.append(r['path'])
        elif file_hash(target)!=r['sha256']: changed.append(r['path'])
    save(out,'INPUT_PRESERVATION_CHECK.json',{'scope':'ORIGINAL_READABLE_BASELINE_FILES','checked':len(records),'changed':changed,'missing':missing,'all_preserved':not changed and not missing})
    print(f'preservation: {len(records)} checked, {len(changed)} changed, {len(missing)} missing',flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['audit','tests','manifest','preserve'])
    parser.add_argument('--canonical-root',type=Path,default=WORK.parents[1]);args=parser.parse_args()
    out=WORK/'reports/remediation';out.mkdir(parents=True,exist_ok=True)
    if args.action=='audit': audit(args.canonical_root,out)
    elif args.action=='tests': package_tests(args.canonical_root,out/'package_tests')
    elif args.action=='manifest': manifest(out)
    else: preserve(args.canonical_root,out)

if __name__=='__main__': main()
