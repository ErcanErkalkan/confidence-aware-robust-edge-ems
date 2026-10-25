"""Verify immutable manifest and that scientific/source NO-GO status is not overwritten."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify():
    m=json.loads((ROOT/'SHA256_MANIFEST.json').read_text())
    for name,sha in m['files'].items():
        got=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if got!=sha:raise ValueError('SHA256_MISMATCH: '+name)
    s=json.loads((ROOT/'results/R28_PUBLIC_METADATA_EVIDENCE.json').read_text())
    if s['source_admission']!='NO_GO' or s['verified_new_raw_time_series']!=0 or s['independent_new_TEST']!='NO_GO':
        raise ValueError('R28_SOURCE_EVIDENCE_STATUS_TAMPER')
    return {'verified_files':len(m['files']),'source_admission':'NO_GO','unseen_TEST':'NO_GO'}
if __name__=='__main__':print(json.dumps(verify(),indent=2))
