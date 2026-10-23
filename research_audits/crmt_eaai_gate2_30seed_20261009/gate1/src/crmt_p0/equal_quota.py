"""TRAIN-only, equal-cardinality shortlisting for CRMT P0 Gate 1.

This is a prospective design utility, NOT a new optimizer and NOT evidence of
holdout superiority. Its API deliberately cannot read validation/test outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import qmc

OBJECTIVES = (
    "cap_violation_pct_total", "lfp_cycle_loss_pct",
    "ramp95_kw_per_min", "flip_per_day",
)
PARAMS = (
    "base_soft_low", "base_soft_high", "prep_power_cap_frac",
    "lookahead_gain", "reserve_enter_margin", "reserve_exit_margin",
    "hold_decay", "near_cap_forecast_buffer_frac", "near_cap_soc_boost",
)
BOUNDS = (
    (0.24, 0.42), (0.58, 0.76), (0.02, 0.20),
    (0.0, 0.08), (0.0, 0.05), (0.0, 0.04),
    (0.35, 0.85), (0.01, 0.10), (0.0, 0.08),
)
METHODS = ("CRMT", "SOBOL", "NSGAII", "MOPSO", "MODE")
PROTOCOL = "P0-E2-TRAIN-ONLY-K20-DRAFT-v1"
LEGACY_PROTOCOL = "opencem-confirmatory-prelock-v1"
LEGACY_BUDGET = 12600
LEGACY_BLOCKS = 210


class GateClosed(RuntimeError):
    """Fail-closed rather than producing an ambiguous research result."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_finite(frame: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    if any(x not in frame.columns for x in cols):
        raise GateClosed("required training columns missing: " + str(sorted(set(cols)-set(frame.columns))))
    try:
        arr = frame[list(cols)].to_numpy(dtype=float)
    except (ValueError, TypeError) as exc:
        raise GateClosed("non-numeric training fields") from exc
    if not np.isfinite(arr).all():
        raise GateClosed("training table contains non-finite data")
    return arr


def _as_ids(frame: pd.DataFrame, name: str="candidate_id") -> list[str]:
    if name not in frame:
        raise GateClosed(f"missing {name}")
    if frame[name].isna().any():
        raise GateClosed(f"null {name}")
    ids = frame[name].astype(str).tolist()
    if not ids or any(not x or x.lower()=="nan" for x in ids):
        raise GateClosed("empty candidate ID")
    if len(ids) != len(set(ids)):
        raise GateClosed("duplicate candidate ID")
    return ids


def _validate_parameter_space(frame: pd.DataFrame) -> np.ndarray:
    x = _check_finite(frame, PARAMS)
    for j, (low, high) in enumerate(BOUNDS):
        if np.any(x[:,j] < low-1e-10) or np.any(x[:,j] > high+1e-10):
            raise GateClosed(f"physical parameter {PARAMS[j]} outside frozen bound")
    if np.any(x[:,1]-x[:,0] < 0.12-1e-10):
        raise GateClosed("SOC reserve band infeasible")
    if np.any(x[:,5] > x[:,4]+1e-10):
        raise GateClosed("reserve hysteresis infeasible")
    # In this frozen OpenCEM setup hard SOC envelope is 0.10..1.0.
    if np.any(x[:,0] < 0.12-1e-10) or np.any(x[:,1] > 0.98+1e-10):
        raise GateClosed("hard SOC envelope violated")
    return x


def _candidate_key(row: np.ndarray) -> tuple[float,...]:
    # Rounding is explicit so near-identical numerical exports cannot buy a
    # second validation slot. Collisions trigger canonical selection, not filling.
    return tuple(np.round(np.asarray(row, dtype=float), 12).tolist())


