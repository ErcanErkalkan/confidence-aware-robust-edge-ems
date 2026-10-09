#!/usr/bin/env python3
"""Join evidence-only cached coverage to frozen TRAIN shortlists, no simulation or TEST."""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path
import pandas as pd

FIELDS=('base_soft_low','base_soft_high','prep_power_cap_frac','lookahead_gain',
        'reserve_enter_margin','reserve_exit_margin','hold_decay',
        'near_cap_forecast_buffer_frac','near_cap_soc_boost')

def digest(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for buf in iter(lambda:f.read(1024*1024),b''):h.update(buf)
 return h.hexdigest()

def build(root:Path,old_cache:Path,out:Path):
 if out.exists():raise FileExistsError(f'No overwrite: {out}')
 source=root/'shortlists'
 coverage=pd.read_csv(old_cache).sort_values(['seed','method','rank']).reset_index(drop=True)
 if len(coverage)!=3000 or coverage[['seed','method','rank']].duplicated().any():raise ValueError('3000 unique required')
 base=[]
 for seed in range(1001,1031):
  for method in ('CRMT','SOBOL','NSGAII','MOPSO','MODE'):
   loc=source/f'seed{seed}'/method
   lock=json.loads((loc/'train_only_shortlist_lock.json').read_text('utf-8'))
   csvp=loc/'train_only_shortlist.csv'
   if lock['shortlist_sha256']!=digest(csvp):raise ValueError('tampered training shortlist')
   frame=pd.read_csv(csvp)
   if len(frame)!=20 or frame['rank'].tolist()!=list(range(1,21)):raise ValueError('corrupt shortlist')
   base.append(frame[['seed','method','rank','candidate_id',*FIELDS]].copy())
 shortlist=pd.concat(base,ignore_index=True)
 pair=coverage.merge(shortlist,left_on=['seed','method','rank','train_candidate_id'],
       right_on=['seed','method','rank','candidate_id'],how='outer',validate='one_to_one',indicator=True)
 if len(pair)!=3000 or (pair['_merge']!='both').any():raise ValueError('identity mismatch shortlist/cache')
 if pair['cache_status'].isna().any():raise ValueError('missing historical state')
 missing=pair.loc[pair.cache_status.ne('CACHED_HISTORICAL_FULL_118'),:].copy()
 if len(missing)!=807:raise ValueError(f'Historical missing workload unexpectedly changed: {len(missing)}')
 missing['required_blocks']=118
 missing['reason']=missing['cache_status']
 out.mkdir(parents=True,exist_ok=False)
 columns=['seed','method','rank','candidate_id','reason','required_blocks','cache_artifact_id',*FIELDS]
 target=out/'HISTORICAL_MISSING_807_REPLAY_WORKLIST.csv'
 missing[columns].to_csv(target,index=False,lineterminator='\n',float_format='%.17g')
 grouped=(coverage.assign(cached=coverage.cache_status.eq('CACHED_HISTORICAL_FULL_118'))
     .groupby(['seed','method'],sort=True).agg(historical_cached=('cached','sum'),
                                              shortlist_size=('cached','size')).reset_index())
 grouped['candidate_replays_to_fill']=grouped['shortlist_size']-grouped['historical_cached']
 grouped['incremental_block_evaluations_to_fill']=grouped['candidate_replays_to_fill']*118
 grouped['uniform_fresh_block_evaluations']=20*118
 grouped['fairness_caveat']='Historical cache only; a uniform fresh replay remains preferred'
 batches=out/'REPLAY_QUOTA_150_METHOD_SEED_JOBS.csv'
 grouped.to_csv(batches,index=False,lineterminator='\n')
 by_method=(missing.groupby('method').size().to_dict())
 report={'status':'PASS','stage':'HISTORICAL_TRAIN_ONLY_K20_AND_VAL_CACHE_COVERAGE_NOT_NEW_EVALUATION',
  'methods':5,'seeds':30,'shortlists':150,'candidates':3000,
  'historical_cached_candidates':int((coverage.cache_status=='CACHED_HISTORICAL_FULL_118').sum()),
  'unresolved_candidates':len(missing),
  'ambiguous_duplicate_old_front_matches':int((coverage.cache_status=='AMBIGUOUS_REPLAY_REQUIRED').sum()),
  'historical_cached_evaluations':int(coverage.candidate_block_rows_available.sum()),
  'historical_incremental_evaluations_to_fill':len(missing)*118,
  'uniform_fresh_replay_evaluations':3000*118,
  'by_method_unresolved_candidates':{k:int(v) for k,v in by_method.items()},
  'no_test_used':True,
  'worklist_sha256':digest(target),'quota_csv_sha256':digest(batches),
  'source_coverage_csv_sha256':digest(old_cache),
  'claim_boundary':'Old VALIDATION cache is exploratory historical reanalysis. Do not claim new experiment or blind test.'}
 (out/'WORKLIST_AUDIT.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage-root',type=Path,required=True)
 p.add_argument('--coverage-csv',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True)
 a=p.parse_args();print(json.dumps(build(a.stage_root,a.coverage_csv,a.output_root),indent=2))
if __name__=='__main__':main()