#!/usr/bin/env python3
"""Four historically exposed, newly raw-verified OpenCEM TRAIN full-day
ENGINEERING simulator/safety smoke runs. No prospective claims or independent TEST.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import pandas as pd
import numpy as np

BLOCKS=[f'opencem:inv{inv}:{day}' for day in ('2025-08-02','2025-08-31') for inv in (1,2)]

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()

def run():
 ap=argparse.ArgumentParser();ap.add_argument('--full-csv',type=Path,required=True);ap.add_argument('--front-f0',type=Path,required=True);ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
 if args.out.exists():raise ValueError('Fail closed: output must not exist')
 sys.path.insert(0,str(args.source_root/'src'))
 from crmt_edge_ems.site_model import build_primary_opencem_site
 from crmt_edge_ems.parameter_space import build_tuned_controller,PARAM_NAMES
 from crmt_edge_ems.safety import SafetyLimits,simulate_checked
 from crmt_edge_ems.metrics_v2 import compute_metrics_v2,METRICS_VERSION
 from jer_microgrid.metrics import compute_metrics
 df=pd.read_csv(args.full_csv)
 front=pd.read_csv(args.front_f0)
 if front.candidate_id.duplicated().any():raise ValueError('Duplicate candidate')
 # One preselected F0 baseline controller; no optimizer search/hidden selection.
 row=front.sort_values('candidate_id').iloc[0]
 candidate=str(row.candidate_id);params={k:float(row[k]) for k in PARAM_NAMES}
 results=[];out_traces=[]
 for block in BLOCKS:
  part=df[df.block_id==block].sort_values('bin_utc').copy()
  ts=pd.to_datetime(part.bin_utc,utc=True)
  if len(part)!=720 or ts.duplicated().any() or not ts.is_monotonic_increasing or not (ts.diff().dropna()==pd.Timedelta(minutes=2)).all():raise ValueError('Invalid full-day support: '+block)
  if np.max(np.abs(part.base_kw_raw-part.base_kw_frozen))>1e-10:raise ValueError('Frozen value mismatch: '+block)
  inv=int(block.split(':')[1][3:]);site=build_primary_opencem_site(inv)
  profile=pd.DataFrame({'timestamp':ts.reset_index(drop=True),'base_kw':part.base_kw_raw.to_numpy(dtype=float),'peak_flag':np.zeros(len(part),dtype=int)})
  record={'block_id':block,'candidate_id':candidate,'source':'VERIFIED_REAGGREGATED_OPENCEM_REAL_TRAIN_MEASUREMENT','n_input_ticks':len(part),'safety_basis':'SCENARIO_ASSUMPTIONS_NOT_CERTIFIED'}
  try:
   sim=simulate_checked(profile,build_tuned_controller(site,params),site,SafetyLimits.from_site(site))
   metrics=compute_metrics_v2(sim.series,site)
   legacy=compute_metrics(sim.series,site)
   record.update({'result':'PASS_CHECKED_EMS_ENGINEERING','n_output_ticks':len(sim.series),'cap_violation_pct_total':float(metrics['cap_violation_pct_total']),'ramp95_kw_per_min':float(metrics['ramp95_kw_per_min']),'flip_per_day':float(metrics['flip_per_day']),'lfp_cycle_loss_v2_pct':float(metrics['lfp_cycle_loss_pct']),'lfp_cycle_loss_legacy_pct':float(legacy['lfp_cycle_loss_pct']),'efcrf_v2':float(metrics['efcrf']),'efcrf_legacy':float(legacy['efcrf']),'metrics_version':METRICS_VERSION})
   traced=sim.series.copy();traced.insert(0,'block_id',block);traced.insert(1,'candidate_id',candidate);out_traces.append(traced)
  except Exception as exc:
   record.update({'result':'SAFETY_VETO_OR_CONTROLLER_ERROR','exception_class':type(exc).__name__,'reason':str(exc),'veto_codes':list(getattr(exc,'codes',()))})
  results.append(record)
 if not out_traces:raise ValueError('All checked simulator runs failed; no successful evidence')
 args.out.mkdir(parents=True)
 pd.DataFrame(out_traces[0].columns.tolist(),columns=['columns']).to_csv(args.out/'TRACE_SCHEMA.csv',index=False)
 pd.concat(out_traces,ignore_index=True).to_csv(args.out/'CHECKED_EMS_720TICK_TRACE_PRIVATE.csv',index=False,float_format='%.17g')
 pd.DataFrame(results).to_csv(args.out/'DAYWISE_CHECKED_EMS_ENGINEERING.csv',index=False)
 evidence={'result':'ENGINEERING_SAFE_CHECKED_REAL_TRAIN_SIMULATION_ONLY','attempts':len(results),'passes':sum(x['result']=='PASS_CHECKED_EMS_ENGINEERING' for x in results),'failures':sum(x['result']!='PASS_CHECKED_EMS_ENGINEERING' for x in results),'candidate':candidate,'blocks':BLOCKS,'details':results,'source_raw_recomputed_full_csv_sha256':sha(args.full_csv),'historical_front_f0_sha256':sha(args.front_f0),'source_main': '2dcbaa49db42e7a0d4cb6edde3977f0384db1679','corrected_metrics':'CRMT-METRICS-v2-RAINFLOW-TERMINAL-SOC','scenario_safety_only':True,'process_level_timeout_used':False,'original_experiment_reconstructed':False,'independent_TEST_executed':False,'R19_prospective_executed':False,'full_406_blocks_emulated':False,'physical_limits_approved':False,'scientific_go':'NO_GO'}
 (args.out/'CHECKED_EMS_ENGINEERING_STATUS.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in evidence.items() if k not in ('details','blocks')},indent=2))
if __name__=='__main__':run()