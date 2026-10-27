"""R19 empirical shortlist fidelity, strict separately versioned implementation.

No data loading from AUDIT is performed during selection. This module never
grants experiment authorization. Historical R19 draft remains locked=false.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .contracts import ContractError, identifiers, integer, finite_array, strict_risk, pareto_mask, digest

PROTOCOL_ID='CRMT-R19-STRICT-v1-DRAFT'

@dataclass(frozen=True)
class PrimaryDesign:
    c: int=1
    a: int=1
    b: int=10
    k: int=10
    candidate_count: int=256
    discovery_events: int=12600
    backfill: bool=False
    locked: bool=False

    def __post_init__(self):
        for name in ('c','a','b','k','candidate_count','discovery_events'): integer(getattr(self,name),name,1)
        if (self.c,self.a,self.b,self.k,self.candidate_count,self.discovery_events)!=(1,1,10,10,256,12600) or self.backfill is not False or self.locked is not False:
            raise ContractError('R19 fixed C1/A1 B=K10 256/12600 no-backfill unlocked draft required')

def paired_ledger(ledger0, ledger1, candidate_ids, discovery_blocks, *, expected=12600):
    ids=set(identifiers(candidate_ids,'candidates')); blocks=set(identifiers(discovery_blocks,'discovery blocks'))
    integer(expected,'expected events',1)
    def parse(raw):
        rows=[]
        for row in raw:
            if not isinstance(row,(tuple,list)) or len(row)!=2 or row[0] not in ids or row[1] not in blocks:
                raise ContractError('ledger has invalid candidate/block event')
            rows.append(tuple(row))
        if len(rows)!=expected or len(set(rows))!=len(rows): raise ContractError('ledger count/duplicate violation')
        if {c for c,_ in rows}!=ids: raise ContractError('ledger does not cover candidate pool')
        return frozenset(rows)
    l0,l1=parse(ledger0),parse(ledger1)
    if l0!=l1: raise ContractError('F0/F1 discovery ledgers differ')
    return l0

def select_shortlists(candidate_ids, discovery_observations, ledger0, ledger1, archives, *, design=PrimaryDesign()):
    ids=identifiers(candidate_ids,'candidates')
    if len(ids)!=design.candidate_count or set(discovery_observations)!=set(ids) or set(archives)!={'F0','F1'}:
        raise ContractError('R19 pool/observation/archive schema mismatch')
    blocks=sorted({b for rows in discovery_observations.values() for b in rows})
    events=paired_ledger(ledger0,ledger1,ids,blocks,expected=design.discovery_events)
    scores=[]
    for cid in ids:
        rows=discovery_observations[cid]
        if set(rows)!={b for c,b in events if c==cid}: raise ContractError('observations differ from executed ledger')
        scores.append(strict_risk([rows[b] for b in sorted(rows)]))
    matrix=np.stack(scores); lo=matrix.min(axis=0); span=matrix.max(axis=0)-lo
    norm=np.divide(matrix-lo,span,out=np.zeros_like(matrix),where=span>0)
    if not np.isfinite(norm).all(): raise ContractError('normalization overflow')
    order=sorted(range(len(ids)),key=lambda i:(float(norm[i].max()),float(norm[i].sum()),ids[i]))
    picks={}; counts={}
    for arm in ('F0','F1'):
        natural=set(identifiers(archives[arm],arm+' natural archive',allow_empty=True))
        if not natural<=set(ids): raise ContractError('archive contains unknown candidate')
        counts[arm]=len(natural)
        if len(natural)<design.b:
            return {'schema_version':1,'protocol_id':PROTOCOL_ID,'status':'BLOCKED_CAPACITY',
                    'arm':arm,'natural_count':len(natural),'required':design.b,'backfill':False}
        picks[arm]=[ids[i] for i in order if ids[i] in natural][:design.b]
    payload={'schema_version':1,'protocol_id':PROTOCOL_ID,'status':'EXPLORATORY_SELECTION_ONLY',
        'candidate_ids':list(ids),'selected':picks,'natural_counts':counts,'B':10,'backfill':False,
        'discovery_ledger_sha256':digest(sorted(events)),'discovery_inputs_sha256':digest(discovery_observations),
        'discovery_block_ids':blocks,'normalization_min':lo.tolist(),'normalization_span':span.tolist(),
        'locked':False}
    payload['selection_sha256']=digest(payload)
    return payload

def audit_fidelity(selection, audit_observations):
    """Exploratory math only. Real AUDIT execution requires the gate engine."""
    raw=dict(selection); seal=raw.pop('selection_sha256',None)
    if seal!=digest(raw) or raw.get('status')!='EXPLORATORY_SELECTION_ONLY' or raw.get('protocol_id')!=PROTOCOL_ID:
        raise ContractError('invalid selection lock')
    ids=identifiers(selection['candidate_ids'],'candidates')
    if set(audit_observations)!=set(ids): raise ContractError('AUDIT must evaluate all candidates')
    blocks=identifiers(sorted(audit_observations[ids[0]]),'AUDIT blocks')
    if len(blocks)<8 or set(blocks)&set(selection['discovery_block_ids']): raise ContractError('AUDIT insufficient/overlapping discovery blocks')
    scores=[]
    for cid in ids:
        if set(audit_observations[cid])!=set(blocks): raise ContractError('unequal AUDIT support')
        scores.append(strict_risk([audit_observations[cid][b] for b in blocks]))
    reference={cid for cid,keep in zip(ids,pareto_mask(scores)) if keep}
    miss={arm:len(reference-set(picks))/len(reference) for arm,picks in selection['selected'].items()}
    return {'schema_version':1,'status':'EXPLORATORY_NOT_CONFIRMATORY','selection_sha256':seal,
        'reference_ids':sorted(reference),'audit_sha256':digest(audit_observations),
        'miss_rate':miss,'delta_miss':miss['F1']-miss['F0'],'audit_events':len(ids)*len(blocks)}

def aggregate_seed_differences(results, planned_seeds):
    seeds=tuple(integer(s,'seed') for s in planned_seeds)
    if len(set(seeds))!=len(seeds) or not seeds: raise ContractError('unique planned seeds required')
    if len(results)!=len(seeds) or {r['seed'] for r in results}!=set(seeds): raise ContractError('failed/missing/duplicate seeds cannot be omitted')
    if any(r.get('status')!='EXPLORATORY_NOT_CONFIRMATORY' for r in results): raise ContractError('incomplete seed result')
    d=finite_array([r['delta_miss'] for r in sorted(results,key=lambda r:r['seed'])],'seed differences',ndim=1)
    if np.any(np.abs(d)>1): raise ContractError('MissRate differences must be in [-1,1]')
    return {'status':'EXPLORATORY_NOT_CONFIRMATORY','n_seeds':len(seeds),'mean_delta_miss':float(d.mean()),'deltas':d.tolist()}
