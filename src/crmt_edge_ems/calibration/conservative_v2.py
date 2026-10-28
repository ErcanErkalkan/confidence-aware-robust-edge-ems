"""CAL-v2 conservative bounded-IID calibration, conditional on explicit assumptions.

The sample axis is independent identically distributed DAY VECTORS. Arbitrary
dependence between candidates, inverters and objectives within one day is
allowed. Dependent/nonstationary days and data-adaptive candidates/support
bounds are unsupported. Declaring these assumptions does not verify them.

Target: mean + lambda * population upper-CVaR of the equal-weight mixture of
inverter marginals for each fixed candidate/objective. The point estimator
retains pooled observations and a ceil-sized upper-tail mean; its rounding
difference from empirical fractional CVaR is explicitly covered.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from fractions import Fraction
import math
import numbers

import numpy as np

from ..contracts import ContractError, digest, finite_array, identifiers, integer, pareto_mask

METHOD_ID = "CAL-v2-DKW-BOUNDED-IID-DAY-VECTORS"
IID_ASSUMPTION = "IID_DAY_VECTORS"
FIXED_CANDIDATES = "FIXED_BEFORE_CALIBRATION"
KNOWN_SUPPORT = "PREDECLARED_KNOWN_SUPPORT"


@dataclass(frozen=True)
class ConservativeCalibration:
    method_id: str
    point_risk: np.ndarray
    lower_risk: np.ndarray
    upper_risk: np.ndarray
    upper_differences: np.ndarray
    declarations: np.ndarray
    retained: np.ndarray
    archive_overflow: bool
    support_days: int
    observations_per_candidate: int
    marginal_family_size: int
    dkw_epsilon: float
    ceil_tail_size: int
    ceil_rounding_correction: np.ndarray
    ceil_rounding_simple_upper_bound: np.ndarray
    input_sha256: str
    conditional_family_alpha: float
    assumptions_independently_verified: bool = False
    scientific_scope: str = "CONDITIONAL_BOUNDED_IID_THEOREM_ONLY_NOT_FIELD_VALIDATION"

    def to_dict(self):
        return {
            item.name: (
                getattr(self, item.name).tolist()
                if isinstance(getattr(self, item.name), np.ndarray)
                else getattr(self, item.name)
            )
            for item in fields(self)
        }


def _real(value, name):
    if (
        isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real)
        or not math.isfinite(value)
    ):
        raise ContractError(f"{name}: finite real value required")
    return float(value)


def _tail_count(q, size):
    # New CAL-v2 decimal parameter semantics; historical ceil code is unchanged.
    tail_probability = Fraction(1) - Fraction(str(q))
    mass = tail_probability * size
    count = (mass.numerator + mass.denominator - 1) // mass.denominator
    return mass, count


def empirical_fractional_cvar(values, *, q=0.9):
    """Exact empirical upper-CVaR with fractional mass at the tail boundary."""
    x = finite_array(values, "empirical CVaR values", ndim=1)
    q = _real(q, "q")
    if not 0 <= q < 1:
        raise ContractError("q must be in [0,1)")
    mass, _ = _tail_count(q, len(x))
    whole = mass.numerator // mass.denominator
    remainder = float(mass - whole)
    ordered = np.sort(x)[::-1]
    total = math.fsum(float(v) for v in ordered[:whole])
    if remainder:
        total += remainder * float(ordered[whole])
    value = total / float(mass)
    if not math.isfinite(value):
        raise ContractError("empirical CVaR overflow")
    return value


def calibrate_conservative(
    samples, *, day_ids, candidate_ids, support_lower, support_upper,
    assumption, candidate_policy, support_origin, alpha=0.05, q=0.9,
    tail_weight=0.5, capacity=10,
):
    """Return simultaneous population risk bounds under the declared contract.

    samples shape: (days, candidates, inverters, four objectives).
    Bounds must be known before these calibration observations, not fitted to
    their extrema. Candidates must be fixed without inspecting this panel.
    Support arrays must broadcast to (candidates, inverters, four objectives).
    """
    if not isinstance(assumption, str) or assumption != IID_ASSUMPTION:
        raise ContractError("unsupported sampling assumption: IID day vectors required; dependence/shift rejected")
    if not isinstance(candidate_policy, str) or candidate_policy != FIXED_CANDIDATES:
        raise ContractError("candidates must be fixed before calibration data")
    if not isinstance(support_origin, str) or support_origin != KNOWN_SUPPORT:
        raise ContractError("known support bounds must be predeclared, never estimated from this panel")
    alpha = _real(alpha, "alpha")
    q = _real(q, "q")
    weight = _real(tail_weight, "tail_weight")
    if not 0 < alpha < 0.5 or not 0 <= q < 1 or weight < 0:
        raise ContractError("valid alpha, q and nonnegative tail weight required")
    capacity = integer(capacity, "capacity", 1)
    x = finite_array(samples, "complete day-vector calibration panel", ndim=4)
    n, c, i, o = x.shape
    if n < 2 or c < 2 or i < 1 or o != 4:
        raise ContractError("days>=2 x candidates>=2 x inverters>=1 x objectives=4 required")
    days = identifiers(day_ids, "day IDs")
    candidates = identifiers(candidate_ids, "candidate IDs")
    if len(days) != n or len(candidates) != c:
        raise ContractError("day/candidate IDs must cover the complete panel")
    try:
        lower_support = np.broadcast_to(
            finite_array(support_lower, "known support lower"), (c, i, o),
        )
        upper_support = np.broadcast_to(
            finite_array(support_upper, "known support upper"), (c, i, o),
        )
    except ValueError as exc:
        raise ContractError("known support bounds cannot broadcast to candidate/inverter/objective shape") from exc
    if np.any(lower_support > upper_support):
        raise ContractError("known lower support exceeds upper support")
    if np.any(x < lower_support[None]) or np.any(x > upper_support[None]):
        raise ContractError("observation outside predeclared known support; no clipping or filtering allowed")

    # Each inverter marginal has n independent days. The pooled n*i values are
    # NOT n*i independent observations. Union-bound all c*i*o marginal DKW events.
    family_size = c*i*o
    epsilon = min(1.0, math.sqrt(math.log(2*family_size/alpha)/(2*n)))
    pooled = x.transpose(1, 0, 2, 3).reshape(c, n*i, o)
    mass, k = _tail_count(q, n*i)
    ordered = np.sort(pooled, axis=1)
    means = np.asarray([
        [math.fsum(float(v)/(n*i) for v in pooled[j, :, objective])
         for objective in range(o)] for j in range(c)
    ])
    tail_means = np.asarray([
        [math.fsum(float(v)/k for v in ordered[j, -k:, objective])
         for objective in range(o)] for j in range(c)
    ])
    point = means + weight*tail_means
    lo = lower_support.min(axis=1)
    hi = upper_support.max(axis=1)
    span = hi-lo
    # |mean(F)-mean(G)| <= span*epsilon;
    # |CVaR_q(F)-CVaR_q(G)| <= span*epsilon/(1-q).
    tail_probability = float(mass/(n*i))
    factor = min(1+weight, epsilon*(1+weight/tail_probability))
    radius = span*factor

    # If t=alpha_tail*M and k=ceil(t), the difference between fractional
    # empirical CVaR and the ceil-tail mean is at most
    # span*(k-t)*(k-1)/(t*k) <= span/t. It is zero for k=1 or integer t.
    rounding_factor = float((k-mass)*(k-1)/(mass*k))
    correction = weight*span*rounding_factor
    simple_upper = weight*span/float(mass)
    with np.errstate(over="ignore", invalid="ignore"):
        lower = np.maximum((1+weight)*lo, point-radius)
        upper = np.minimum((1+weight)*hi, point+radius+correction)
    if not all(np.isfinite(a).all() for a in (point, lower, upper, correction, simple_upper)):
        raise ContractError("finite calibration arithmetic overflow")
    # Outward rounding is numerical containment, not a new statistical assumption.
    lower = np.nextafter(lower, -np.inf)
    upper = np.nextafter(upper, np.inf)
    with np.errstate(over="ignore", invalid="ignore"):
        upper_differences = np.nextafter(upper[:, None, :] - lower[None, :, :], np.inf)
    if not all(np.isfinite(a).all() for a in (lower, upper, upper_differences)):
        raise ContractError("outward calibration interval arithmetic overflow")
    offdiag = ~np.eye(c, dtype=bool)
    declarations = (
        np.all(upper_differences <= 0, axis=2)
        & np.any(upper_differences < 0, axis=2) & offdiag
    )
    retained = ~np.any(declarations, axis=0)
    input_hash = digest({
        "samples": x.tolist(), "day_ids": list(days), "candidate_ids": list(candidates),
        "support_lower": lower_support.tolist(), "support_upper": upper_support.tolist(),
        "assumption": assumption, "candidate_policy": candidate_policy,
        "support_origin": support_origin, "alpha": alpha, "q": q,
        "tail_weight": weight, "capacity": capacity,
    })
    return ConservativeCalibration(
        METHOD_ID, point, lower, upper, upper_differences, declarations, retained,
        int(retained.sum()) > capacity, n, n*i, family_size, epsilon, k,
        correction, simple_upper, input_hash, alpha,
    )


def known_truth_metrics(result, truth_risk):
    """Known-truth synthetic diagnostics; never infer truth from a finite TEST."""
    truth = finite_array(truth_risk, "known population risk", ndim=2)
    c = len(truth)
    if truth.shape != (c, 4) or result.point_risk.shape != (c, 4):
        raise ContractError("known truth/result shape mismatch")
    delta = truth[:, None, :] - truth[None, :, :]
    offdiag = ~np.eye(c, dtype=bool)
    true_dominance = np.all(delta <= 0, axis=2) & np.any(delta < 0, axis=2) & offdiag
    front = pareto_mask(truth)
    return {
        "family_risk_undercoverage": bool(np.any(
            (truth < result.lower_risk) | (truth > result.upper_risk)
        )),
        "family_difference_undercoverage": bool(np.any(
            (delta > result.upper_differences)[offdiag]
        )),
        "false_dominance_declaration": bool(np.any(result.declarations & ~true_dominance)),
        "false_pareto_removal": bool(np.any(front & ~result.retained)),
        "true_pareto_retention": float(np.sum(front & result.retained)/np.sum(front)),
        "archive_overflow": result.archive_overflow,
        "archive_size": int(result.retained.sum()),
        "true_pareto_size": int(front.sum()),
        "selection_fidelity": None,
        "selection_fidelity_reason": "No K-shortlist policy; overflow is retained and reported",
    }