def _validate_pool(frame: pd.DataFrame, *, method: str, seed: int) -> pd.DataFrame:
    forbidden = ("validation", "internal_test", "holdout", "test_", "_ood", "ood_", "external")
    if any(any(term in str(col).lower() for term in forbidden) for col in frame.columns):
        raise GateClosed("non-TRAIN fields supplied to shortlist function")
    _as_ids(frame)
    _check_finite(frame, OBJECTIVES)
    x = _validate_parameter_space(frame)
    if 'method' not in frame.columns or set(frame['method'].astype(str)) != {method}:
        raise GateClosed("wrong method in candidate pool")
    if 'seed' not in frame.columns or set(pd.to_numeric(frame['seed'], errors='coerce')) != {seed}:
        raise GateClosed("wrong seed in candidate pool")
    if 'train_block_count' not in frame.columns:
        raise GateClosed('missing TRAIN block coverage')
    cov = _check_finite(frame, ('train_block_count',))[:,0]
    if np.any(cov < 2) or np.any(cov > LEGACY_BLOCKS) or np.any(cov != np.floor(cov)):
        raise GateClosed("invalid training coverage")
    # Each unique controller may occupy at most one shortlist slot.
    work = frame.copy().reset_index(drop=True)
    work['_param_key'] = [_candidate_key(x[i]) for i in range(len(work))]
    work = work.sort_values('candidate_id', kind='mergesort')
    work = work.drop_duplicates('_param_key', keep='first').reset_index(drop=True)
    return work


def _non_dominated_levels(loss: np.ndarray) -> np.ndarray:
    n = len(loss)
    dominated_by = [set() for _ in range(n)]
    # Deterministic Pareto level (no epsilon-based inconsistent ordering).
    for i in range(n):
        for j in range(n):
            if i != j and bool(np.all(loss[j] <= loss[i]) and np.any(loss[j] < loss[i])):
                dominated_by[i].add(j)
    levels = np.full(n, -1, dtype=int)
    layer = 0
    while np.any(levels < 0):
        todo = [i for i in range(n) if levels[i]<0 and all(levels[j]>=0 for j in dominated_by[i])]
        if not todo:
            raise GateClosed('Pareto ordering failed')
        for i in todo: levels[i] = layer
        layer+=1
    return levels


def shortlist_train_only(pool: pd.DataFrame, *, method: str, seed: int, k: int=20) -> tuple[pd.DataFrame, dict]:
    """Normalize ONLY from TRAIN scores, rank Pareto front first, exactly K.

    Tie break: Pareto layer -> normalized Chebyshev -> normalized L1 ->
    lexical candidate ID. This is intentionally centralized, not diverse.
    """
    if method not in METHODS or not isinstance(seed, int) or seed < 0 or not isinstance(k,int) or k < 1:
        raise GateClosed('invalid method, seed or K')
    train = _validate_pool(pool, method=method, seed=seed)
    if len(train) < k:
        raise GateClosed(f"only {len(train)} unique physical candidates; K={k} required")
    losses = _check_finite(train, OBJECTIVES)
    minimum = losses.min(axis=0)
    maximum = losses.max(axis=0)
    span = maximum - minimum
    norm = np.zeros_like(losses, dtype=float)
    nonzero = span > 1e-12
    norm[:,nonzero] = (losses[:,nonzero]-minimum[nonzero])/span[nonzero]
    train['_pareto_level'] = _non_dominated_levels(losses)
    train['_train_linf'] = np.max(norm, axis=1)
    train['_train_l1'] = np.sum(norm, axis=1)
    ranked = train.sort_values(['_pareto_level','_train_linf','_train_l1','candidate_id'],kind='mergesort')
    shortlist = ranked.head(k).copy().reset_index(drop=True)
    shortlist.insert(0, 'rank', np.arange(1,k+1))
    if shortlist['candidate_id'].nunique() != k or shortlist['_param_key'].nunique() != k:
        raise GateClosed('shortlist lacks K unique physical candidates')
    shortlist = shortlist.drop(columns=['_param_key'])
    # No side effect and no validation data access: output can be hashed/locked
    audit = {
        'protocol': PROTOCOL,'stage':'TRAIN_SHORTLIST_ONLY',
        'claim_boundary':'DESIGN AUDIT; no validation/test/OOD used or run',
        'method':method,'seed':seed,'k':k,
        'train_candidate_rows':len(pool),'unique_train_candidates':len(train),
        'removed_duplicate_physical_parameters':len(pool)-len(train),
        'expected_validation_blocks_per_candidate':118,
        'planned_validation_controller_block_evaluations':k*118,
        'training_normalization':{obj:{'train_min':float(minimum[i]),'train_max':float(maximum[i]),'degenerate':bool(not nonzero[i])} for i,obj in enumerate(OBJECTIVES)},
        'selected_first_front':int((shortlist['_pareto_level']==0).sum()),
        'selection_rule':'Pareto level -> TRAIN normalized Linf -> L1 -> lexical ID',
    }
    return shortlist,audit


