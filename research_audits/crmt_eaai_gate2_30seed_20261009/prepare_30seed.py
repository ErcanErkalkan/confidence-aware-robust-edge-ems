#!/usr/bin/env python3
"""Reproducible TRAIN-only 30x5 K20 Gate2 shortlist expansion from frozen Actions artifacts.

Not a new optimization/replay. This script never reads validation/test or replaces frozen evidence.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'gate1'/'src'))
from crmt_p0.equal_quota import GateClosed, sha256, shortlist_train_only, training_pool_from_files, write_train_lock

ARTIFACTS={
 'CRMT':[10569941406,10567761550,10565755696,10569573596,10569347386],
 'SOBOL':[10567850738],
 'NSGAII':[10566175447],
 'MOPSO':[10571005708],
 'MODE':[10581233117,10581959635,10581643132,10582164465,10581904621],
}
SEEDS=set(range(1001,1031))
MANIFEST='3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1'
TRAIN_COMMIT='be5756321617087ca421a639d60a99513f29d889'
MODE_COMMIT='897a9875dbbe7bd46520c9f91c4c7ee633d189fe'
FIELDS=['seed','method','source_artifact_id','source_train_git_sha','source_run_summary_sha256','source_manifest_sha256','source_train_budget','selected_candidates','train_shortlist_csv_sha256','train_shortlist_lock_sha256','planned_val_blocks']


def extract_train_group(z:zipfile.ZipFile,prefix:str,dest:Path,method:str)->None:
    for name in ('run_summary.json','ledger.csv','optimizer_front.csv','candidate_metrics.csv' if method=='CRMT' else 'candidate_evaluations.csv'):
        if '/' in name or '\\' in name:raise GateClosed('invalid file name')
        (dest/name).write_bytes(z.read(prefix+'/'+name))


def execute(artifact_dir:Path,out_root:Path)->dict:
    if out_root.exists():raise GateClosed('Destination exists: refusing to overwrite')
    if not artifact_dir.is_dir():raise GateClosed('Archive directory does not exist')
    out_root.mkdir(parents=True,exist_ok=False)
    seen=set(); rows=[]; source_ids=[]
    manifest_sets={}
    try:
      for method,ids in ARTIFACTS.items():
        for id_ in ids:
            src=artifact_dir/f'github-actions-artifact-{id_}.zip'
            if not src.is_file():raise GateClosed(f'Artifact missing: {src.name}')
            with zipfile.ZipFile(src) as z:
                if z.testzip() is not None:raise GateClosed(f'Corrupt ZIP: {src.name}')
                prefixes=sorted({p.rsplit('/',1)[0] for p in z.namelist() if re.search(rf'/{method}_seed\d+/run_summary\.json$',p)})
                if not prefixes:raise GateClosed(f'No expected TRAIN files: {src.name}')
                for prefix in prefixes:
                    seed=int(prefix.rsplit('seed',1)[1]);key=(method,seed)
                    if seed not in SEEDS or key in seen:raise GateClosed(f'Duplicate or invalid key: {key}')
                    seen.add(key)
                    with tempfile.TemporaryDirectory(prefix='crmt_train_only_') as tmp:
                        td=Path(tmp);extract_train_group(z,prefix,td,method)
                        pool,summary=training_pool_from_files(td)
                        if summary['method']!=method or int(summary['seed'])!=seed:
                            raise GateClosed(f'Archive identity mismatch {key}')
                        if summary['data_context']['manifest_sha256']!=MANIFEST:
                            raise GateClosed(f'Split manifest not canonical: {key}')
                        expected_commit=MODE_COMMIT if method=='MODE' else TRAIN_COMMIT
                        if summary.get('git_sha')!=expected_commit:
                            raise GateClosed(f'TRAIN source commit mismatch {key}')
                        short,audit=shortlist_train_only(pool,method=method,seed=seed,k=20)
                        subdir=out_root/'shortlists'/f'seed{seed}'/method
                        lock=write_train_lock(short,audit,subdir,summary)
                        if lock['planned_validation_controller_block_evaluations']!=2360:
                            raise GateClosed('Unexpected validation quota')
                        rows.append({'seed':seed,'method':method,'source_artifact_id':id_,
                          'source_train_git_sha':expected_commit,'source_run_summary_sha256':sha256(td/'run_summary.json'),
                          'source_manifest_sha256':MANIFEST,'source_train_budget':int(summary['ledger_used']),
                          'selected_candidates':len(short),
                          'train_shortlist_csv_sha256':lock['shortlist_sha256'],
                          'train_shortlist_lock_sha256':sha256(subdir/'train_only_shortlist_lock.json'),
                          'planned_val_blocks':2360})
                    source_ids.append(id_)
      all_keys={(m,s) for m in ARTIFACTS for s in SEEDS}
      if seen != all_keys: raise GateClosed(f'Missing {len(all_keys-seen)} or extra {len(seen-all_keys)} methods/seeds')
      rows.sort(key=lambda r:(r['seed'],r['method']))
      index=out_root/'train_only_30seed_5method_shortlist_index.csv'
      with index.open('w',encoding='utf-8',newline='') as f:
          writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');writer.writeheader();writer.writerows(rows)
      report={'status':'PASS','label':'HISTORICAL_TRAIN_ONLY_SHORTLIST_STAGING_NOT_EXPERIMENTAL_VALIDATION',
         'source_manifest_sha256':MANIFEST,'seeds':list(sorted(SEEDS)),'methods':list(ARTIFACTS),
         'train_source_runs':len(rows),'unique_source_zip_count':len(set(source_ids)),
         'candidate_slots':len(rows)*20,'planned_val_block_evaluations':sum(r['planned_val_blocks'] for r in rows),
         'source_train_total_controller_block_evaluations':sum(r['source_train_budget'] for r in rows),
         'method_seed_coverage':{m:len([r for r in rows if r['method']==m]) for m in ARTIFACTS},
         'index_sha256':sha256(index),
         'limitations':['Historical training results, not new optimization','No VAL/TEST/OOD data read','Validation replay still absent','Control candidate shortlist does not equalize optimizer search strategies']}
      (out_root/'stage_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
      return report
    except BaseException:
        import shutil;shutil.rmtree(out_root,ignore_errors=True)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact-dir',type=Path,required=True)
    p.add_argument('--output-root',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(execute(a.artifact_dir,a.output_root),indent=2))
if __name__=='__main__':main()
