"""Full 256-candidate actual EMS equal-evaluation engineering cost benchmark.

Inline built-in controllers are used only for this declared microbenchmark.
Process-supervisor startup/IPC, HIL, energy and independent data are not measured.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import os
import platform
import time
import tracemalloc
import numpy as np
import pandas as pd
from jer_microgrid.config import SiteConfig
from crmt_edge_ems.contracts import canonical, digest, OBJECTIVES, strict_risk, pareto_mask
from crmt_edge_ems.generator import sobol_candidates
from crmt_edge_ems.strict_replay_v2 import StrictReplayBlock, StrictReplayEvaluator
from crmt_edge_ems.archive import CandidateRecord, ConfidenceArchive
from crmt_edge_ems.risk import RiskConfig
from crmt_edge_ems.budget import EvaluationLedger
from crmt_edge_ems.engineering_fixtures import execution_context

def main():
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    design={"scope":"FULL256_SYNTHETIC_ENGINEERING_MICROBENCHMARK","candidate_count":256,
        "paired_blocks":2,"ticks_per_block":12,"cadence_minutes":2,"n_boot":200,"seed":991,
        "arms":["F0","LEGACY_F1"],"supervisor":"INLINE_BUILTIN_ONLY",
        "cost_policy":"Each arm independently executes all 512 identical-support EMS events.",
        "not_measured":["energy","supervisor IPC/startup","checkpoint IO","prospective end-to-end R19"],
        "source_context":execution_context()}
    (a.out/"PREDECLARED_DESIGN.json").write_bytes(canonical(design))
    phases={}
    @contextmanager
    def phase(name):
        w=time.perf_counter();c=time.process_time();tracemalloc.start()
        try:yield
        finally:
            _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            phases[name]={"wall_seconds":time.perf_counter()-w,"parent_cpu_seconds":time.process_time()-c,
                "peak_python_allocated_bytes":peak,"scope":"THIS_PHASE_IN_ONE_PROCESS"}
    with phase("candidate_generation"):
        params=sobol_candidates(256,seed=991);ids=[f"c{i:04d}" for i in range(256)]
    blocks=[StrictReplayBlock(f"d{i}",pd.DataFrame({"timestamp":pd.date_range(f"2026-01-{i+1:02d}",periods=12,freq="2min",tz="UTC"),
        "base_kw":15+4*np.sin(np.arange(12)/3+i),"peak_flag":np.zeros(12,dtype=int)}),cadence_minutes=2,expected_ticks=12) for i in range(2)]
    site=SiteConfig(ts_hours=2/60);results={};arrays={}
    for arm in design["arms"]:
        ledger=EvaluationLedger(512);evaluator=StrictReplayEvaluator(site,ledger=ledger,supervisor=None)
        # All support is checked before reserving any event.
        evaluator.validate_blocks(blocks);records={}
        with phase(arm+"_simulation_and_metrics"):
            for cid,param in zip(ids,params):
                df=evaluator.evaluate(param,blocks,candidate_id=cid)
                samples=df[list(OBJECTIVES)].to_numpy()
                records[cid]=CandidateRecord(cid,param,samples,strict_risk(samples),tuple(df["block_id"]))
            ledger.assert_exact()
        calls=0
        with phase(arm+"_archive_and_calibration"):
            if arm=="F0":
                selected=[c for c,k in zip(ids,pareto_mask([records[c].risk_vector for c in ids])) if k]
            else:
                import crmt_edge_ems.archive as module
                original=module.confidence_risk_dominance
                def counted(*args,**kwargs):
                    nonlocal calls
                    calls+=1;return original(*args,**kwargs)
                archive=ConfidenceArchive(n_boot=200)
                for record in records.values():archive.add(record)
                module.confidence_risk_dominance=counted
                try:selected=archive.confidently_nondominated_ids()
                finally:module.confidence_risk_dominance=original
        with phase(arm+"_selection"):
            x=np.stack([records[c].risk_vector for c in ids]);span=np.ptp(x,axis=0)
            z=np.divide(x-x.min(axis=0),span,out=np.zeros_like(x),where=span>0)
            rank=sorted(range(256),key=lambda i:(float(z[i].max()),float(z[i].sum()),ids[i]))
            picks=[ids[i] for i in rank if ids[i] in selected][:10]
        arrays[arm]=[records[c].samples.tolist() for c in ids]
        results[arm]={"simulator_events":ledger.used,"failed_simulator_events":0,"native_archive_size":len(selected),
            "selected":picks,"capacity_status":"K10" if len(picks)==10 else "BLOCKED_CAPACITY_NO_BACKFILL",
            "confidence_pair_calls":calls,"bootstrap_replicates":2*200*calls,"metrics_sha256":digest(arrays[arm])}
    if arrays["F0"]!=arrays["LEGACY_F1"]:raise RuntimeError("matched simulator inputs produced differing metrics")
    rss=None
    if os.name=="posix":
        import resource
        rss=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if platform.system()=="Darwin" else 1024))
    report={"design":design,"methods":results,"phases":phases,"actual_simulator_events":1024,
        "equal_simulator_evaluation_budget":True,"equal_end_to_end_compute_budget":False,
        "process_peak_rss_bytes":rss,"process_peak_rss_scope":"ENTIRE_DRIVER_NOT_PHASE_ADDITIVE",
        "energy_joules":None,"source_context":design["source_context"],
        "fairness_limit":"Synthetic compact-support microbenchmark. No full R19 execution or hardware energy claim."}
    with phase("serialization"):
        (a.out/"RESULTS.json").write_bytes(canonical(report))
    report["phases"]=phases
    (a.out/"RESULTS.json").write_bytes(canonical(report))
if __name__=="__main__":main()
