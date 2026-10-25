import hashlib,json,csv,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from r26_source_gate import audit_catalog,check_reference

def verify():
    m=json.loads((ROOT/'SHA256_MANIFEST.json').read_text())
    for file,h in m['file_sha256'].items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==h,file
    catalog=json.loads((ROOT/'config/R26_SOURCE_CANDIDATES.json').read_text())
    result=audit_catalog(catalog)
    recorded=json.loads((ROOT/'results/R26_SOURCE_GATE.json').read_text())
    assert recorded['catalog_sha256']==result['catalog_sha256']
    assert recorded['source_approved_count']==0 and len(catalog)==8
    assert check_reference()['verified_as']=='SEEN_HISTORICAL_TRAIN_ONLY'
    return {'file_sha256_ok':len(m['file_sha256']),'metadata_candidates':len(catalog),'accepted_sources':0,'stage':'NO_GO'}
if __name__=='__main__':print(json.dumps(verify(),indent=2))
