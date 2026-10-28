"""Engineering CLI. Scientific commands fail before reading scientific inputs."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.provenance import validate_manifest
from crmt_edge_ems.gates import gate_report,require_scientific_execution
from crmt_edge_ems.experiment_runner import dry_run,environment

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','verify','dry-run','gate-check','discovery','archive-build','shortlist-select','audit','analyze','independent-test','report'])
    parser.add_argument('--out',type=Path)
    parser.add_argument('--optimizer-seed',type=int,default=2001);parser.add_argument('--simulation-seed',type=int,default=3001)
    parser.add_argument('--ems-plan',type=Path,help='Opt-in hash-bound real EMS engineering execution plan')
    parser.add_argument('--data-root',type=Path)
    parser.add_argument('--engineering',action='store_true',help='Permit explicitly exposed/synthetic fixtures only')
    args=parser.parse_args()
    try:
        if args.ems_plan is not None:
            # No scientific inputs are read without explicit engineering scope.
            if not args.engineering: require_scientific_execution('discovery')
            if args.data_root is None or args.out is None: raise ContractError('--data-root and directory --out required')
            if args.command=='dry-run': raise ContractError('dry-run and real EMS plan are distinct commands')
            from crmt_edge_ems.execution_backend import EMSExecutionBackend
            plan=json.loads(args.ems_plan.read_text(encoding='utf-8'))
            if plan.get('scope')!='ENGINEERING_EXPOSED_OR_SYNTHETIC': raise ContractError('engineering flag cannot authorize prospective inputs')
            result=EMSExecutionBackend(plan,data_root=args.data_root,output=args.out).run(args.command)
            print(json.dumps(result,indent=2,allow_nan=False));return 0
        if args.engineering: raise ContractError('--engineering requires --ems-plan')
        if args.command not in {'prepare','verify','dry-run','gate-check'}: require_scientific_execution(args.command)
        if args.command=='gate-check': result=gate_report()
        else:
            manifest=json.loads((ROOT/'reproducibility/current_source_manifest.json').read_text(encoding='utf-8'))
            verification=validate_manifest(ROOT,manifest)
            if args.command=='dry-run':
                if args.out is None: raise ContractError('--out required for dry-run')
                result=dry_run(args.out,optimizer_seed=args.optimizer_seed,simulation_seed=args.simulation_seed,source_binding=manifest['content_sha256'])
            else: result={'source_validation':verification,'environment':environment(ROOT),'CONFIRMATORY_STATUS':'NO_GO'}
        if args.out is not None and args.command!='dry-run':
            args.out.parent.mkdir(parents=True,exist_ok=True)
            with args.out.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,allow_nan=False)
        print(json.dumps(result,indent=2,allow_nan=False))
    except (ContractError,OSError,ValueError) as exc:
        print(json.dumps({'status':'BLOCKED','error':str(exc),'CONFIRMATORY_STATUS':'NO_GO'}));return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
