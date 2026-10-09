"""Development-only, fail-closed E2 equal-quota validation orchestration.

Consumes SHA-locked Gate1 TRAIN-only candidate lists. Uses the original project's
MultiSiteReplayEvaluator and selection/indicator implementations via injected
callables. No TEST/OOD input API exists. Does not overwrite original evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from .equal_quota import (
    OBJECTIVES, PARAMS, METHODS, PROTOCOL as GATE1_PROTOCOL,
    GateClosed, sha256, _validate_parameter_space,
)

GATE2_PROTOCOL = 'P0-E2-EQUAL-VAL-K20-ENGINEERING-PILOT-v1'
K = 20
N_VAL_BLOCKS = 118
VALIDATION_BUDGET = K * N_VAL_BLOCKS
Q = .90
TAIL_WEIGHT = .50


class StrictLedger:
    """Exact controller-block ledger, rejects repeats and overbudget writes."""
    UNIT = 'controller_block_evaluation'

    def __init__(self, max_evaluations: int):
        if max_evaluations < 1:
            raise GateClosed('nonpositive budget')
        self.max_evaluations = int(max_evaluations)
        self.events: list[dict] = []
        self.seen: set[tuple[str, str]] = set()

    @property
    def used(self) -> int:
        return len(self.events)

    def reserve(self, method_id: str, candidate_id: str, block_ids: Sequence[str]):
        blocks = tuple(str(x) for x in block_ids)
        if len(blocks) != len(set(blocks)):
            raise GateClosed('duplicate block within reservation')
        if self.used + len(blocks) > self.max_evaluations:
            raise GateClosed('over budget')
        keys = [(str(candidate_id), b) for b in blocks]
        if any(key in self.seen for key in keys):
            raise GateClosed('duplicate candidate:block charged twice')
        # All checks pass before any budget is debited.
        start = self.used
        self.seen.update(keys)
        records = []
        for j, b in enumerate(blocks, start=1):
            record = {'ordinal': start+j, 'method_id': str(method_id),
                      'candidate_id': str(candidate_id), 'block_id': b,
                      'unit': self.UNIT}
            records.append(record)
        self.events.extend(records)
        return tuple(records)

    def assert_exact(self):
        if self.used != self.max_evaluations:
            raise GateClosed(f'ledger incomplete: {self.used} != {self.max_evaluations}')

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.events, columns=(
            'ordinal','method_id','candidate_id','block_id','unit'))


def _validate_shortlist(frame: pd.DataFrame, lock: Mapping, *, method: str, seed: int,
                        expected_manifest_sha256: str) -> pd.DataFrame:
    if lock.get('protocol') != GATE1_PROTOCOL or lock.get('stage') != 'TRAIN_SHORTLIST_ONLY':
        raise GateClosed('shortlist is not TRAIN-ONLY Gate1 artifact')
    if lock.get('method') != method or int(lock.get('seed', -1)) != int(seed):
        raise GateClosed('Gate1 identity mismatch')
    if lock.get('input_train_manifest_sha256') != expected_manifest_sha256:
        raise GateClosed('TRAIN and VALIDATION do not share the frozen manifest')
    if int(lock.get('k', -1)) != K or int(lock.get('source_training_budget', -1)) != 12600:
        raise GateClosed('shortlist K or TRAIN budget mismatch')
    if int(lock.get('planned_validation_controller_block_evaluations', -1)) != VALIDATION_BUDGET:
        raise GateClosed('shortlist VAL budget mismatch')
    if len(frame) != K:
        raise GateClosed('shortlist cardinality is not exactly 20')
    required = {'rank','candidate_id','method','seed',*PARAMS}
    if not required.issubset(frame.columns):
        raise GateClosed('missing critical shortlist fields')
    forbidden = ('validation', 'internal_test', 'holdout', 'test_', '_ood', 'ood_', 'external')
    if any(any(t in str(c).lower() for t in forbidden) for c in frame.columns):
        raise GateClosed('non-TRAIN data in shortlist')
    if list(pd.to_numeric(frame['rank'], errors='coerce')) != list(range(1, K+1)):
        raise GateClosed('shortlist ranks invalid')
    if set(frame['method'].astype(str)) != {method} or set(pd.to_numeric(frame['seed'], errors='coerce')) != {seed}:
        raise GateClosed('shortlist data identity mismatch')
    if frame['candidate_id'].isna().any() or frame['candidate_id'].astype(str).duplicated().any():
        raise GateClosed('null/repeated candidate ID')
    if frame['candidate_id'].astype(str).str.strip().eq('').any():
        raise GateClosed('blank candidate ID')
    params = _validate_parameter_space(frame)
    rounded = [tuple(np.round(row, 12)) for row in params]
    if len(set(rounded)) != K:
        raise GateClosed('non-unique controller parameters in shortlist')
    return frame.copy()


def load_gate1_shortlist(directory: Path, *, method: str, seed: int,
                         expected_manifest_sha256: str) -> tuple[pd.DataFrame, dict]:
    p = Path(directory)
    lock_file = p / 'train_only_shortlist_lock.json'
    shortlist_file = p / 'train_only_shortlist.csv'
    if not lock_file.is_file() or not shortlist_file.is_file():
        raise GateClosed('shortlist/lock missing')
    lock = json.loads(lock_file.read_text(encoding='utf8'))
    if lock.get('shortlist_sha256') != sha256(shortlist_file):
        raise GateClosed('shortlist SHA-256 mismatch')
    shortlist = pd.read_csv(shortlist_file)
    return _validate_shortlist(shortlist, lock, method=method, seed=seed,
                               expected_manifest_sha256=expected_manifest_sha256), lock


def validate_replay_blocks(blocks: Sequence, *, expected_count: int=N_VAL_BLOCKS):
    if len(blocks) != expected_count:
        raise GateClosed(f'VAL block count mismatch: {len(blocks)} != {expected_count}')
    ids = [str(b.block_id) for b in blocks]
    if len(set(ids)) != expected_count or any(not b for b in ids):
        raise GateClosed('duplicated/blank VAL block ID')
    if any(str(b.split) != 'validation' for b in blocks):
        raise GateClosed('non-VAL block supplied')
    if any(b.site_id is None for b in blocks):
        raise GateClosed('site ID missing')
    return ids


def _risk_score(values: Sequence[float]) -> float:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) != N_VAL_BLOCKS or not np.isfinite(x).all():
        raise GateClosed('invalid risk aggregation input')
    tail_count = max(1, int(np.ceil((1-Q)*len(x))))
    tail = np.partition(x,len(x)-tail_count)[len(x)-tail_count:]
    return float(x.mean() + TAIL_WEIGHT*tail.mean())


def evaluate_equal_validation(
    *, seed: int, shortlists: Mapping[str, pd.DataFrame], blocks: Sequence,
    evaluator_factory: Callable[[str, StrictLedger], object],
    score_fn: Callable, select_fn: Callable, indicators_fn: Callable,
) -> tuple[dict[str,pd.DataFrame],dict]:
    """Evaluate all five shortlists on exactly the same 118 VALIDATION blocks.

    score_fn/select_fn/indicators_fn MUST be original GitHub canonical funcs.
    This function does not read or accept TEST data or write any files.
    """
    block_ids = validate_replay_blocks(blocks)
    if set(shortlists) != set(METHODS):
        raise GateClosed('must supply all five methods; incomplete comparison prohibited')
    score_rows=[]
    all_metrics=[]
    all_ledgers=[]
    for method in METHODS:
        frame=shortlists[method]
        if len(frame)!=K:
            raise GateClosed('method shortlist not exactly K')
        ledger=StrictLedger(VALIDATION_BUDGET)
        evaluator=evaluator_factory(method,ledger)
        for row in frame.itertuples(index=False):
            cid=str(row.candidate_id)
            params={name:float(getattr(row,name)) for name in PARAMS}
            measurements=evaluator.evaluate(params,blocks,candidate_id=cid)
            if not isinstance(measurements,pd.DataFrame):
                raise GateClosed('evaluator did not return a DataFrame')
            if 'block_id' not in measurements or 'split' not in measurements:
                raise GateClosed('evaluator block provenance missing')
            if len(measurements)!=N_VAL_BLOCKS or list(measurements['block_id'].astype(str))!=block_ids:
                raise GateClosed('candidate missing/out of order/foreign VAL blocks')
            if set(measurements['split'].astype(str))!={'validation'}:
                raise GateClosed('evaluator returned non-VAL records')
            if 'site_id' not in measurements or measurements['site_id'].isna().any():
                raise GateClosed('site provenance missing')
            if not np.isfinite(measurements[list(OBJECTIVES)].to_numpy(dtype=float)).all():
                raise GateClosed('non-finite operational objective')
            score_rows.append({'method':method,'seed':seed,'candidate_id':cid,**params,
                               **{name:_risk_score(measurements[name]) for name in OBJECTIVES}})
            frame_metrics=measurements.copy()
            frame_metrics.insert(0,'candidate_id',cid)
            frame_metrics.insert(0,'method',method)
            frame_metrics.insert(0,'seed',seed)
            all_metrics.append(frame_metrics)
        ledger.assert_exact()
        ledger_frame=ledger.to_frame()
        if ledger_frame['ordinal'].tolist() != list(range(1,VALIDATION_BUDGET+1)):
            raise GateClosed('non-contiguous ledger ordinal')
        if set(ledger_frame['method_id']) != {method}:
            raise GateClosed('ledger method identity corrupted')
        if ledger_frame[['candidate_id','block_id']].duplicated().any():
            raise GateClosed('duplicate candidate-block ledger')
        if set(ledger_frame['block_id']) != set(block_ids):
            raise GateClosed('ledger block coverage mismatch')
        ledger_frame.insert(0,'seed',seed)
        all_ledgers.append(ledger_frame)
    raw=pd.DataFrame(score_rows)
    if len(raw)!=len(METHODS)*K or raw[['method','candidate_id']].duplicated().any():
        raise GateClosed('VAL scored candidate count mismatch')
    scored,refs=score_fn(raw,objectives=OBJECTIVES)
    selected=select_fn(scored)
    if len(selected)!=len(METHODS) or set(selected['method'])!=set(METHODS):
        raise GateClosed('selection not exactly one controller per method')
    indicators,indicator_refs=indicators_fn(scored,objectives=OBJECTIVES)
    if set(indicators['method'])!=set(METHODS):
        raise GateClosed('indicators missing methods')
    outputs={'raw_scores':raw, 'scored_candidates':scored,
             'validation_block_metrics':pd.concat(all_metrics,ignore_index=True),
             'validation_ledger':pd.concat(all_ledgers,ignore_index=True),
             'selected_candidates':selected,'validation_optimizer_indicators':indicators}
    audit={'stage':'ENGINEERING_PILOT_VALIDATION_ONLY',
           'protocol':GATE2_PROTOCOL,'seed':seed,
           'claim_boundary':'Historic VAL engineering pilot; NOT independent confirmatory evidence or TEST',
           'methods':list(METHODS),'k_per_method':K,
           'val_blocks_per_candidate':N_VAL_BLOCKS,
           'controller_block_budget_per_method':VALIDATION_BUDGET,
           'total_controller_block_evaluations':len(METHODS)*VALIDATION_BUDGET,
           'risk_q':Q,'risk_tail_weight':TAIL_WEIGHT,
           'validation_normalization_reference':refs,
           'indicator_normalization_reference':indicator_refs}
    return outputs,audit


def write_gate2_evidence(output_dir:Path, outputs:Mapping[str,pd.DataFrame], audit:dict,
                         *,shortlist_locks:Mapping[str,dict],validation_manifest_sha256:str,
                         validation_block_ids:Sequence[str]):
    """Write only after every method passed. New directory only, no overwrite."""
    output_dir=Path(output_dir)
    if output_dir.exists():
        raise GateClosed('output already exists; immutable evidence')
    if not validation_manifest_sha256 or not shortlist_locks:
        raise GateClosed('source provenance missing')
    if set(shortlist_locks)!=set(METHODS):
        raise GateClosed('source shortlist lock incomplete')
    if len(validation_block_ids)!=N_VAL_BLOCKS or len(set(validation_block_ids))!=N_VAL_BLOCKS:
        raise GateClosed('output block provenance incomplete')
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(prefix='.gate2_staging_',dir=output_dir.parent) as staging:
        staging=Path(staging)
        hashes={}
        for name,frame in outputs.items():
            path=staging/(name+'.csv')
            frame.to_csv(path,index=False,lineterminator='\n',float_format='%.17g')
            hashes[path.name]=sha256(path)
        report={**audit,
                'training_shortlist_locks':{m:{'shortlist_sha256':shortlist_locks[m]['shortlist_sha256'],
                                               'source_train_git_sha':shortlist_locks[m].get('source_train_git_sha')}
                                            for m in METHODS},
                'validation_canonical_manifest_sha256':validation_manifest_sha256,
                'validation_block_ids_sha256':hashlib.sha256(
                    ('\n'.join(validation_block_ids)+'\n').encode('utf8')).hexdigest(),
                'files_sha256':hashes}
        (staging/'gate2_lock.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
        staging.rename(output_dir)
    return report
