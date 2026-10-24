"""Independent arithmetic and provenance audit of recorded R22 output (no rerun)."""
from __future__ import annotations
import csv,hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_r22 import EXPERIMENTS,BASE
from day_certifier import check_originals


def verify(path=ROOT/'results'):
    path=Path(path)
    d=json.loads((path/'R22_EXPERIMENT.json').read_text())
    h=json.loads((path/'R22_REAL_TRAIN_DAY_AUDIT.json').read_text())
    with (path/'R22_PER_REPETITION.csv').open() as f:source=list(csv.DictReader(f))
    reps=d['metadata']['repetitions']
    assert len(d['records'])==len(source)==len(EXPERIMENTS)*reps
    assert len(d['summary'])==len(EXPERIMENTS)
    assert d['metadata']['data']=='SYNTHETIC_ONLY_NOT_NEW_OPENCEM_TEST'
    for i,x in enumerate(d['records']):
        for k,v in x.items():
            assert source[i][k]==('' if v is None else str(v))
    for s in d['summary']:
        part=[x for x in d['records'] if x['scenario']==s['scenario']]
        assert len(part)==reps
        assert s['n_blocked']==sum(x['false_removal'] is None for x in part)
        assert s['n_measured']+s['n_blocked']==reps
        assert s['n_certified_decisions']==sum(x['decision'] for x in part)
        assert s['decision_rate']==sum(x['decision'] for x in part)/reps
        if s['n_measured']:
            for field in ('false_removal','false_pair','band_undercoverage'):
                assert s[field+'_count']==sum(bool(x[field]) for x in part)
    assert [z['seed'] for z in h['rows']]==[1001,1004,1005]
    assert all(z['status'].endswith('NOT_NEW_TEST') for z in h['rows'])
    assert check_originals()
    return {'repetitions':reps,'experiment_records':len(d['records']),
            'source_train_seeds':[x['seed'] for x in h['rows']],
            'passed':True}

if __name__=='__main__':print(json.dumps(verify(),indent=2))
