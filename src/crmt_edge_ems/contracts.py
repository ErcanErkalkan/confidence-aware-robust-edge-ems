"""CRMT remediation v1 contracts; legacy F0/F1 modules are unchanged."""
from __future__ import annotations
import hashlib
import json
import math
import numbers
from pathlib import Path
import numpy as np

IMPLEMENTATION_ID = 'CRMT-REMEDIATION-v1'
OBJECTIVES = ('cap_violation_pct_total', 'lfp_cycle_loss_pct', 'ramp95_kw_per_min', 'flip_per_day')

class ContractError(ValueError):
    """Invalid scientific input; callers must stop rather than omit records."""

def integer(value, name, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral) or value < minimum:
        raise ContractError(f'{name}: integer >= {minimum} required')
    return int(value)

def finite_array(value, name, *, ndim=None):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'iuf' or raw.dtype.kind == 'b':
        raise ContractError(f'{name}: numeric values required')
    x = np.asarray(value, dtype=float)
    if not x.size or (ndim is not None and x.ndim != ndim) or not np.isfinite(x).all():
        raise ContractError(f'{name}: nonempty finite array of dimension {ndim} required')
    return x

def identifiers(values, name, *, allow_empty=False):
    ids = tuple(values)
    if (not ids and not allow_empty) or any(not isinstance(s,str) or not s or s.strip()!=s for s in ids) or len(set(ids))!=len(ids):
        raise ContractError(f'{name}: unique nonblank string IDs required')
    return ids

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def strict_risk(samples, *, q=0.90, tail_weight=0.5, min_blocks=2):
    """Historical mean + weight * ceil(top-tail) mean, with no silent deletion.

    Axis -2 is block; the final axis is objective. Supports bootstrap batches.
    min_blocks is a technical minimum, not proof of sufficient tail support.
    """
    x=finite_array(samples,'risk samples')
    integer(min_blocks,'min_blocks',2)
    if x.ndim<2 or x.shape[-2]<min_blocks or x.shape[-1]!=4:
        raise ContractError('risk: at least min_blocks x four objectives required')
    if not isinstance(q,numbers.Real) or isinstance(q,bool) or not math.isfinite(q) or not 0<=q<1:
        raise ContractError('q must be finite in [0,1)')
    if not isinstance(tail_weight,numbers.Real) or isinstance(tail_weight,bool) or not math.isfinite(tail_weight) or tail_weight<0:
        raise ContractError('tail_weight must be finite and nonnegative')
    n=x.shape[-2]; k=max(1,math.ceil((1-q)*n))
    result=x.mean(axis=-2)+tail_weight*np.partition(x,n-k,axis=-2)[...,n-k:,:].mean(axis=-2)
    return finite_array(result,'risk result')

def pareto_mask(scores):
    x=finite_array(scores,'Pareto scores',ndim=2)
    if x.shape[1]!=4: raise ContractError('four minimization objectives required')
    # Exact weak/strict comparisons: equal vectors retain both candidate IDs.
    return np.asarray([not np.any(np.all(x<=r,axis=1)&np.any(x<r,axis=1)) for r in x])