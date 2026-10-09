#!/usr/bin/env python3
"""EAAI/P0 E2: original OpenCEM VAL replay with Gate1 K=20 locked candidates.

This is an engineering pilot, NOT a newly independent test. Run from canonical
repository with PYTHONPATH pointing to both canonical src/tools and sidecar src.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from crmt_p0.gate2_validation import *
from crmt_p0.equal_quota import METHODS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--raw-root',type=Path,required=True)
    p.add_argument('--verification-csv',type=Path,required=True)
    p.add_argument('--block-lock-json',type=Path,required=True)
    p.add_argument('--shortlist-root',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    if args.seed not in range(1001,1031):
        raise GateClosed('Gate2 full 30 seed expansion supports only seeds 1001-1030')
    if args.output_dir.exists():
        raise GateClosed('output directory already exists')
    # Always use the established original model and source verification.
    from opencem_confirmatory_train import build_locked_split_blocks
    from opencem_qa import load_verified_csvs
    from crmt_edge_ems.replay import MultiSiteReplayEvaluator
    from crmt_edge_ems.site_model import build_primary_opencem_site
    from crmt_edge_ems.selection import score_validation_candidates,select_one_per_method
    from crmt_edge_ems.indicators import validation_optimizer_indicators
    lock=json.loads(args.block_lock_json.read_text(encoding='utf8'))
    csvs=load_verified_csvs(args.raw_root,args.verification_csv)
    blocks,ctx=build_locked_split_blocks(csvs,lock=lock,split_name='validation')
    validate_replay_blocks(blocks)
    manifest=ctx['manifest_sha256']
    shortlists={};source_locks={}
    for method in METHODS:
        shortlists[method],source_locks[method]=load_gate1_shortlist(
            args.shortlist_root/f'seed{args.seed}'/method,method=method,seed=args.seed,
            expected_manifest_sha256=manifest)
    sites={1:build_primary_opencem_site(1),2:build_primary_opencem_site(2)}
    def factory(method,ledger):
        return MultiSiteReplayEvaluator(sites,ledger=ledger,method_id=method)
    outputs,audit=evaluate_equal_validation(
        seed=args.seed,shortlists=shortlists,blocks=blocks,evaluator_factory=factory,
        score_fn=score_validation_candidates,select_fn=select_one_per_method,
        indicators_fn=validation_optimizer_indicators)
    audit['stage']='E2_30_SEED_EXPLORATORY_VALIDATION_REPLAY'
    audit['protocol']='P0-E2-EQUAL-VAL-K20-30SEED-EXPLORATORY-v1'
    recorded=write_gate2_evidence(args.output_dir,outputs,audit,
        shortlist_locks=source_locks,validation_manifest_sha256=manifest,
        validation_block_ids=[str(b.block_id) for b in blocks])
    print(json.dumps({'seed':args.seed,'stage':recorded['stage'],
                      'total_block_evaluations':recorded['total_controller_block_evaluations'],
                      'output_dir':str(args.output_dir),'status':'PASS'},indent=2))

if __name__=='__main__':
    try:
        main()
    except (GateClosed,KeyError,ValueError,FileNotFoundError,RuntimeError) as exc:
        print('GATE CLOSED:',str(exc),file=sys.stderr)
        sys.exit(2)