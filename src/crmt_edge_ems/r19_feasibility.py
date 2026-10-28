"""R19 design-time geometry only; this module never inspects AUDIT outcomes.

Two exact-K shortlists from the same N-candidate pool have a sharp paired
MissRate bound. Geometric feasibility is necessary, not sufficient for power,
method performance, or approval of a prospective protocol.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
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
    status: str = "PLANNING_SENSITIVITY_ONLY_NOT_CONFIRMATORY"

    def to_dict(self):
        return asdict(self)


def geometry(
    pareto_size: int,
    *,
    pool_size: int = 256,
    shortlist_size: int = 10,
    practical_effect_threshold: float = 0.05,
) -> ShortlistGeometry:
    """Return the exact hit-count bound, with a decimal threshold comparison.

    The supplied finite float threshold is interpreted through its shortest
    round-trippable decimal representation: 0.05 denotes exactly 1/20. This
    avoids a floating tolerance that could declare an impossible positive
    effect feasible when the sharp bound is zero.
    """
    n = integer(pool_size, "pool_size", 1)
    k = integer(shortlist_size, "shortlist_size", 1)
    p = integer(pareto_size, "pareto_size", 1)
    if k > n or p > n:
        raise ContractError("pool must contain shortlist and Pareto set")
    e = practical_effect_threshold
    if (
        isinstance(e, bool)
        or not isinstance(e, (int, float))
        or not math.isfinite(e)
        or not 0 < e <= 1
    ):
        raise ContractError("finite practical effect in (0,1] required")
    low = max(0, k - (n - p))
    high = min(k, p)
    exact_bound = Fraction(high - low, p)
    exact_threshold = Fraction(str(float(e)))
    return ShortlistGeometry(
        n, k, p, float(e), low, high, float(exact_bound),
        exact_bound >= exact_threshold, 1 / p,
    )


def design_grid(
    *, pool_size=256, shortlist_size=10, practical_effect_threshold=0.05,
):
    n = integer(pool_size, "pool_size", 1)
    return [
        geometry(
            p, pool_size=n, shortlist_size=shortlist_size,
            practical_effect_threshold=practical_effect_threshold,
        ).to_dict()
        for p in range(1, n + 1)
    ]
