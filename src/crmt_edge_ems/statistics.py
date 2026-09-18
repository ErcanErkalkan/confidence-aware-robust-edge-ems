from __future__ import annotations

from itertools import combinations
from typing import Sequence

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, rankdata, wilcoxon


def holm_adjust(p_values: Sequence[float]) -> np.ndarray:
    """Holm family-wise adjusted p-values in original order."""
    p = np.asarray(p_values, dtype=float)
    if p.ndim != 1 or not np.isfinite(p).all():
        raise ValueError("p_values must be a finite one-dimensional sequence")
    m = len(p)
    if m == 0:
        return np.asarray([], dtype=float)
    order = np.argsort(p, kind="mergesort")
    sorted_p = p[order]
    adjusted_sorted = np.empty(m, dtype=float)
    running = 0.0
    for i, value in enumerate(sorted_p):
        candidate = min(1.0, (m - i) * float(value))
        running = max(running, candidate)
        adjusted_sorted[i] = running
    out = np.empty(m, dtype=float)
    out[order] = adjusted_sorted
    return out


def paired_rank_biserial(a: Sequence[float], b: Sequence[float]) -> float:
    """Paired rank-biserial effect for differences a-b.

    Positive values mean a tends to be numerically larger than b; negative
    values mean a tends to be smaller. The scientific meaning of direction
    depends on whether the metric is minimized or maximized.
    """
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if d.ndim != 1 or not np.isfinite(d).all():
        raise ValueError("paired values must be finite one-dimensional arrays")
    nz = d != 0.0
    d = d[nz]
    if d.size == 0:
        return 0.0
    ranks = rankdata(np.abs(d), method="average")
    w_plus = float(np.sum(ranks[d > 0]))
    w_minus = float(np.sum(ranks[d < 0]))
    denom = w_plus + w_minus
    return 0.0 if denom == 0.0 else (w_plus - w_minus) / denom


def paired_bootstrap_median_difference(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_boot: int = 10_000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Median paired difference a-b with deterministic percentile bootstrap CI."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("a and b must be same-shape one-dimensional arrays")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("paired arrays must be finite")
    if a.size < 2:
        raise ValueError("at least two paired observations are required")
    if n_boot < 1000:
        raise ValueError("n_boot must be >= 1000")
    if not (0.0 < alpha < 0.5):
        raise ValueError("alpha must be in (0,0.5)")
    d = a - b
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(int(n_boot), d.size))
    boots = np.median(d[idx], axis=1)
    lo, hi = np.quantile(boots, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(np.median(d)), float(lo), float(hi)


def friedman_table(
    long_frame: pd.DataFrame,
    *,
    metrics: Sequence[str],
    methods: Sequence[str],
    seed_col: str = "seed",
    method_col: str = "method",
) -> pd.DataFrame:
    rows = []
    for metric in metrics:
        pivot = long_frame.pivot(
            index=seed_col,
            columns=method_col,
            values=metric,
        )
        missing = [m for m in methods if m not in pivot.columns]
        if missing or pivot[list(methods)].isna().any().any():
            raise ValueError(f"incomplete paired design for {metric}: missing={missing}")
        arrays = [pivot[m].to_numpy(dtype=float) for m in methods]
        if all(np.allclose(arrays[0], x) for x in arrays[1:]):
            statistic, p_value = 0.0, 1.0
        else:
            result = friedmanchisquare(*arrays)
            statistic = float(result.statistic)
            p_value = float(result.pvalue)
            if not np.isfinite(statistic) or not np.isfinite(p_value):
                statistic, p_value = 0.0, 1.0
        rows.append(
            {
                "metric": metric,
                "n_seeds": int(len(pivot)),
                "friedman_statistic": statistic,
                "p_value": p_value,
            }
        )
    return pd.DataFrame(rows)


def pairwise_paired_table(
    long_frame: pd.DataFrame,
    *,
    metrics: Sequence[str],
    methods: Sequence[str],
    n_boot: int,
    bootstrap_seed: int,
    alpha: float,
    direction: dict[str, str] | None = None,
    seed_col: str = "seed",
    method_col: str = "method",
) -> pd.DataFrame:
    """Paired Wilcoxon/effect-size table with Holm correction per metric family."""
    rows = []
    direction = direction or {}
    pairs = list(combinations(methods, 2))
    for metric_index, metric in enumerate(metrics):
        pivot = long_frame.pivot(
            index=seed_col,
            columns=method_col,
            values=metric,
        )
        missing = [m for m in methods if m not in pivot.columns]
        if missing or pivot[list(methods)].isna().any().any():
            raise ValueError(f"incomplete paired design for {metric}: missing={missing}")
        metric_rows = []
        raw_p = []
        for pair_index, (a_name, b_name) in enumerate(pairs):
            a = pivot[a_name].to_numpy(dtype=float)
            b = pivot[b_name].to_numpy(dtype=float)
            d = a - b
            if np.allclose(d, 0.0):
                statistic, p_value = 0.0, 1.0
            else:
                result = wilcoxon(
                    a,
                    b,
                    zero_method="wilcox",
                    alternative="two-sided",
                    method="auto",
                )
                statistic = float(result.statistic)
                p_value = float(result.pvalue)
            effect = paired_rank_biserial(a, b)
            median_diff, ci_low, ci_high = paired_bootstrap_median_difference(
                a,
                b,
                n_boot=n_boot,
                seed=int(bootstrap_seed + 1000 * metric_index + pair_index),
                alpha=alpha,
            )
            row = {
                "metric": metric,
                "metric_direction": direction.get(metric, "unspecified"),
                "method_a": a_name,
                "method_b": b_name,
                "n_seeds": int(len(a)),
                "wilcoxon_statistic": statistic,
                "p_value_raw": p_value,
                "rank_biserial_a_minus_b": effect,
                "median_difference_a_minus_b": median_diff,
                "median_difference_ci_low": ci_low,
                "median_difference_ci_high": ci_high,
            }
            metric_rows.append(row)
            raw_p.append(p_value)
        adjusted = holm_adjust(raw_p)
        for row, p_adj in zip(metric_rows, adjusted):
            row["p_value_holm"] = float(p_adj)
            row["alpha"] = float(alpha)
            rows.append(row)
    return pd.DataFrame(rows)


def descriptive_table(
    long_frame: pd.DataFrame,
    *,
    metrics: Sequence[str],
    method_col: str = "method",
) -> pd.DataFrame:
    rows = []
    for method, group in long_frame.groupby(method_col, sort=True):
        for metric in metrics:
            x = pd.to_numeric(group[metric], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(x).all():
                raise ValueError(f"non-finite values for {method}/{metric}")
            rows.append(
                {
                    "method": method,
                    "metric": metric,
                    "n": int(len(x)),
                    "mean": float(np.mean(x)),
                    "std": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
                    "median": float(np.median(x)),
                    "q25": float(np.quantile(x, 0.25)),
                    "q75": float(np.quantile(x, 0.75)),
                    "min": float(np.min(x)),
                    "max": float(np.max(x)),
                }
            )
    return pd.DataFrame(rows)
