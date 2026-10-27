"""R19 *design-time geometry only*. No AUDIT/TEST data may be inspected here.

Exact, sharp upper bound on paired MissRate difference when two shortlists
contain exactly K distinct candidates from the same N-candidate pool.

Not a change to the original R19 preregistered draft or a performance claim.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import math
from .contracts import ContractError, integer

@dataclass(frozen=True)
class ShortlistGeometry:
    pool_size: int
    shortlist_size: int
    pareto_size: int
    practical_effect_threshold: float
    min_true_pareto_hits: int
    max_true_pareto_hits: int
    sharp_max_abs_delta_miss: float
    effect_geometrically_possible: bool
    numerical_step_per_hit: float
    status: str='PLANNING_SENSITIVITY_ONLY_NOT_CONFIRMATORY'

    def to_dict(self): return asdict(self)


def geometry(pareto_size: int, *, pool_size: int=256, shortlist_size: int=10,
             practical_effect_threshold: float=0.05)->ShortlistGeometry:
    n=integer(pool_size,'pool_size',1)
    k=integer(shortlist_size,'shortlist_size',1)
    p=integer(pareto_size,'pareto_size',1)
    if k>n or p>n: raise ContractError('pool must contain shortlist and Pareto set')
    e=practical_effect_threshold
    if isinstance(e,bool) or not isinstance(e,(int,float)) or not math.isfinite(e) or not 0<e<=1:
        raise ContractError('finite practical effect in (0,1] required')
    # Inclusion/exclusion in a fixed N-element universe.
    low=max(0,k-(n-p))
    high=min(k,p)
    sharp=(high-low)/p
    return ShortlistGeometry(n,k,p,float(e),low,high,sharp,
         sharp+1e-14 >= e,1/p)


def design_grid(*, pool_size=256, shortlist_size=10, practical_effect_threshold=0.05):
    n=integer(pool_size,'pool_size',1)
    return [geometry(p,pool_size=n,shortlist_size=shortlist_size,
                     practical_effect_threshold=practical_effect_threshold).to_dict()
            for p in range(1,n+1)]