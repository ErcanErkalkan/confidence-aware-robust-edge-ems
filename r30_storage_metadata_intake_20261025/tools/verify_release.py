#!/usr/bin/env python3
"""R30 package SHA and science/evidence guard checks. Not an external attestation."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
 m=json.loads((ROOT/'SHA256_MANIFEST.json').read_text(encoding='utf8'))
 for name,want in m['file_sha256'].items():
  p=ROOT/name
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=want:raise ValueError('R30_MANIFEST_SHA256_MISMATCH:'+name)
 s=json.loads((ROOT/'results/R30_ANONYMIZED_PUBLIC_METADATA_GROUPS.json').read_text())
 assert s['n_metadata_candidates']==385 and s['storage_flag_union']['n']==7 and s['storage_flag_intersection']==0
 assert s['raw_homes_time_series_read']==0 and s['independent_new_TEST']=='NO_GO'
 p=ROOT/'results/R29_REFERENCE_AGGREGATES_UNMODIFIED.json'
 assert hashlib.sha256(p.read_bytes()).hexdigest()=='57dd870c0ca4b964b347f40779dbd9a9d6a87e762359989c6c663595e0b65ea3'
 return {'sha256_sources_checked':len(m['file_sha256']),'metadata_only':True,'original_provider_csv_authenticated':False,'storage_flag_union':7,'new_independent_TEST':'NO_GO'}
if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
