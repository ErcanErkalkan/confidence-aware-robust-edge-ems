#!/usr/bin/env python3
"""R27 Brazil STAR ZIP metadata/limited row inspector. NEVER certifies independent TEST.

Zip paths and member limits checked; published MD5 is a *weak* integrity cross-check,
not an independent source, license or scientifically valid measurement attestation.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,re,zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

PUBLISHED_MD5='b4f4bad22ba1d896937cfe555f41b25c'
SOURCE='https://zenodo.org/records/3959739'
SYSTEMS={'Battery':10,'PV':5,'IAM':5}
NAME_RE=re.compile(r'(?P<date>20\d{2}[-_]\d{2}[-_]\d{2})[-_](?P<site>STAR[-_][ABCD])[-_](?P<system>Battery|PV|IAM)', re.I)
MAX_ARCHIVE_BYTES=128*1024*1024
MAX_MEMBERS=150000
MAX_CSV_BYTES=1024*1024

class EvidenceBlocked(ValueError):pass

def safe_name(n:str)->bool:
    p=PurePosixPath(n.replace('\\','/'))
    return not(p.is_absolute() or '..' in p.parts or '\x00' in n or re.match(r'^[a-zA-Z]:',n))

def check_zip(z:zipfile.ZipFile)->list[zipfile.ZipInfo]:
    infos=z.infolist()
    if len(infos)>MAX_MEMBERS:raise EvidenceBlocked('MEMBER_COUNT_EXCESSIVE')
    if any(not safe_name(i.filename) for i in infos):raise EvidenceBlocked('PATH_TRAVERSAL_OR_ABSOLUTE')
    if sum(i.file_size for i in infos)>MAX_ARCHIVE_BYTES:raise EvidenceBlocked('UNCOMPRESSED_BYTES_EXCESSIVE')
    if any(i.file_size>MAX_ARCHIVE_BYTES for i in infos):raise EvidenceBlocked('MEMBER_TOO_LARGE')
    return infos

def text_shape(b:bytes,expected:int)->dict:
    """Lightweight parse of first few lines, never infers source cadence from headers."""
    try:s=b.decode('utf-8-sig')
    except UnicodeDecodeError:return {'parse_status':'NON_UTF8_SAMPLE','observed_columns':None}
    try:rows=[r for r in csv.reader(io.StringIO(s)) if r]
    except csv.Error:return {'parse_status':'INVALID_CSV_SAMPLE','observed_columns':None}
    if not rows:return {'parse_status':'EMPTY_SAMPLE','observed_columns':None}
    sizes=Counter(len(r) for r in rows[:10])
    # A site CSV can have a header, comma-separated decimal, or different data schema.
    # Claim neither layout nor valid sensor mapping simply from column count.
    return {'parse_status':'SAMPLE_ONLY_NOT_SCHEMA_CERTIFIED', 'observed_columns':dict(sorted(sizes.items())),
            'documented_expected_columns':expected,'sampled_rows':min(len(rows),10)}

def inspect_file(path:Path,*,published_md5:str=PUBLISHED_MD5)->dict:
    p=Path(path)
    if not p.is_file():raise EvidenceBlocked('RAW_NOT_PRESENT')
    h5=hashlib.md5();h256=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h5.update(chunk);h256.update(chunk)
    if h5.hexdigest()!=published_md5:raise EvidenceBlocked('PUBLISHER_MD5_MISMATCH')
    observed=[];nested=0;unknown=0;by_system=Counter();sites=Counter();sample_errors=0;compressed=0
    with zipfile.ZipFile(p) as outer:
        root=check_zip(outer)
        layers=[outer]
        # One level of nested ZIP only; never extract to filesystem.
        for info in root:
            if info.is_dir():continue
            if info.filename.lower().endswith('.zip'):
                if info.file_size>MAX_ARCHIVE_BYTES:raise EvidenceBlocked('NESTED_ZIP_TOO_LARGE')
                data=outer.read(info)
                try:inner=zipfile.ZipFile(io.BytesIO(data))
                except zipfile.BadZipFile:raise EvidenceBlocked('INVALID_NESTED_ZIP')
                check_zip(inner);layers.append(inner);nested+=1
        for z in layers:
            for item in z.infolist():
                if item.is_dir() or item.filename.lower().endswith('.zip'):continue
                if not item.filename.lower().endswith(('.csv','.txt')):unknown+=1;continue
                match=NAME_RE.search(item.filename)
                if not match:unknown+=1;continue
                sys=next(k for k in SYSTEMS if k.lower()==match.group('system').lower())
                site=match.group('site').upper().replace('_','-')
                by_system[sys]+=1;sites[site]+=1
                if len(observed)<120: # examples only, not exhaustive schema audit
                    with z.open(item) as fh:small=fh.read(MAX_CSV_BYTES)
                    try:shape=text_shape(small,SYSTEMS[sys])
                    except (UnicodeError,ValueError):shape={'parse_status':'SAMPLE_ERROR'};sample_errors+=1
                    observed.append({'name':item.filename,'site':site,'system':sys,'file_size':item.file_size,**shape})
    return {
      'source_record':SOURCE,'raw_file':p.name,'raw_sha256':h256.hexdigest(),
      'raw_publisher_md5_matches':True,'md5_security':'WEAK_PUBLISHER_CHECK_ONLY',
      'nested_zip_members':nested,'files_by_system':dict(sorted(by_system.items())),
      'site_file_counts':dict(sorted(sites.items())),'unclassified_members':unknown,
      'sampled_files':observed,'sample_parse_errors':sample_errors,
      'license_use_permission_verified':False,'independent_source_custody_verified':False,
      'native_2min_cadence_verified':False,'measured_grid_import_export_verified':False,
      'total_building_load_verified':False,'battery_chemistry_LFP_verified':False,
      'original_CRMT_4objectives_comparable':False,
      'is_independent_new_TEST':False,'is_confirmatory_R19_AUDIT':False,
      'status':'RAW_STRUCTURE_REVIEW_ONLY_EXTERNAL_EVIDENCE_AND_PHYSICAL_MAPPING_BLOCKED'
    }

def main():
    q=argparse.ArgumentParser();q.add_argument('zip_path');q.add_argument('--out',required=True)
    a=q.parse_args();r=inspect_file(Path(a.zip_path))
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8') as f:json.dump(r,f,indent=2,ensure_ascii=False);f.write('\n')
    print(r['status'])
if __name__=='__main__':main()
