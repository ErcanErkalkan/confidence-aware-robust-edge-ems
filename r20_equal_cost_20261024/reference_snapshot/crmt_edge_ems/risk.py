from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


DEFAULT_OBJECTIVES: tuple[str, ...] = (
    "cap_violation_pct_total",
    "lfp_cycle_loss_pct",
    "ramp95_kw_per_min",
    "flip_per_day",
)


@dataclass(frozen=True)
class RiskConfig:
    q: float = 0.90
    tail_weight: float = 0.50
    objectives: tuple[str, ...] = DEFAULT_OBJECTIVES

    def __post_init__(self) -> None:
        if not (0.5 <= self.q < 1.0):
            raise ValueError("q must be in [0.5, 1)")
        if self.tail_weight < 0.0:
            raise ValueError("tail_weight must be non-negative")


def empirical_cvar(values: Sequence[float] | np.ndarray, q: float = 0.90) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    if not (0.0 <= q < 1.0):
        raise ValueError("q must be in [0, 1)")
    k = max(1, int(np.ceil((1.0 - q) * x.size)))
    tail = np.partition(x, x.size - k)[x.size - k :]
    return float(np.mean(tail))


def risk_calibrated_score(values: Sequence[float] | np.ndarray, *, q: float = 0.90, tail_weight: float = 0.50) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.mean(x) + tail_weight * empirical_cvar(x, q=q))


def aggregate_objectives(block_metrics: pd.DataFrame, config: RiskConfig = RiskConfig()) -> dict[str, float]:
    missing = [c for c in config.objectives if c not in block_metrics.columns]
    if missing:
        raise KeyError(f"Missing objective columns: {missing}")
    return {objective:risk_calibrated_score(block_metrics[objective].to_numpy(dtype=float),q=config.q,tail_weight=config.tail_weight) for objective in config.objectives}


def objective_matrix(block_metrics: pd.DataFrame, objectives: Sequence[str] = DEFAULT_OBJECTIVES) -> np.ndarray:
    missing = [c for c in objectives if c not in block_metrics.columns]
    if missing:
        raise KeyError(f"Missing objective columns: {missing}")
    return block_metrics[list(objectives)].to_numpy(dtype=float)
