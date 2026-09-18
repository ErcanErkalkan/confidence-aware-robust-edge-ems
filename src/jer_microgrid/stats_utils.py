from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

from .config import PRIMARY_STRESS_METRICS
from .utils import bootstrap_ci_mean, cohen_dz, rank_biserial_from_diff


def holm_adjust(p_values: Sequence[float]) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values without statsmodels dependency."""
    p = np.asarray(list(p_values), dtype=float)
    m = p.size
    if m == 0:
        return np.array([], dtype=float)
    order = np.argsort(p)
    p_sorted = p[order]
    adjusted_sorted = np.empty(m, dtype=float)
    running_max = 0.0
    for i, pv in enumerate(p_sorted):
        adj = (m - i) * pv
        running_max = max(running_max, adj)
        adjusted_sorted[i] = min(running_max, 1.0)
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted


def paired_stats_table(df: pd.DataFrame, left: str, right: str, metrics: Sequence[str] | None = None,
                       controller_col: str = 'controller', unit_cols: Sequence[str] = ('scenario_seed', 'day_id')) -> pd.DataFrame:
    metrics = list(metrics or PRIMARY_STRESS_METRICS)
    left_df = df[df[controller_col] == left].copy()
    right_df = df[df[controller_col] == right].copy()
    merged = left_df.merge(right_df, on=list(unit_cols), suffixes=('_left', '_right'))
    rows = []
    raw_ps = []
    for metric in metrics:
        x = merged[f'{metric}_left'].to_numpy(dtype=float)
        y = merged[f'{metric}_right'].to_numpy(dtype=float)
        diff = x - y
        if diff.size == 0:
            rows.append({
                'metric': metric,
                'comparison': f'{left} vs {right}',
                'n_pairs': 0,
                'mean_paired_diff': float('nan'),
                'ci95_lo': float('nan'),
                'ci95_hi': float('nan'),
                'p_value': float('nan'),
                'effect_size': float('nan'),
                'effect_name': 'NA',
                'direction': 'undetermined',
            })
            raw_ps.append(float('nan'))
            continue

        if np.allclose(diff, 0.0, equal_nan=True):
            ci_lo, ci_hi = bootstrap_ci_mean(diff)
            rows.append({
                'metric': metric,
                'comparison': f'{left} vs {right}',
                'n_pairs': int(diff.size),
                'mean_paired_diff': 0.0,
                'ci95_lo': float(ci_lo),
                'ci95_hi': float(ci_hi),
                'p_value': 1.0,
                'effect_size': 0.0,
                'effect_name': 'NoDifference',
                'direction': 'tie',
            })
            raw_ps.append(1.0)
            continue

        normal = False
        if diff.size >= 8:
            try:
                normal = stats.shapiro(diff).pvalue > 0.05
            except Exception:
                normal = False
        if normal:
            test = stats.ttest_rel(x, y, nan_policy='omit')
            p = float(test.pvalue)
            effect = cohen_dz(diff)
            effect_name = 'Cohen_dz'
        else:
            try:
                test = stats.wilcoxon(x, y, zero_method='wilcox', alternative='two-sided')
                p = float(test.pvalue)
            except Exception:
                p = 1.0
            effect = rank_biserial_from_diff(diff)
            effect_name = 'Rank_biserial'
        ci_lo, ci_hi = bootstrap_ci_mean(diff)
        direction = 'left_better' if np.nanmean(diff) < 0 else 'right_better'
        rows.append({
            'metric': metric,
            'comparison': f'{left} vs {right}',
            'n_pairs': int(diff.size),
            'mean_paired_diff': float(np.nanmean(diff)),
            'ci95_lo': float(ci_lo),
            'ci95_hi': float(ci_hi),
            'p_value': p,
            'effect_size': float(effect),
            'effect_name': effect_name,
            'direction': direction,
        })
        raw_ps.append(p)
    finite_ps = [p for p in raw_ps if np.isfinite(p)]
    adj = holm_adjust(finite_ps) if finite_ps else []
    adj_idx = 0
    for row, raw_p in zip(rows, raw_ps):
        if np.isfinite(raw_p):
            row['p_holm'] = float(adj[adj_idx])
            adj_idx += 1
        else:
            row['p_holm'] = float('nan')
    return pd.DataFrame(rows)
