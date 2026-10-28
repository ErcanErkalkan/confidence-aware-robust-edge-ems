"""Predeclared 2x2x2 engineering factorial on checked real EMS simulations.

C: tail weight 0/.5; F: final point/confidence archive; A: RR/adaptive.
F affects final archive only in the current implementation. Identical simulator
records are shared across F cells; they are not double-counted as execution.
"""
from pathlib import Path
import argparse
import itertools
import numpy as np
from crmt_edge_ems.contracts import canonical, strict_risk, pareto_mask, OBJECTIVES
from crmt_edge_ems.engineering_fixtures import make_engineering_plan
from crmt_edge_ems.execution_backend import EMSExecutionBackend

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--out",required=True,type=Path);args=parser.parse_args()
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    design={"scope":"EXPLORATORY_SYNTHETIC_ENGINEERING","seeds":[41,73],"candidate_count":4,
        "discovery_budget_per_cell":12,"audit_events_per_executed_CA_cell":8,"initial_blocks":2,
        "discovery_blocks":4,"audit_blocks":2,"ticks_per_block":24,"C":[0,.5],
        "F":["POINT","LEGACY_F1"],"A":["round_robin","adaptive"],
        "outcomes":["native_archive_size","reference_retention"],"alpha":None,
        "independent_units":"NONE: deterministic synthetic fixtures; optimizer seeds only",
        "parameter_selection_after_outcomes":False,
        "F_semantics":"Final archive only; no F-dependent allocation path in current study."}
    (out/"PREDECLARED_DESIGN.json").write_bytes(canonical(design))
    rows=[];actual=0;allocation={}
    for seed,C,A in itertools.product(design["seeds"],(0,1),(0,1)):
        tag=f"seed{seed}_C{C}_A{A}";root=out/tag;data=root/"fixture"
        plan=make_engineering_plan(data,ticks=24,discovery_blocks=4,candidates=4,budget=12,seed=seed)
        plan.update(risk_weight=design["C"][C],allocation_mode=design["A"][A])
        (data/"plan.json").write_bytes(canonical(plan))
        backend=EMSExecutionBackend(plan,data_root=data,output=root/"execution");report=backend.run()
        discovery=backend.store.load("discovery");archive=backend.store.load("archive-build");audit=backend.store.load("audit")
        actual+=report["actual_simulator_events"]
        allocation[tag]=discovery["allocation_counts"]
        ids=list(discovery["candidates"]);obs=audit["observations"]
        reference={c for c,k in zip(ids,pareto_mask([strict_risk(list(obs[c].values()),tail_weight=plan["risk_weight"]) for c in ids])) if k}
        for F,arm in enumerate(("F0","F1")):
            picks=set(archive["archives"][arm])
            rows.append({"seed":seed,"C":C,"F":F,"A":A,"native_archive_size":len(picks),
                "reference_retention":len(picks&reference)/len(reference),
                "reference_size":len(reference),"logical_evaluation_budget":12,
                "event_records_shared_across_F":True,"allocation_counts":discovery["allocation_counts"]})
    effects={}
    # Standard +/-1 factorial contrasts, descriptive only (no independent physical sampling).
    for outcome in design["outcomes"]:
        effects[outcome]={}
        for size in (1,2,3):
            for factors in itertools.combinations(("C","F","A"),size):
                key="*".join(factors)
                effects[outcome][key]=float(np.mean([np.prod([2*r[k]-1 for k in factors])*r[outcome] for r in rows])*2)
    differing=sum(allocation[f"seed{s}_C{c}_A0"]!=allocation[f"seed{s}_C{c}_A1"] for s,c in itertools.product(design["seeds"],(0,1)))
    (out/"RESULTS.json").write_bytes(canonical({"scope":design["scope"],"design":design,"rows":rows,
        "factorial_contrasts":effects,"allocation_traces":allocation,"CA_pairs_with_different_allocation":differing,
        "actual_simulator_events":actual,"logical_cells":len(rows),
        "ADAPTIVE_CONTRIBUTION_SUPPORTED":False,"independent_causal_or_operational_benefit":False,
        "interpretation":"Mechanism and descriptive factorial evidence only; historical 30/30 equality remains unchanged."}))
if __name__=="__main__":main()
