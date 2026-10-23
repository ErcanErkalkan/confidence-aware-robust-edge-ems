#!/usr/bin/env python3
"""Read-only VAL cache completeness audit; never impute missing candidates.

Cached historical validation is NOT a new replay or an independent TEST.
No quality comparisons are computed. Used only to determine replay needs.
"""
from __future__ import annotations
import argparse,hashlib,io,json,re,zipfile
from pathlib import Path
import numpy as np,pandas as pd
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from crmt_p0.equal_quota import METHODS,PARAMS,OBJECTIVES,GateClosed,sha256
from crmt_p0.gate2_validation import K,N_VAL_BLOCKS,load_gate1_shortlist,_risk_score

VAL_ZIPS=(10584636373,10585128699,10584888899,10584104886,10584618918,
 10585213636,10584404201,10584544070,10585125244,10584153277)


def audit(artifact_root:Path,shortlist_root:Path,output_dir:Path)->dict:
    if output_dir.exists():raise GateClosed('output exists; no overwrite')
    cached={}
    for zid in VAL_ZIPS:
        with zipfile.ZipFile(artifact_root/f'github-actions-artifact-{zid}.zip') as z:
            for name in z.namelist():
                match=re.fullmatch(r'validation_selection_seed(10\d\d)/selection_lock\.json',name)
                if match is None:continue
                seed=int(match.group(1));prefix=name.rsplit('/',1)[0]
                if seed not in range(1001,1031):continue
                if seed in cached:raise GateClosed('duplicate validation archive per seed')
                lock=json.loads(z.read(name))
                if lock.get('stage')!='VALIDATION_SELECTION_LOCK' or int(lock['seed'])!=seed:
                    raise GateClosed('legacy VAL lock wrong stage/seed')
                if lock.get('data_context',{}).get('split')!='validation' or int(lock['data_context']['split_block_count'])!=118:
                    raise GateClosed('legacy VAL context wrong split/cardinality')
                data={}
                for key in ('validation_candidate_scores.csv','validation_block_metrics.csv'):
                    blob=z.read(prefix+'/'+key)
                    if hashlib.sha256(blob).hexdigest()!=lock['files_sha256'][key]:
                        raise GateClosed('legacy VAL file hash mismatch')
                    data[key]=pd.read_csv(io.BytesIO(blob))
                cached[seed]=(lock,data['validation_candidate_scores.csv'],data['validation_block_metrics.csv'],zid)
    if set(cached)!=set(range(1001,1031)):raise GateClosed('not all thirty seed cached')
    records=[]
    for seed in range(1001,1031):
        lock,scores,blocks,zid=cached[seed]
        manifest=lock['data_context']['manifest_sha256']
        for method in METHODS:
            shortlist,sl=load_gate1_shortlist(shortlist_root/f'seed{seed}'/method,method=method,seed=seed,
                                      expected_manifest_sha256=manifest)
            old=scores[scores['method']==method].copy()
            if old.empty:raise GateClosed('VAL cache lacks method')
            old_params=old[list(PARAMS)].to_numpy(dtype=float)
            sub=blocks[blocks['method']==method]
            match_count=0
            for row in shortlist.itertuples(index=False):
                p=np.array([float(getattr(row,param)) for param in PARAMS])
                mask=np.max(np.abs(old_params-p),axis=1)<1e-9
                matches=old[mask]
                # Conservative: multiple physically identical historical front entries
                # cannot be silently mapped to one shortlisted candidate.
                status='AMBIGUOUS_REPLAY_REQUIRED' if len(matches)>1 else 'MISSING_REPLAY_REQUIRED'
                if len(matches)==1:
                    old_id=str(matches.iloc[0].candidate_id)
                    measurements=sub[sub['candidate_id'].astype(str)==old_id]
                    if len(measurements)!=N_VAL_BLOCKS or measurements.block_id.nunique()!=N_VAL_BLOCKS:
                        raise GateClosed('matched cached candidate not full 118 blocks')
                    if set(measurements['split'].astype(str))!={'validation'}:
                        raise GateClosed('cache contamination with non-VAL')
                    if measurements['site_id'].isna().any():raise GateClosed('missing old site provenance')
                    for objective in OBJECTIVES:
                        agg=_risk_score(measurements[objective].to_numpy(dtype=float))
                        orig=float(matches.iloc[0][objective])
                        if not np.isclose(agg,orig,atol=2e-8,rtol=0):
                            raise GateClosed('VAL aggregation mismatch '+objective)
                    status='CACHED_HISTORICAL_FULL_118'
                    match_count+=1
                records.append({'seed':seed,'method':method,'rank':int(row.rank),
                   'train_candidate_id':str(row.candidate_id),
                   'cache_status':status,
                   'candidate_block_rows_available':N_VAL_BLOCKS if status.startswith('CACHED') else 0,
                   'cache_artifact_id':zid})
            if match_count>K:raise GateClosed('cached coverage impossible')
    df=pd.DataFrame(records).sort_values(['seed','method','rank']).reset_index(drop=True)
    by_method=(df.assign(is_cached=df.cache_status.eq('CACHED_HISTORICAL_FULL_118'))
      .groupby('method',sort=True)['is_cached'].agg(['sum','count']).reset_index())
    report={'stage':'HISTORICAL VAL CACHE COVERAGE / NOT NEW E2 EXPERIMENT',
      'seeds':30,'methods':5,'shortlisted_candidates':len(df),
      'historical_val_full_candidates':int(df.cache_status.eq('CACHED_HISTORICAL_FULL_118').sum()),
      'missing_candidate_replays':int(df.cache_status.ne('CACHED_HISTORICAL_FULL_118').sum()),
      'ambiguous_duplicate_historical_matches':int(df.cache_status.eq('AMBIGUOUS_REPLAY_REQUIRED').sum()),
      'available_historical_controller_block_rows':int(df.candidate_block_rows_available.sum()),
      'required_new_simulator_block_rows':int(df.cache_status.ne('CACHED_HISTORICAL_FULL_118').sum())*N_VAL_BLOCKS,
      'by_method':[{ 'method':str(r.method), 'cache_hits':int(r.sum), 'quota':int(r.count)}
                   for r in by_method.itertuples(index=False)],
      'claim_boundary':'Cache is not a new experiment; missing candidates cannot be evaluated without canonical OpenCEM replay profiles.'}
    output_dir.mkdir(parents=True)
    path=output_dir/'historical_validation_cache_coverage_30seeds.csv'
    df.to_csv(path,index=False,lineterminator='\n')
    report['coverage_csv_sha256']=sha256(path)
    (output_dir/'historical_validation_cache_coverage_30seeds_summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--artifact-dir',type=Path,required=True)
    a.add_argument('--shortlist-root',type=Path,required=True)
    a.add_argument('--output-dir',type=Path,required=True)
    args=a.parse_args()
    print(json.dumps(audit(args.artifact_dir,args.shortlist_root,args.output_dir),indent=2))

if __name__=='__main__':main()
