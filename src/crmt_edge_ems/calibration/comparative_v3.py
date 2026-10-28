"""Whole-day exploratory bootstrap comparators; no finite-sample guarantee.

Inverters and candidates are resampled together. CAL-v2's conditional DKW
implementation remains separate and unchanged. No capacity truncation occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math

import numpy as np

from ..contracts import ContractError, finite_array, integer, pareto_mask


@dataclass(frozen=True)
class DayBootstrap:
    point: np.ndarray
    replicates: np.ndarray
    support_days: int
    block_length: int
    n_boot: int


def risk_day_panel(samples, *, q=0.9, tail_weight=0.5):
    """Mean + ceil-tail risk, pooling inverter marginals, not independent days."""
    x = finite_array(samples, "whole-day panel", ndim=4)
    n, c, i, o = x.shape
    if n < 2 or c < 2 or i < 1 or o != 4:
        raise ContractError("days>=2, candidates>=2, inverters>=1, four objectives required")
    if (isinstance(q, (bool, np.bool_)) or not isinstance(q, (int, float))
            or not math.isfinite(q) or not 0 <= q < 1):
        raise ContractError("q must be finite in [0,1)")
    if (isinstance(tail_weight, (bool, np.bool_))
            or not isinstance(tail_weight, (int, float))
            or not math.isfinite(tail_weight) or tail_weight < 0):
        raise ContractError("nonnegative finite tail weight required")
    pooled = x.transpose(1, 0, 2, 3).reshape(c, n*i, o)
    mass = (1-Fraction(str(q)))*(n*i)
    k = (mass.numerator+mass.denominator-1)//mass.denominator
    return pooled.mean(axis=1)+tail_weight*np.sort(pooled, axis=1)[:, -k:].mean(axis=1)


def day_bootstrap(samples, *, n_boot=399, seed=0, block_length=1,
                  chronology=None, q=0.9, tail_weight=0.5):
    """Resample complete day vectors; circular blocks require consecutive days.

    Paired candidate/inverter structure is preserved within every sampled day.
    Circular blocks are exploratory under dependence, never an IID declaration.
    """
    x = finite_array(samples, "whole-day panel", ndim=4)
    point = risk_day_panel(x, q=q, tail_weight=tail_weight)
    n = len(x)
    n_boot = integer(n_boot, "n_boot", 199)
    block_length = integer(block_length, "block_length", 1)
    seed = integer(seed, "seed")
    if block_length > n:
        raise ContractError("block length exceeds days")
    if block_length > 1:
        if chronology is None:
            raise ContractError("consecutive day chronology required for circular blocks")
        chronology = finite_array(chronology, "day chronology", ndim=1)
        if len(chronology) != n or not np.all(np.diff(chronology) == 1):
            raise ContractError("circular blocks cannot bridge missing chronological days")
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        if block_length == 1:
            indices = rng.integers(n, size=n)
        else:
            starts = rng.integers(n, size=math.ceil(n/block_length))
            indices = ((starts[:, None]+np.arange(block_length)) % n).ravel()[:n]
        boot.append(risk_day_panel(x[indices], q=q, tail_weight=tail_weight))
    return DayBootstrap(point, np.stack(boot), n, block_length, n_boot)


def filter_day_bootstrap(bootstrap, *, method="maxT", alpha=0.05):
    """Exploratory one-sided paired risk differences, all minimization objectives.

    Quantile resolution is reported, including inadequate Bonferroni tails.
    """
    if not isinstance(bootstrap, DayBootstrap):
        raise ContractError("DayBootstrap required")
    if (isinstance(alpha, (bool, np.bool_))
            or not isinstance(alpha, (int, float))
            or not math.isfinite(alpha) or not 0 < alpha < 0.5):
        raise ContractError("alpha must be finite in (0,0.5)")
    if method not in {"unadjusted", "bonferroni", "maxT"}:
        raise ContractError("unknown bootstrap comparison method")
    observed, b = bootstrap.point, bootstrap.replicates
    c, o = observed.shape
    offdiag = ~np.eye(c, dtype=bool)
    diff = observed[:, None, :]-observed[None, :, :]
    errors = diff[None]-b[:, :, None, :]+b[:, None, :, :]
    family_size = c*(c-1)*o
    margin = np.zeros_like(diff)
    if method == "maxT":
        scales = np.maximum(errors[:, offdiag].std(axis=0, ddof=1), 1e-12)
        max_t = np.max(errors[:, offdiag]/scales[None], axis=(1, 2))
        critical = max(0., float(np.quantile(max_t, 1-alpha)))
        margin[offdiag] = critical*scales
        sufficient = (bootstrap.n_boot+1)*alpha >= 1
    else:
        tail_alpha = alpha/family_size if method == "bonferroni" else alpha
        margin[offdiag] = np.maximum(0., np.quantile(errors[:, offdiag], 1-tail_alpha, axis=0))
        sufficient = (bootstrap.n_boot+1)*tail_alpha >= 1
    upper = diff+margin
    declarations = np.all(upper <= 0, axis=2) & np.any(upper < 0, axis=2) & offdiag
    return {
        "upper_differences": upper,
        "declarations": declarations,
        "retained": ~np.any(declarations, axis=0),
        "bootstrap_tail_resolution_sufficient": bool(sufficient),
        "family_size": family_size,
        "statistical_scope": "EXPLORATORY_BOOTSTRAP_NO_COVERAGE_THEOREM",
    }


def diagnostics(retained, declarations, upper_differences, *, capacity=10,
                truth=None, abstain_on_overflow=False):
    """Keep coverage, false declarations, retention, overflow and decision apart."""
    capacity = integer(capacity, "capacity", 1)
    retained = np.asarray(retained, dtype=bool)
    declarations = np.asarray(declarations, dtype=bool)
    upper = np.asarray(upper_differences, dtype=float)
    c = len(retained)
    if retained.ndim != 1 or declarations.shape != (c, c) or upper.shape != (c, c, 4):
        raise ContractError("filter shapes disagree")
    if not isinstance(abstain_on_overflow, bool):
        raise ContractError("abstain_on_overflow must be boolean")
    overflow = int(retained.sum()) > capacity
    result = {
        "archive_size": int(retained.sum()), "capacity": capacity,
        "archive_overflow": overflow,
        "abstention": bool(abstain_on_overflow and overflow),
        "selection_executed": False,
        "shortlist_size": None,
        "false_elimination": None, "family_coverage": None,
        "false_dominance": None, "retained_pareto_fraction": None,
        "retained_pareto_count": None, "true_pareto_size": None,
    }
    if truth is not None:
        true = finite_array(truth, "known risk truth", ndim=2)
        if true.shape != (c, 4):
            raise ContractError("known truth/filter shapes disagree")
        delta = true[:, None, :]-true[None, :, :]
        offdiag = ~np.eye(c, dtype=bool)
        dominates = np.all(delta <= 0, axis=2) & np.any(delta < 0, axis=2) & offdiag
        front = pareto_mask(true)
        hits = int(np.sum(front & retained))
        result.update(
            false_elimination=bool(np.any(front & ~retained)),
            family_coverage=bool(np.all((delta <= upper)[offdiag])),
            false_dominance=bool(np.any(declarations & ~dominates)),
            retained_pareto_fraction=hits/int(front.sum()),
            retained_pareto_count=hits, true_pareto_size=int(front.sum()),
        )
    return result
