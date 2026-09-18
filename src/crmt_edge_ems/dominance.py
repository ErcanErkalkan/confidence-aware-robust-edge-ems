from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .risk import RiskConfig, risk_calibrated_score


@dataclass(frozen=True)
class DominanceDecision:
    relation: int  # -1: A confidently dominates B; +1: B dominates A; 0: unresolved/incomparable
    upper_diff_a_minus_b: np.ndarray
    upper_diff_b_minus_a: np.ndarray
    alpha_familywise: float


def pareto_dominates(a: np.ndarray, b: np.ndarray, *, atol: float = 1e-12) -> bool:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return bool(np.all(a <= b + atol) and np.any(a < b - atol))


def _paired_bootstrap_upper_mean(diff: np.ndarray, *, alpha: float, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    if diff.ndim != 2:
        raise ValueError("diff must be [blocks, objectives]")
    n, m = diff.shape
    if n < 2:
        return np.full(m, np.inf, dtype=float)
    per_obj_alpha = alpha / max(m, 1)
    idx = rng.integers(0, n, size=(n_boot, n))
    means = diff[idx].mean(axis=1)
    return np.quantile(means, 1.0 - per_obj_alpha, axis=0)


def confidence_dominance(
    a_samples: np.ndarray,
    b_samples: np.ndarray,
    *,
    alpha: float = 0.05,
    n_boot: int = 2000,
    epsilon: float = 0.0,
    seed: int = 0,
) -> DominanceDecision:
    """Legacy mean-based paired confidence dominance.

    Kept as an ablation/reference mechanism. The proposed CRMT archive uses
    :func:`confidence_risk_dominance`, which bootstraps the same risk-calibrated
    functional used by the optimizer objectives.
    """
    a = np.asarray(a_samples, dtype=float)
    b = np.asarray(b_samples, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Paired confidence dominance requires the same block/objective shape")
    if a.ndim != 2:
        raise ValueError("Samples must be [blocks, objectives]")
    if not (0.0 < alpha < 0.5):
        raise ValueError("alpha must be in (0, 0.5)")
    if n_boot < 200:
        raise ValueError("n_boot must be >= 200")

    finite = np.all(np.isfinite(a), axis=1) & np.all(np.isfinite(b), axis=1)
    a = a[finite]
    b = b[finite]
    if a.shape[0] < 2:
        inf = np.full(a.shape[1] if a.ndim == 2 else 0, np.inf)
        return DominanceDecision(0, inf, inf, alpha)

    rng_ab = np.random.default_rng(seed)
    rng_ba = np.random.default_rng(seed + 1)
    upper_ab = _paired_bootstrap_upper_mean(a - b, alpha=alpha, n_boot=n_boot, rng=rng_ab)
    upper_ba = _paired_bootstrap_upper_mean(b - a, alpha=alpha, n_boot=n_boot, rng=rng_ba)

    mean_ab = np.mean(a - b, axis=0)
    mean_ba = -mean_ab
    a_no_worse = bool(np.all(upper_ab <= epsilon))
    b_no_worse = bool(np.all(upper_ba <= epsilon))
    a_strict = bool(np.any(mean_ab < -epsilon))
    b_strict = bool(np.any(mean_ba < -epsilon))
    relation = -1 if (a_no_worse and a_strict) else (1 if (b_no_worse and b_strict) else 0)
    return DominanceDecision(relation, upper_ab, upper_ba, alpha)


def _bootstrap_risk_differences(
    a: np.ndarray,
    b: np.ndarray,
    *,
    risk: RiskConfig,
    n_boot: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Paired bootstrap of CRMT risk-functional differences A - B.

    Each resample uses the same block indices for A and B, preserving the paired
    experimental design. For every objective, the statistic is exactly the
    mean + tail_weight * empirical-CVaR functional used by CRMT.
    """
    n, m = a.shape
    idx = rng.integers(0, n, size=(n_boot, n))
    out = np.empty((n_boot, m), dtype=float)
    for r in range(n_boot):
        ai = a[idx[r]]
        bi = b[idx[r]]
        for j in range(m):
            out[r, j] = risk_calibrated_score(ai[:, j], q=risk.q, tail_weight=risk.tail_weight) - risk_calibrated_score(
                bi[:, j], q=risk.q, tail_weight=risk.tail_weight
            )
    return out


def confidence_risk_dominance(
    a_samples: np.ndarray,
    b_samples: np.ndarray,
    *,
    risk: RiskConfig = RiskConfig(),
    alpha: float = 0.05,
    n_boot: int = 2000,
    epsilon: float = 0.0,
    seed: int = 0,
) -> DominanceDecision:
    """Confidence dominance for the *risk-calibrated* CRMT objectives.

    A confidently dominates B only when simultaneous one-sided bootstrap upper
    bounds show that A is no worse than B on every risk-calibrated objective,
    while the observed risk vector shows a strict improvement on at least one.
    Family-wise error is controlled with Bonferroni across objectives.
    """
    a = np.asarray(a_samples, dtype=float)
    b = np.asarray(b_samples, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Paired risk dominance requires the same block/objective shape")
    if a.ndim != 2:
        raise ValueError("Samples must be [blocks, objectives]")
    if a.shape[1] != len(risk.objectives):
        raise ValueError("Sample objective width must match RiskConfig.objectives")
    if not (0.0 < alpha < 0.5):
        raise ValueError("alpha must be in (0, 0.5)")
    if n_boot < 200:
        raise ValueError("n_boot must be >= 200")

    finite = np.all(np.isfinite(a), axis=1) & np.all(np.isfinite(b), axis=1)
    a = a[finite]
    b = b[finite]
    if a.shape[0] < 2:
        inf = np.full(a.shape[1] if a.ndim == 2 else 0, np.inf)
        return DominanceDecision(0, inf, inf, alpha)

    rng_ab = np.random.default_rng(seed)
    rng_ba = np.random.default_rng(seed + 1)
    boot_ab = _bootstrap_risk_differences(a, b, risk=risk, n_boot=n_boot, rng=rng_ab)
    boot_ba = _bootstrap_risk_differences(b, a, risk=risk, n_boot=n_boot, rng=rng_ba)
    per_obj_alpha = alpha / max(a.shape[1], 1)
    upper_ab = np.quantile(boot_ab, 1.0 - per_obj_alpha, axis=0)
    upper_ba = np.quantile(boot_ba, 1.0 - per_obj_alpha, axis=0)

    observed_a = np.asarray([
        risk_calibrated_score(a[:, j], q=risk.q, tail_weight=risk.tail_weight) for j in range(a.shape[1])
    ])
    observed_b = np.asarray([
        risk_calibrated_score(b[:, j], q=risk.q, tail_weight=risk.tail_weight) for j in range(b.shape[1])
    ])
    diff = observed_a - observed_b

    a_no_worse = bool(np.all(upper_ab <= epsilon))
    b_no_worse = bool(np.all(upper_ba <= epsilon))
    a_strict = bool(np.any(diff < -epsilon))
    b_strict = bool(np.any(diff > epsilon))
    relation = -1 if (a_no_worse and a_strict) else (1 if (b_no_worse and b_strict) else 0)
    return DominanceDecision(relation, upper_ab, upper_ba, alpha)
