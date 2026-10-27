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
    args=parser.parse_args()
    try:
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