def reconstructed_crmt_candidate_params(seed: int, n: int=256) -> pd.DataFrame:
    """Reproduce current Sobol candidate-parameter pipeline, no controller needed.

    CRMT generator source: scipy.stats.qmc.Sobol(scramble=True, seed=seed),
    normalize-v1 bounds, reject infeasible hysteresis.
    """
    eng = qmc.Sobol(d=9, scramble=True, seed=seed)
    out=[]
    n_draw=0
    while len(out)<n and n_draw<n*16:
        unit=eng.random(1)[0]
        n_draw+=1
        row={p: float(low+u*(high-low)) for p,u,(low,high) in zip(PARAMS,unit,BOUNDS)}
        if row['reserve_exit_margin'] <= row['reserve_enter_margin']+1e-12:
            row['candidate_id']=f'CRMT-c{len(out)+1:04d}'
            out.append(row)
    if len(out)!=n:
        raise GateClosed('CRMT Sobol regeneration exhausted')
    return pd.DataFrame(out)


def empirical_risk(x: np.ndarray,q:float,weight:float) -> float:
    a=np.asarray(x, dtype=float)
    if a.ndim!=1 or not len(a) or not np.isfinite(a).all():
        raise GateClosed('invalid finite block risk samples')
    n=max(1,int(np.ceil((1-q)*len(a))))
    return float(a.mean()+weight*np.partition(a,len(a)-n)[len(a)-n:].mean())


