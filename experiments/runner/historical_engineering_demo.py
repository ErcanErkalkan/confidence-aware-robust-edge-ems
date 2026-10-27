"""Auditable partial-TRACE engineering replay, never a complete scientific day."""
from pathlib import Path
import argparse
import sys
import json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from crmt_edge_ems.contracts import canonical,digest,file_hash,strict_risk,OBJECTIVES,ContractError
from crmt_edge_ems.profiling import CostTracker
from crmt_edge_ems.safety import SafetyLimits,simulate_checked,SafetyBlocked
from crmt_edge_ems.parameter_space import fixed_controller_parameters,build_tuned_controller
from jer_microgrid.config import SiteConfig
from jer_microgrid.metrics import compute_metrics
from data_adapters.validation import reconstruct_with_lineage

def run(source,out):
    source=Path(source);out=Path(out)
    if out.exists() and any(out.iterdir()): raise ContractError('preserve previous diagnostic output')
    out.mkdir(parents=True,exist_ok=True)
    raw=pd.read_csv(source,nrows=10000)
    cols=['read_ts','inverter','outsumw']+[c for c in ('pv1power','pv2power','pv3power') if c in raw]
    numeric=raw[cols].apply(pd.to_numeric,errors='coerce');finite=np.isfinite(numeric.to_numpy()).all(axis=1)
    nonnegative=(numeric[[c for c in cols if c not in {'read_ts','inverter'}]]>=0).all(axis=1)
    inv=numeric['inverter'];valid=finite&nonnegative&(inv==1)
    # Explicit engineering subset policy. No row is silently removed from a
    # scientific estimand: the entire selection/exclusion index is recorded.
    subset=numeric.loc[valid].drop_duplicates(['read_ts','inverter'],keep='first')
    row_numbers=(subset.index+1).tolist()
    lineage=reconstruct_with_lineage(subset,source_sha256=file_hash(source),original_row_numbers=row_numbers,cadence_minutes=2)
    lineage=lineage.sort_values('timestamp').reset_index(drop=True)
    config={'scope':'HISTORICAL_EXPOSED_PARTIAL_TRACE_ENGINEERING_NOT_INDEPENDENT_OR_FULL_DAY',
        'source_path':str(source),'source_sha256':file_hash(source),'source_rows_read':len(raw),
        'selected_original_rows':row_numbers,'excluded_original_rows':sorted(set(range(1,len(raw)+1))-set(row_numbers)),
        'subset_policy':'First 10000 rows; inverter1; complete finite nonnegative load/PV; first row per duplicate key; explicitly exploratory diagnostic only',
        'scenario_assumptions':'Default SiteConfig 100kWh battery, 50kW power, 0.2-0.8 SOC, 0.95 efficiencies; 1000kW grid import/export stress caps; not provider physical facts',
        'independent_test':False}
    (out/'config.json').write_bytes(canonical(config))
    # Select three contiguous 8-bin pieces; do not call them independent days.
    pieces=[]
    for i in range(0,len(lineage)-7,8):
        g=lineage.iloc[i:i+8].copy();dt=pd.DatetimeIndex(g['timestamp']).as_unit('ns').asi8
        if len(g)==8 and np.all(np.diff(dt)==120*10**9): pieces.append(g)
        if len(pieces)==3:break
    if len(pieces)<3: raise ContractError('not enough contiguous diagnostic pieces; no scientific completeness inferred')
    site=SiteConfig(ts_hours=2/60);limits=SafetyLimits(.2,.8,50,50,100,.95,.95,2/60,1000,1000,20,100,10)
    params=fixed_controller_parameters(site);tracker=CostTracker(3);evaluations=[];all_lineage=[]
    for i,g in enumerate(pieces):
        key=tracker.reserve('TRAIN','fixed-controller',f'ENGINEERING_PARTIAL_PIECE:{i}')
        try:
            with tracker.measure('simulation'): sim=simulate_checked(g,build_tuned_controller(site,params),site,limits)
            metrics=compute_metrics(sim.series,site)
            vector=[metrics[o] for o in OBJECTIVES]
            if not np.isfinite(vector).all(): raise ContractError('nonfinite scientific objective from replay')
            tracker.finish(key,success=True)
        except Exception:
            tracker.finish(key,success=False);raise
        input_ids=g['lineage_id'].tolist()
        sim_rows=sim.series.assign(timestamp=sim.series['timestamp'].astype(str)).to_dict(orient='records')
        evaluations.append({'piece':i,'input_lineage_ids':input_ids,'input_sha256':digest(input_ids),
            'parameter_sha256':digest(params),'simulation_sha256':digest(sim_rows),'objective_vector':vector,
            'objective_sha256':digest(vector)})
        for r in g.to_dict(orient='records'):r['timestamp']=r['timestamp'].isoformat();all_lineage.append(r)
    risk=strict_risk([e['objective_vector'] for e in evaluations]).tolist()
    report={'status':'ENGINEERING_TRACE_MEASURED_NOT_SCIENTIFIC_VALIDATION','evaluations':evaluations,
        'lineage_sha256':digest(all_lineage),'risk_vector':risk,'risk_sha256':digest(risk),
        'archive_members':['fixed-controller'],'selected_candidate':'fixed-controller',
        'selection_rule':'Singleton engineering demonstration, not R19/B10 selection','cost':tracker.report(),
        'physical_assumptions_verified':False,'CONFIRMATORY_STATUS':'NO_GO'}
    (out/'lineage.json').write_bytes(canonical(all_lineage));(out/'report.json').write_bytes(canonical(report));return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    print(json.dumps(run(a.source,a.out),indent=2))
