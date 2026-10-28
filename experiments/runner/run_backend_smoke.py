"""Actual full-day EMS engineering smoke. No prospective or independent TEST."""
from pathlib import Path
import argparse
from crmt_edge_ems.execution_backend import EMSExecutionBackend
from crmt_edge_ems.engineering_fixtures import make_engineering_plan
from crmt_edge_ems.contracts import canonical

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--out",type=Path,required=True);args=parser.parse_args()
    data=args.out/"fixture";plan=make_engineering_plan(data)
    backend=EMSExecutionBackend(plan,data_root=data,output=args.out/"execution")
    result=backend.run()
    # Resume verifies hashes and returns persisted outputs without new simulator calls.
    resumed=EMSExecutionBackend(plan,data_root=data,output=args.out/"execution").run()
    if canonical(result)!=canonical(resumed):raise RuntimeError("resume changed engineering output")
    (args.out/"SUMMARY.json").write_bytes(canonical({"scope":"SYNTHETIC_ENGINEERING_EXPOSED",
        "full_day_ticks":720,"actual_simulator_events":result["actual_simulator_events"],
        "candidate_count":4,"discovery_blocks":2,"audit_blocks":2,
        "resume_hash_verified":True,"independent_TEST":False,"R19_prospective":False,
        "source_context":plan["execution_context"],"report":result}))
if __name__=="__main__":main()
