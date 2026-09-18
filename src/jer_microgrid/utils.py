from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats


def clip(x, lo, hi):
    return np.minimum(np.maximum(x, lo), hi)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return values.copy()
    s = pd.Series(values)
    return s.rolling(window=window, min_periods=1).mean().to_numpy()


def bootstrap_ci_mean(diff: np.ndarray, alpha: float = 0.05, n_boot: int = 2000, seed: int = 1234) -> tuple[float, float]:
    diff = np.asarray(diff, dtype=float)
    rng = np.random.default_rng(seed)
    if diff.size == 0:
        return float('nan'), float('nan')
    samples = rng.choice(diff, size=(n_boot, diff.size), replace=True)
    means = samples.mean(axis=1)
    lo = np.quantile(means, alpha / 2)
    hi = np.quantile(means, 1 - alpha / 2)
    return float(lo), float(hi)


def cohen_dz(diff: np.ndarray) -> float:
    diff = np.asarray(diff, dtype=float)
    sd = diff.std(ddof=1)
    if diff.size < 2 or sd == 0:
        return 0.0
    return float(diff.mean() / sd)


def cliff_delta(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x)
    y = np.asarray(y)
    if x.size == 0 or y.size == 0:
        return float('nan')
    gt = 0
    lt = 0
    for xi in x:
        gt += np.sum(xi > y)
        lt += np.sum(xi < y)
    return float((gt - lt) / (x.size * y.size))


def rank_biserial_from_diff(diff: np.ndarray) -> float:
    diff = np.asarray(diff, dtype=float)
    diff = diff[np.isfinite(diff)]
    diff = diff[~np.isclose(diff, 0.0)]
    if diff.size == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(diff), method='average')
    pos = float(ranks[diff > 0.0].sum())
    neg = float(ranks[diff < 0.0].sum())
    denom = pos + neg
    if denom == 0.0:
        return 0.0
    return float((pos - neg) / denom)


def pct(x: np.ndarray | float) -> float:
    arr = np.asarray(x, dtype=float)
    return float(100.0 * np.mean(arr))


def save_json(path: str | Path, obj) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, default=str)


def latex_escape(text: str) -> str:
    repl = {
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return text


def mean_std_str(x: Iterable[float], ndigits: int = 2) -> str:
    arr = np.asarray(list(x), dtype=float)
    if arr.size == 0:
        return 'NA'
    return f"{arr.mean():.{ndigits}f} ({arr.std(ddof=1) if arr.size > 1 else 0.0:.{ndigits}f})"


def median_iqr_str(x: Iterable[float], ndigits: int = 2) -> str:
    arr = np.asarray(list(x), dtype=float)
    if arr.size == 0:
        return 'NA'
    q1, q3 = np.quantile(arr, [0.25, 0.75])
    return f"{np.median(arr):.{ndigits}f} [{q1:.{ndigits}f}, {q3:.{ndigits}f}]"


def time_of_use_peak_flag(index: pd.DatetimeIndex) -> np.ndarray:
    hours = index.hour
    return ((hours >= 17) & (hours < 22)).astype(int)


def scenario_seed_id(scenario: str, seed: int) -> str:
    return f"{scenario}_seed{seed}"


def quantile_safe(x: np.ndarray, q: float) -> float:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return float('nan')
    return float(np.quantile(x, q))
