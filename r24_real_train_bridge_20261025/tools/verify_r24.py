"""Independent byte-level and arithmetic audit of R24 packed data (no new TEST)."""
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from r24_audit import run,OBJ

def verify():
    old=json.loads((ROOT/'results/R24_REAL_TRAIN_BRIDGE.json').read_text(encoding='utf8'))
    new=run()
    assert new==old,'original TRAIN audit does not reproduce'
    with (ROOT/'results/R24_B10_AND_DAY_COVERAGE.csv').open(newline='',encoding='utf8') as f:
        a=list(csv.DictReader(f))
    assert len(a)==3
    for row in a:
        r=next(x for x in old['rows'] if x['seed']==int(row['seed']))
        for k in ('B10_shared','global_complete_two_inverter_days_256','global_common_blocks_256','natural_archive_F0','natural_archive_F1'):
            assert int(row[k])==r[k],(k,r['seed'])
    dry=json.loads((ROOT/'results/R24_PREFLIGHT_DRY_RUN.json').read_text())
    assert dry['audit_events_n']==15360 and not dry['r23_certificate_eligible']
    manifest=json.loads((ROOT/'SHA256_MANIFEST.json').read_text())
    for path,expected in manifest['source_files_sha256'].items():
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        assert actual==expected,path
    return {'SHA256_verified':len(manifest['source_files_sha256']),
            'real_seeds':[1001,1004,1005],
            'B10_common':[r['B10_shared'] for r in old['rows']],
            'global_complete_days':[r['global_complete_two_inverter_days_256'] for r in old['rows']],
            'new_TEST':'NO_GO','status':'VERIFIED_HISTORICAL_TRAIN_ONLY'}

if __name__=='__main__':print(json.dumps(verify(),indent=2,ensure_ascii=False))
