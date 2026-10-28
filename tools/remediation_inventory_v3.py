"""Read-only local inventory and exact historical-preimage search; outputs only to --out.

Drive IDs are joined only when supplied by an observed connector metadata export.
No name/size match is called a verified duplicate or an execution identity.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, re, subprocess, time, zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)

def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args])

def byte_variants(raw):
    yield 'RAW_BYTES',raw
    yield 'CRLF_TO_LF',raw.replace(b'\r\n',b'\n')
    yield 'LF_TO_CRLF',raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    if raw.startswith(b'\xef\xbb\xbf'):yield 'REMOVE_UTF8_BOM',raw[3:]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['inventory','recovery'],required=True)
    a=p.parse_args();root=a.root.resolve();repo=a.repo.resolve();out=a.out.resolve();start=time.perf_counter()
    if not out.is_relative_to(root):raise ValueError('Output must remain in named project root')
    if a.mode=='recovery':
        old=root/'10_FINAL_REMEDIATION_AND_VALIDATION/01_SOURCE_AUDIT/fresh_20261028/FROZEN_MANIFEST_RECHECK.json'
        prior=json.loads(old.read_text(encoding='utf-8-sig'))
        targets=[r for r in prior['records'] if r['classification']=='CONTENT_DIFFERENCE' and not r.get('historical_manifest_blob_found_at')]
        expected={r['path']:r['expected'] for r in targets};byname={Path(k).name:k for k in expected};matches=[];counts=Counter();issues=[]
        def inspect(raw,origin,name):
            target=byname.get(name)
            if target is None:return
            for label,data in byte_variants(raw):
                if hashlib.sha256(data).hexdigest()==expected[target]:matches.append({'target':target,'origin':origin,'byte_variant':label,'sha256':expected[target]})
        for directory,dirs,files in os.walk(root):
            dirs[:]=[d for d in dirs if d not in {'.git','node_modules','__pycache__','.pytest_cache'} and (Path(directory)/d).resolve()!=out]
            for name in files:
                f=Path(directory)/name
                try:
                    if name in byname:counts['local_candidate_files']+=1;inspect(f.read_bytes(),f.relative_to(root).as_posix(),name)
                    if f.suffix.lower()=='.zip':
                        counts['zip_archives_inspected']+=1
                        with zipfile.ZipFile(f) as z:
                            for m in z.infolist():
                                if Path(m.filename).name in byname and m.file_size<2_000_000:
                                    counts['zip_source_members']+=1;inspect(z.read(m),f.relative_to(root).as_posix()+'!'+m.filename,Path(m.filename).name)
                except (OSError,ValueError,zipfile.BadZipFile) as e:issues.append({'path':f.relative_to(root).as_posix(),'error':str(e)})
        objects=git(repo,'rev-list','--objects','--all','--',*expected).decode().splitlines();seen=set()
        for line in objects:
            oid,sep,path=line.partition(' ')
            if not sep or Path(path).name not in byname or oid in seen:continue
            seen.add(oid)
            if git(repo,'cat-file','-t',oid).strip()!=b'blob':continue
            counts['reachable_git_source_blobs']+=1;inspect(git(repo,'cat-file','blob',oid),'git:'+oid+':'+path,Path(path).name)
        rows=[{'source_path':k,'expected_sha256':v,'status':'EXACT_PREIMAGE_FOUND' if any(m['target']==k for m in matches) else 'UNRESOLVED','matched_origins':';'.join(m['origin']+'@'+m['byte_variant'] for m in matches if m['target']==k),'scope':'BYTE_IDENTITY_ONLY; execution identity separately unresolved'} for k,v in expected.items()]
        write_csv(out/'07_SOURCE_PROVENANCE/HISTORICAL_SOURCE_RECOVERY_MATRIX.csv',rows,list(rows[0]))
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_main':git(repo,'rev-parse','HEAD').decode().strip(),'all_remote_refs':git(repo,'show-ref').decode().splitlines(),'counts':dict(counts),'matches':matches,'issues':issues,'original_execution_record':'seed1001/C1_F1_A1: UNRECORDED_LOCAL_SHA','replacement_with_current_HEAD':False,'historical_execution_sha_recovered':False,'scope':'Reachable fetched Git history plus all accessible local source basenames and ZIP members. Drive-only inaccessible originals are outside scope. Exact byte match does not establish execution.','elapsed_seconds':time.perf_counter()-start}
        write_json(out/'07_SOURCE_PROVENANCE/HISTORICAL_EXECUTION_IDENTITY_AUDIT.json',report)
        text='# Çözülemeyen özgün kaynak ön imajları\n\n'+f"Erişilebilir {counts['local_candidate_files']} kaynak kopyası, {counts['zip_archives_inspected']} ZIP, {counts['zip_source_members']} kaynak üyesi ve {counts['reachable_git_source_blobs']} Git blobu incelendi.\n\n"+'\n'.join('- '+r['source_path']+': '+r['status'] for r in rows)+'\n\nseed1001/C1_F1_A1 özgün yürütme kimliği UNRECORDED_LOCAL_SHA olarak korunur. Güncel HEAD bunun yerine geçirilmedi. Gereken kanıt: özgün hash eşleşen baytlar; yürütme için koşu zamanı imzalı/sağlayıcı kaynaklı değişmez kaynak SHA kaydı. Ad/yorum/tarih benzerliği yeterli değildir.\n'
        (out/'07_SOURCE_PROVENANCE/UNRESOLVED_SOURCE_PREIMAGES_TR.md').write_text(text,encoding='utf-8')
        print(json.dumps({'mode':a.mode,'counts':dict(counts),'matches':len(matches),'elapsed':report['elapsed_seconds']}));return
    rows=[];issues=[];excluded=[]
    public={}
    for line in git(repo,'ls-tree','-r','HEAD').decode().splitlines():
        left,path=line.split('\t',1);public[path]=left.split()[2]
    for directory,dirs,files in os.walk(root):
        for d in list(dirs):
            if d in {'.git','node_modules'}:
                excluded.append((Path(directory)/d).relative_to(root).as_posix());dirs.remove(d)
        for name in files:
            f=Path(directory)/name;rel=f.relative_to(root).as_posix()
            if f.is_relative_to(out):continue # evolving outputs have separate final delivery manifest
            role='HISTORICAL_PRESERVED'
            if any(x in f.parts for x in ('__pycache__','.pytest_cache')) or f.suffix in {'.pyc','.aux','.log','.toc','.blg'}:role='TEMPORARY_PRESERVED'
            if f.is_relative_to(repo):role='CURRENT_ENGINEERING_CHECKOUT'
            try:
                stat=f.stat();sha=digest(f);date=datetime.fromtimestamp(stat.st_mtime,timezone.utc).isoformat()
                gh='';match=''
                candidate=f.relative_to(repo).as_posix() if f.is_relative_to(repo) else ''
                if candidate in public:
                    # Git SHA1 is distinct from SHA256; compare canonical blob bytes only for exact public counterpart.
                    raw=f.read_bytes();gitsha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                    if gitsha==public[candidate]:gh='https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/blob/'+git(repo,'rev-parse','HEAD').decode().strip()+'/'+candidate;match='GIT_BLOB_BYTES_MATCH'
                category='ENGINEERING_SOURCE' if f.suffix in {'.py','.ps1','.yml','.toml'} else 'RESEARCH_METADATA_OR_REPORT'
                if rel.startswith('02_DATASETS/') or any(x in rel.lower() for x in ('trajectory','raw_values','raw_to_replay_full')):category='PRIVATE_DATA_OR_DERIVED_TRACE'
                if 'MANUSCRIPT' in rel.upper():category='MANUSCRIPT_WORKING_OR_HISTORICAL'
                ver=';'.join(re.findall(r'(?i)(?:^|[/_])(v\d+|20\d{6})(?=[/_.-]|$)',rel))
                rows.append({'local_path':rel,'drive_path':'CRMT_RESEARCH_PROJECT/'+rel,'drive_file_id':'','drive_id_status':'NOT_RESOLVED_FROM_LOCAL_FILESYSTEM','version_token':ver,'modified_utc':date,'size_bytes':stat.st_size,'sha256':sha,'role':role,'github_counterpart':gh,'counterpart_verification':match,'scientific_evidence_category':category,'duplicate_status':'NOT_CLASSIFIED_BY_NAME_OR_SIZE'})
            except OSError as e:issues.append({'path':rel,'error':str(e)})
        if len(rows)%1000==0:print(json.dumps({'progress_files':len(rows)}),flush=True)
    write_csv(out/'00_STATUS/PROJECT_FILE_INVENTORY_SHA256.csv',rows,list(rows[0]))
    summary={'checked_at':datetime.now(timezone.utc).isoformat(),'files_hashed':len(rows),'bytes_hashed':sum(r['size_bytes'] for r in rows),'scope':'All readable local files; Git database/node_modules excluded; evolving new output16 uses delivery manifest. Cloud IDs joined separately from observed metadata.','excluded_metadata_directories':excluded,'issues':issues,'roles':dict(Counter(r['role'] for r in rows)),'top_level_counts':dict(Counter(r['local_path'].split('/')[0] for r in rows)),'elapsed_seconds':time.perf_counter()-start,'files_deleted_or_moved':0}
    write_json(out/'00_STATUS/INVENTORY_SCOPE.json',summary);print(json.dumps(summary))

if __name__=='__main__':main()