def training_pool_from_files(run_dir: Path) -> tuple[pd.DataFrame,dict]:
    """Convert frozen TRAIN *candidate evaluations*, not just archive fronts.

    Hashes and ledger rows must match the TRAIN run's native lock; scripts
    fail on any corruption, mixed split, missing candidate, or budget mismatch.
    """
    run_dir=Path(run_dir)
    summary_path=run_dir/'run_summary.json'
    summary=json.loads(summary_path.read_text(encoding='utf-8'))
    if summary.get('stage')!='TRAIN_OPTIMIZATION_ONLY' or summary.get('protocol_version')!=LEGACY_PROTOCOL:
        raise GateClosed('unexpected stage/protocol; no prelock proof')
    method=str(summary.get('method'))
    seed=int(summary['seed'])
    if method not in METHODS or int(summary.get('controller_block_budget',-1))!=LEGACY_BUDGET or int(summary.get('ledger_used',-1))!=LEGACY_BUDGET:
        raise GateClosed('method or budget mismatch')
    ctx=summary.get('data_context',{})
    if ctx.get('split')!='train' or int(ctx.get('split_block_count',-1))!=LEGACY_BLOCKS or not ctx.get('manifest_sha256'):
        raise GateClosed('source is not locked TRAIN')
    frozen_risk=summary.get('risk',{})
    if not np.isclose(float(frozen_risk.get('q',0)),.90) or not np.isclose(float(frozen_risk.get('tail_weight',0)),.50) or tuple(frozen_risk.get('objectives',()))!=OBJECTIVES:
        raise GateClosed('risk functional changed')
    expected_files=summary.get('files_sha256',{})
    files=('ledger.csv','optimizer_front.csv','candidate_metrics.csv' if method=='CRMT' else 'candidate_evaluations.csv')
    for file in files:
        if file not in expected_files or sha256(run_dir/file)!=expected_files[file]:
            raise GateClosed('checksum mismatch: '+file)
    ledger=pd.read_csv(run_dir/'ledger.csv')
    if len(ledger)!=LEGACY_BUDGET or not {'ordinal','candidate_id','block_id','method_id','unit'}.issubset(ledger):
        raise GateClosed('ledger missing rows/fields')
    if ledger['ordinal'].tolist()!=list(range(1,LEGACY_BUDGET+1)):
        raise GateClosed('ledger ordinal mismatch')
    if ledger['method_id'].nunique()!=1 or str(ledger['method_id'].iloc[0])!=method or set(ledger['unit'])!={'controller_block_evaluation'}:
        raise GateClosed('ledger method/unit mismatch')
    if ledger[['candidate_id','block_id']].duplicated().any():
        raise GateClosed('duplicate candidate-block evaluation in ledger')
    # The candidate must be evaluated on listed TRAIN blocks only.
    if ledger['block_id'].nunique()>LEGACY_BLOCKS:
        raise GateClosed('excess training block IDs')
    coverage=ledger.groupby('candidate_id',sort=False).size().rename('train_block_count').reset_index()
    if len(coverage)!=int(summary.get('candidate_count',-1)):
        raise GateClosed('TRAIN candidate count vs ledger mismatch')
    front=pd.read_csv(run_dir/'optimizer_front.csv')
    if len(front)!=int(summary.get('optimizer_output_size',-1)):
        raise GateClosed('TRAIN front count mismatch')
    if method=='CRMT':
        df=pd.read_csv(run_dir/'candidate_metrics.csv')
        if len(df)!=LEGACY_BUDGET or set(df['split'].astype(str))!={'train'}:
            raise GateClosed('non-TRAIN CRMT samples or missing rows')
        if df[['candidate_id','block_id']].duplicated().any():
            raise GateClosed('CRMT candidate-block duplication')
        left=df[['candidate_id','block_id']].sort_values(['candidate_id','block_id']).reset_index(drop=True)
        right=ledger[['candidate_id','block_id']].sort_values(['candidate_id','block_id']).reset_index(drop=True)
        if not left.equals(right):
            raise GateClosed('CRMT ledger and samples disagree')
        params=reconstructed_crmt_candidate_params(seed, int(summary['candidate_count']))
        expected_id=set(params['candidate_id'])
        if set(coverage['candidate_id'])!=expected_id:
            raise GateClosed('Sobol regeneration IDs disagree with ledger')
        # Cross-check all archived parameters, to detect generator/version drift.
        indexed=params.set_index('candidate_id')
        for row in front.itertuples(index=False):
            cid=str(row.candidate_id)
            if cid not in expected_id: raise GateClosed('front references unknown candidate')
            for p in PARAMS:
                if not np.isclose(float(getattr(row,p)),float(indexed.at[cid,p]),rtol=0,atol=1e-10):
                    raise GateClosed('reconstructed parameter differs from frozen CRMT front')
        risks=[]
        for cid, group in df.groupby('candidate_id',sort=False):
            risks.append({'candidate_id':str(cid),**{o:empirical_risk(group[o].to_numpy(dtype=float),.90,.50) for o in OBJECTIVES}})
        pool=params.merge(pd.DataFrame(risks),on='candidate_id',validate='one_to_one')
    else:
        pool=pd.read_csv(run_dir/'candidate_evaluations.csv')
        _as_ids(pool)
        if set(pool['candidate_id'])!=set(coverage['candidate_id']):
            raise GateClosed('baseline candidate list differs from ledger')
        if any(x!=LEGACY_BLOCKS for x in coverage['train_block_count'].tolist()):
            raise GateClosed('baseline candidate was not evaluated on 210 TRAIN blocks')
    pool=pool.merge(coverage,on='candidate_id',validate='one_to_one')
    pool['method']=method
    pool['seed']=seed
    allowed=('method','seed','candidate_id','train_block_count',*PARAMS,*OBJECTIVES)
    pool=pool[list(allowed)].copy()
    return pool, summary


def write_train_lock(shortlist:pd.DataFrame,audit:dict,output_dir:Path,source_summary:Mapping)->dict:
    output_dir=Path(output_dir)
    if output_dir.exists():
        raise GateClosed('output directory already exists; never overwrite audit/evidence')
    if output_dir.parent.exists() is False:
        output_dir.parent.mkdir(parents=True)
    # Atomic directory setup within exclusive parent; caller must use new path.
    output_dir.mkdir(exist_ok=False)
    path=output_dir/'train_only_shortlist.csv'
    shortlist.to_csv(path,index=False,lineterminator='\n',float_format='%.17g')
    lock={**audit,'shortlist_sha256':sha256(path),
          'input_train_manifest_sha256':source_summary['data_context']['manifest_sha256'],
          'source_train_git_sha':source_summary.get('git_sha'),
          'source_train_file_hashes':source_summary['files_sha256'],
          'source_training_budget':int(source_summary['ledger_used'])}
    (output_dir/'train_only_shortlist_lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return lock
