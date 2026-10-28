#!/usr/bin/env python3
"""Read-only retrospective *engineering* rescore, NOT original execution reconstruction.

Given the main source ZIP extracted to a local directory, historical TRAIN archive
candidate parameters and a frozen accepted-bin historical archive, run the same
candidate/block through the installed legacy and versioned v2 metric functions.
Never edits any original dataset; only newly generated outputs under --out.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

MAIN_SHA = '2dcbaa49db42e7a0d4cb6edde3977f0384db1679'
COLUMNS = ('cap_violation_pct_total','lfp_cycle_loss_pct','ramp95_kw_per_min','flip_per_day','efcrf','idod')
FOUR_BLOCKS = [f'opencem:inv{i}:{day}' for day in ('2025-08-02','2025-08-31') for i in (1,2)]
PARAMS=('base_soft_low','base_soft_high','prep_power_cap_frac','lookahead_gain','reserve_enter_margin',
        'reserve_exit_margin','hold_decay','near_cap_forecast_buffer_frac','near_cap_soc_boost')

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''):
            h.update(b)
    return h.hexdigest()

def get_profiles(lineage):
    member='RESULTS/ACCEPTED_2MIN_REPLAY_BINS_WITH_SOURCE_ROWS.csv.gz'
    with zipfile.ZipFile(lineage,'r') as z:
        with gzip.GzipFile(fileobj=z.open(member)) as stream:
            raw=pd.read_csv(stream,usecols=('block_id','bin_utc','base_kw'))
    profiles={}
    for block_id in FOUR_BLOCKS:
        rows=raw[raw.block_id==block_id].copy()
        t=pd.to_datetime(rows.bin_utc,utc=True,errors='raise')
        if len(rows)!=720 or t.isna().any() or t.duplicated().any() or not t.is_monotonic_increasing or \
           not (t.diff().dropna()==pd.Timedelta(minutes=2)).all() or \
           not np.isfinite(rows.base_kw.to_numpy(dtype=float)).all():
            raise ValueError('Pilot block does not satisfy exact 720-bin support: '+block_id)
        # The historic OpenCEM adapter makes neutral peak flags; no tariff inference.
        profiles[block_id]=pd.DataFrame({'timestamp':t.reset_index(drop=True),
             'base_kw':rows.base_kw.to_numpy(dtype=float),
             'peak_flag':np.zeros(len(rows),dtype=np.int64)})
    return profiles

def pareto_mask_exact(values):
    # Pure minimization, no tolerance, no point-specific extra tie breaker.
    n=len(values); mask=np.ones(n,dtype=bool)
    for i in range(n):
        mask[i]=not np.any(np.all(values <= values[i],axis=1)&np.any(values < values[i],axis=1))
    return mask

def dominance_pairs(a):
    n=len(a)
    return {(i,j) for i in range(n) for j in range(n) if i!=j
            and np.all(a[i] <= a[j]) and np.any(a[i] < a[j])}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-root',type=Path,required=True)
    ap.add_argument('--source-zip',type=Path,required=True)
    ap.add_argument('--lineage-zip',type=Path,required=True)
    ap.add_argument('--front-f0',type=Path,required=True)
    ap.add_argument('--front-f1',type=Path,required=True)
    ap.add_argument('--historic-candidate-metrics',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--extra-f1-only',type=int,default=10,help='First sorted F1-only candidates included after the complete F0 archive')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(args.source_root/'src'))
    from crmt_edge_ems.site_model import build_primary_opencem_site
    from crmt_edge_ems.parameter_space import build_tuned_controller
    from jer_microgrid.simulation import simulate_controller
    from jer_microgrid.metrics import compute_metrics
    from crmt_edge_ems.metrics_v2 import compute_metrics_v2, METRICS_VERSION, rainflow_cycles_detailed_v2
    from jer_microgrid.metrics import rainflow_cycles_detailed
    front0=pd.read_csv(args.front_f0)
    front1=pd.read_csv(args.front_f1)
    for f in (front0,front1):
        if f.candidate_id.duplicated().any() or not set(PARAMS).issubset(f):
            raise ValueError('Bad historical candidate parameter registry')
    if not set(front0.candidate_id).issubset(set(front1.candidate_id)):
        raise ValueError('F0 pilot archive not contained in F1 pilot archive')
    original_f1_size=len(front1)
    if args.extra_f1_only < 0: raise ValueError('extra-f1-only must be nonnegative')
    f0_ids=set(front0.candidate_id)
    first_extra=sorted(set(front1.candidate_id)-f0_ids)[:args.extra_f1_only]
    front1=front1[front1.candidate_id.isin(f0_ids.union(first_extra))].copy().sort_values('candidate_id')
    profiles=get_profiles(args.lineage_zip)
    hist=pd.read_csv(args.historic_candidate_metrics)
    hist=hist[hist.block_id.isin(FOUR_BLOCKS)].set_index(['candidate_id','block_id'])
    expected_rows=len(front1)*len(FOUR_BLOCKS)
    if len(hist.loc[hist.index.get_level_values('candidate_id').isin(front1.candidate_id)])!=expected_rows:
        raise ValueError('Not all F1 candidates have recorded historic rows in 4 pilot blocks')
    old_new=[]; errors=[]
    sites={i:build_primary_opencem_site(i) for i in (1,2)}
    for j,candidate in enumerate(front1.itertuples(index=False),start=1):
        c=candidate.candidate_id; params={p:float(getattr(candidate,p)) for p in PARAMS}
        for b,profile in profiles.items():
            site=sites[int(b.split(':')[1].replace('inv',''))]
            try:
                trajectory=simulate_controller(profile,build_tuned_controller(site,params),site).series
                legacy=compute_metrics(trajectory,site)
                corrected=compute_metrics_v2(trajectory,site)
            except Exception as exc:
                errors.append({'candidate_id':c,'block_id':b,'error_type':type(exc).__name__,'detail':str(exc)})
                continue
            historic=hist.loc[(c,b)]
            row={'candidate_id':c,'block_id':b,'site_id':int(b.split(':')[1].replace('inv','')),
                 'source_main_sha':MAIN_SHA,'metric_version_v2':METRICS_VERSION,
                 'evidence_scope':'RETROSPECTIVE_CURRENT_CODE_RERUN_ON_EXPOSED_TRAIN_NOT_ORIGINAL_EXECUTION',
                 'n_ticks':len(trajectory),
                 'max_soc':float(max(trajectory.soc.max(),trajectory.soc_next.max())),
                 'min_soc':float(min(trajectory.soc.min(),trajectory.soc_next.min()))}
            for m in COLUMNS:
                row[f'legacy_rerun_{m}']=float(legacy[m])
                row[f'v2_rerun_{m}']=float(corrected[m])
                row[f'delta_v2_minus_legacy_{m}']=float(corrected[m])-float(legacy[m])
                row[f'original_stored_{m}']=float(historic[m])
                row[f'legacy_rerun_minus_original_{m}']=float(legacy[m])-float(historic[m])
            old_new.append(row)
    output=pd.DataFrame(old_new)
    output.to_csv(args.out/'LEGACY_VS_V2_OBJECTIVES.csv',index=False,float_format='%.17g')
    pd.DataFrame(errors,columns=('candidate_id','block_id','error_type','detail')).to_csv(args.out/'FAILED_RERUNS.csv',index=False)
    summary={'main_sha':MAIN_SHA,'historical_legacy_originals_overwritten':False,
      'evidence_scope':'ENGINEERING_EXPLORATORY_REPLAY_OF_HISTORICAL_TRAIN_ACCEPTED_BINS; NOT ORIGINAL_EXECUTION; NOT PROSPECTIVE_OR_TEST',
      'candidate_F0':len(front0),'candidate_F1_pilot':len(front1),'candidate_F1_original':original_f1_size,'pilot_blocks':FOUR_BLOCKS,
      'attempted_events':expected_rows,'successful_events':len(old_new),'failed_events':len(errors),
      'results_not_historic_original_rerun':True,'metrics_version_v2':METRICS_VERSION,
      'source_sha256':{str(k):digest(v) for k,v in [('source_zip',args.source_zip),('lineage_zip',args.lineage_zip),('front_F0',args.front_f0),('front_F1',args.front_f1),('historical_metrics',args.historic_candidate_metrics)]},
      'code_sha256':{p:digest(args.source_root/p) for p in ('src/jer_microgrid/metrics.py','src/crmt_edge_ems/metrics_v2.py','src/jer_microgrid/simulation.py')},
      'measurement_contract':'Per-candidate/per-block same new simulated trajectory, evaluated by historical metric function and v2 metric function. Historical stored metrics independently cross-checked for mismatch.',
      'limitations':['Four pre-exposed TRAIN blocks from one seed and a preselected F1 subset; no independent inference.',
        'Historical per-tick SOC/command traces are not in the original stored metrics CSV.',
        'An identical rerun relative to old historic execution is not assumed.',
        'We do NOT silently alter original stored archive memberships or risk-weighted fronts.',
        'All candidate site profiles use neutral peak flags as documented by OpenCEM adapter.',
        'The 4-block arithmetic mean diagnostic is not the historical 12,600-event mean+CVaR optimizer target.']}
    if len(output):
        for m in COLUMNS:
            x=output[f'delta_v2_minus_legacy_{m}'];y=output[f'legacy_rerun_minus_original_{m}'];a=np.abs(x.to_numpy());z=np.abs(y.to_numpy())
            summary[m]={'n':len(x),'delta_mean':float(x.mean()),'delta_median':float(x.median()),
                'delta_min':float(x.min()),'delta_max':float(x.max()),'nonzero_gt_1e-12':int((a>1e-12).sum()),
                'historic_legacy_parity_within_1e-9':int((z<=1e-9).sum()),
                'historic_legacy_parity_outside_1e-9':int((z>1e-9).sum()),
                'max_abs_legacy_minus_original':float(z.max())}
    ranking_rows=[];summary['pilot_archive_diagnostics']={}
    for label,f in [('F0',front0),('F1',front1)]:
        sub=output[output.candidate_id.isin(f.candidate_id)]
        good=sub.groupby('candidate_id').size();ids=sorted(set(good[good==len(FOUR_BLOCKS)].index))
        if not ids:
            summary['pilot_archive_diagnostics'][label]={'full_block_candidates':0};continue
        dat=sub[sub.candidate_id.isin(ids)].groupby('candidate_id')
        dims=COLUMNS[:4]; old=np.vstack([dat[f'legacy_rerun_{m}'].mean().reindex(ids).to_numpy() for m in dims]).T
        new=np.vstack([dat[f'v2_rerun_{m}'].mean().reindex(ids).to_numpy() for m in dims]).T
        oldmask=pareto_mask_exact(old);newmask=pareto_mask_exact(new)
        p0=dominance_pairs(old);p1=dominance_pairs(new)
        summary['pilot_archive_diagnostics'][label]={'full_block_candidates':len(ids),'old_pareto_count':int(oldmask.sum()),
            'v2_pareto_count':int(newmask.sum()),'pareto_membership_changed':int((oldmask!=newmask).sum()),
            'old_dominance_pairs':len(p0),'v2_dominance_pairs':len(p1),
            'lost_dominance_pairs':len(p0-p1),'new_dominance_pairs':len(p1-p0),
            'diagnostic_only':'4-block arithmetic mean within fixed historical archive; NOT historical mean+CVaR Pareto or measured selection fidelity'}
        for i,c in enumerate(ids):
            r={'archive':label,'candidate_id':c,'old_is_pareto':bool(oldmask[i]),'v2_is_pareto':bool(newmask[i]),
               'pareto_changed':bool(oldmask[i]!=newmask[i])}
            for k,m in enumerate(dims):r['mean_legacy_'+m]=old[i,k];r['mean_v2_'+m]=new[i,k]
            ranking_rows.append(r)
    pd.DataFrame(ranking_rows).to_csv(args.out/'PILOT_PARETO_MEMBERSHIP.csv',index=False)
    # Independent simple mathematical checks for regression/counterexample coverage.
    trajectory=np.array([0.2,0.8,0.2]);old_half=sum(d*w for d,w,*_ in rainflow_cycles_detailed(trajectory));v2_full=sum(d*w for d,w,*_ in rainflow_cycles_detailed_v2(trajectory))
    assert abs(old_half-0.3)<1e-12 and abs(v2_full-0.6)<1e-12
    summary['unit_counterexample']={'soc_path':[0.2,0.8,0.2],'legacy_weighted_depth':old_half,'v2_weighted_depth':v2_full}
    (args.out/'METRIC_SENSITIVITY_STATISTICS.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    return summary

if __name__=='__main__':
    ans=main();print(json.dumps({'attempted':ans['attempted_events'],'successful':ans['successful_events'],'failed':ans['failed_events'],
           'pilot_archive_diagnostics':ans['pilot_archive_diagnostics']},indent=2))
