"""Verify frozen experiment arithmetic, original source provenance and SHA manifest."""
from __future__ import annotations
import csv,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def verify(root:Path=ROOT):
    data=json.loads((root/'results/R23_EXPERIMENT.json').read_text())
    stat=list(csv.DictReader((root/'results/R23_SUMMARY.csv').open()))
    records=list(csv.DictReader((root/'results/R23_PER_REPETITION.csv').open()))
    assert len(data['records'])==len(records)==480
    assert len(data['summary'])==len(stat)==16
    for j,r in enumerate(data['records']):
        for key,val in r.items():
            assert records[j][key]==('' if val is None else str(val))
    for r in data['summary']:
        group=[x for x in data['records'] if x['scenario']==r['scenario'] and x['method']==r['method']]
        assert len(group)==30
        ok=[x for x in group if not x['blocked']]
        assert r['n_measured']==len(ok)
        assert r['n_blocked']==30-len(ok)
        assert r['capacity_decisions']==(sum(bool(x['capacity_met']) for x in ok) if ok else None)
    source=json.loads((root/'results/R23_REAL_TRAIN_GATE.json').read_text())
    assert len(source['rows'])==3
    assert all(r['decision'].startswith('BLOCKED_') for r in source['rows'])
    manifest=json.loads((root/'SHA256_MANIFEST.json').read_text())
    for file,sha in manifest['file_sha256'].items():
        assert hashlib.sha256((root/file).read_bytes()).hexdigest()==sha,(file,'sha')
    return {'records':len(records),'summary_rows':len(stat),'real_train_seeds':[x['seed'] for x in source['rows']],
            'file_sha256_passed':len(manifest['file_sha256']),'verified':True}

if __name__=='__main__':print(json.dumps(verify(),indent=2))
