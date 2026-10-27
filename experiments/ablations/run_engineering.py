"""Small actual EMS simulator factorial regression, synthetic inputs only."""
from pathlib import Path
import argparse
import json
import itertools
import time
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from crmt_edge_ems.ablation import factorial_design,matched_diagnostics
from crmt_edge_ems.contracts import digest,canonical,strict_risk,ContractError,OBJECTIVES
from crmt_edge_ems.profiling import CostTracker
from crmt_edge_ems.evaluator import SyntheticEvaluator,ScenarioBlock
from crmt_edge_ems.generator import sobol_candidates
from crmt_edge_ems.risk import RiskConfig
from crmt_edge_ems.study import CRMTStudy
from jer_microgrid.config import SyntheticConfig

class MeasuredEvaluator(SyntheticEvaluator):
    def __init__(self,tracker):
        super().__init__(synth=SyntheticConfig(hours=1/6));self.tracker=tracker
    def evaluate(self,params,blocks,*,candidate_id):
        blocks=list(blocks);keys=self.tracker.reserve_many('TRAIN',candidate_id,[b.block_id for b in blocks])
        try:
            with self.tracker.measure('simulation'): result=super().evaluate(params,blocks,candidate_id=candidate_id)
            for key in keys:self.tracker.finish(key,success=True)
            return result
        except Exception:
            for key in keys:self.tracker.finish(key,success=False)
            raise
    def aggregate(self,metrics,risk=RiskConfig()):
        vals=strict_risk(metrics[list(OBJECTIVES)].to_numpy(),q=risk.q,tail_weight=risk.tail_weight)
        return dict(zip(OBJECTIVES,vals))

def run(out):
    out=Path(out)
    if out.exists() and any(out.iterdir()): raise ContractError('preserve existing engineering result directory')
    out.mkdir(parents=True,exist_ok=True)
    config={'implementation_id':'CRMT-FACTORIAL-EMS-ENGINEERING-v1','scope':'SYNTHETIC_SMALL_REGRESSION_NOT_R19',
        'optimizer_seed':71,'simulation_seed':9000,'candidates':8,'blocks':8,'train_budget':40,'bootstrap_resamples':200,
        'scenario_duration_minutes':10,'factorial_rows':32,'primary_protocol_unchanged':True}
    (out/'config.json').write_bytes(canonical(config))
    params=sobol_candidates(8,seed=71);candidates={f'c{i}':p for i,p in enumerate(params)}
    blocks=[ScenarioBlock('load_step',9000+i) for i in range(8)];rows=[];base={}
    for confidence,adaptive,risk_on in itertools.product((False,True),repeat=3):
        tracker=CostTracker(40);evaluator=MeasuredEvaluator(tracker);risk=RiskConfig(tail_weight=.5 if risk_on else 0)
        study=CRMTStudy(evaluator,risk=risk,initial_blocks=2,allocation_batch=2,n_boot=200,
            archive_mode='confidence' if confidence else 'risk_pareto',allocation_mode='adaptive' if adaptive else 'round_robin')
        start=time.perf_counter();cpu=time.process_time();r=study.run(candidates,blocks,max_evaluations=40)
        elapsed=time.perf_counter()-start;cpu=time.process_time()-cpu
        if r.budget_used!=40 or len(tracker.events)!=40: raise ContractError('factorial budget mismatch')
        matrix=np.stack([strict_risk(r.candidate_metrics[c][list(OBJECTIVES)].to_numpy(),tail_weight=risk.tail_weight) for c in candidates])
        span=np.ptp(matrix,axis=0);normalized=np.divide(matrix-matrix.min(axis=0),span,out=np.zeros_like(matrix),where=span>0)
        counts={c:len(df) for c,df in r.candidate_metrics.items()};cost=tracker.report()
        cost.update(optimizer_cpu_time=cpu,optimizer_wall_time=elapsed,bootstrap_calls=None,bootstrap_cpu_time=None,
            archive_construction_time=None,uninstrumented='Legacy study internals: bootstrap/archive phase split not separately measured')
        for capacity,strategy in itertools.product((1,3),('linf_l1','l1_linf')):
            order=sorted(range(8),key=lambda i:((float(normalized[i].max()),float(normalized[i].sum())) if strategy=='linf_l1' else (float(normalized[i].sum()),float(normalized[i].max())))+(f'c{i}',))
            picks=[f'c{i}' for i in order if f'c{i}' in r.archive_ids][:capacity]
            row={'confidence':confidence,'adaptive':adaptive,'risk_calibration':risk_on,'output_capacity':capacity,'strategy':strategy,
                'status':'ENGINEERING_MEASURED' if len(picks)==capacity else 'BLOCKED_CAPACITY',
                'archive_ids':r.archive_ids,'allocation_counts':counts,'selected_ids':picks if len(picks)==capacity else [],
                'selected_parameter_sha256':digest(candidates[picks[0]]) if len(picks)==capacity else None,
                'candidate_pool_sha256':digest(candidates),'data_partition_sha256':digest([b.block_id for b in blocks]),
                'optimizer_seed':71,'simulation_seed':9000,'train_budget':40,'cost':cost}
            rows.append(row);base[(confidence,adaptive,risk_on,capacity,strategy)]=row
    comparisons=[]
    for f,c,b,s in itertools.product((False,True),(False,True),(1,3),('linf_l1','l1_linf')):
        a=base[(f,False,c,b,s)];z=base[(f,True,c,b,s)]
        if a['status']=='ENGINEERING_MEASURED' and z['status']=='ENGINEERING_MEASURED':
            comparisons.append({'confidence':f,'risk_calibration':c,'capacity':b,'strategy':s,**matched_diagnostics(a,z)})
    for name,value in [('factorial_rows.json',rows),('adaptive_comparisons.json',comparisons)]: (out/name).write_bytes(canonical(value))
    result={'status':'SYNTHETIC_ENGINEERING_ONLY','unique_optimizer_settings_executed':8,'factorial_rows':len(rows),
        'actual_simulator_controller_block_events':320,'full_R19_or_independent_validation':False,
        'adaptive_benefit':'UNSUPPORTED: one optimizer seed, synthetic short blocks, no held-out uncertainty analysis'}
    (out/'status.json').write_bytes(canonical(result));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.out),indent=2))
