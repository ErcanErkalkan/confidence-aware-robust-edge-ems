#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
    m=json.loads((ROOT/'SHA256_MANIFEST.json').read_text())
    for name,want in m['sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=want:raise ValueError('SHA256_MISMATCH:'+name)
    e=json.loads((ROOT/'results/R29_PUBLIC_PECAN_AGGREGATES.json').read_text())
    if e['n_records']!=2072 or e['candidate_count']!=385 or e['independent_new_TEST']!='NO_GO':raise ValueError('BAD_R29_COUNTS_OR_STATUS')
    return {'verified_file_sha256':len(m['sha256']),'public_metadata_rows':e['n_records'],'metadata_candidates':e['candidate_count'],'new_TEST':'NO_GO'}
if __name__=='__main__':print(json.dumps(verify(),indent=2))
