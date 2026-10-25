"""R25 command line: never creates a real external preregistration on its own."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from r25_protocol_gate import (Blocked,local_gate_report,create_split_reservation,lock_receipt_envelope,verify_external_signature)

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write_new(p,data):
    dest=Path(p);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')

def main():
    p=argparse.ArgumentParser(description='CRMT R25 local evidence gates; external attestation NOT automatic.')
    p.add_argument('command',choices=('status','reserve','request-receipt','verify-receipt'))
    p.add_argument('--input',help='split reservation request, or signed receipt JSON')
    p.add_argument('--plan',help='locally reserved split plan')
    p.add_argument('--lock',help='R19 selection_lock JSON; not a synthetic fixture')
    p.add_argument('--envelope',help='R25 signed request envelope')
    p.add_argument('--pinned-public-key',default=None,help='independently approved Ed25519 public key hex; NO default')
    p.add_argument('--out',required=True,help='new output file; existing files never overwritten')
    args=p.parse_args()
    try:
        if args.command=='status':result=local_gate_report()
        elif args.command=='reserve':
            if not args.input:raise Blocked('MISSING_INPUT')
            result=create_split_reservation(read(args.input))
        elif args.command=='request-receipt':
            if not args.lock or not args.plan:raise Blocked('MISSING_PLAN_OR_LOCK')
            result=lock_receipt_envelope(read(args.lock),read(args.plan))
        else:
            if not args.envelope:raise Blocked('MISSING_ENVELOPE')
            result=verify_external_signature(read(args.envelope),read(args.input) if args.input else {},args.pinned_public_key)
        write_new(args.out,result)
        print(result.get('status',result.get('schema',result.get('stage'))))
    except (Blocked,KeyError,ValueError) as e:raise SystemExit('R25_BLOCKED: '+str(e)) from e

if __name__=='__main__':main()
