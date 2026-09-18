from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def nondominated_points(points: np.ndarray, *, atol: float = 1e-12) -> np.ndarray:
    """Return unique minimization-nondominated rows."""
    x = np.asarray(points, dtype=float)
    if x.ndim != 2 or x.shape[0] == 0:
        raise ValueError("points must be a non-empty 2D array")
    if not np.isfinite(x).all():
        raise ValueError("points must be finite")
    keep = []
    for i in range(len(x)):
        dominated = False
        for j in range(len(x)):
            if i == j:
                continue
            no_worse = np.all(x[j] <= x[i] + atol)
            strict = np.any(x[j] < x[i] - atol)
            if no_worse and strict:
                dominated = True
                break
        if not dominated:
            keep.append(i)
    out = x[keep]
    return np.unique(out, axis=0)


def exact_hypervolume(points: np.ndarray, reference: Sequence[float]) -> float:
    """Exact axis-aligned dominated hypervolume for minimization fronts."""
    x = np.asarray(points, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if x.ndim != 2 or ref.shape != (x.shape[1],):
        raise ValueError("reference width must match point dimension")
    if not np.isfinite(x).all() or not np.isfinite(ref).all():
        raise ValueError("points/reference must be finite")
    x = x[np.all(x < ref, axis=1)]
    if x.size == 0:
        return 0.0
    x = nondominated_points(x)

    def rec(p: np.ndarray, r: np.ndarray) -> float:
        if len(p) == 0:
            return 0.0
        if p.shape[1] == 1:
            return max(0.0, float(r[0] - np.min(p[:, 0])))
        z_values = np.unique(p[:, -1])
        z_values = z_values[z_values < r[-1]]
        total = 0.0
        for i, z0 in enumerate(z_values):
            z1 = float(z_values[i + 1]) if i + 1 < len(z_values) else float(r[-1])
            if z1 <= z0:
                continue
            active = p[p[:, -1] <= z0, :-1]
            total += rec(active, r[:-1]) * (z1 - float(z0))
        return total

    return float(rec(x, ref))


def igd_plus(approximation: np.ndarray, reference_front: np.ndarray) -> float:
    """IGD+ for minimization; lower is better."""
    a = np.asarray(approximation, dtype=float)
    r = np.asarray(reference_front, dtype=float)
    if a.ndim != 2 or r.ndim != 2 or a.shape[1] != r.shape[1]:
        raise ValueError("approximation/reference shape mismatch")
    if len(a) == 0 or len(r) == 0:
        raise ValueError("fronts must be non-empty")
    distances = []
    for ref in r:
        delta = np.maximum(a - ref, 0.0)
        distances.append(float(np.min(np.linalg.norm(delta, axis=1))))
    return float(np.mean(distances))


def additive_epsilon(
    approximation: np.ndarray,
    reference_front: np.ndarray,
) -> float:
    """Unary additive epsilon indicator for minimization; lower is better."""
    a = np.asarray(approximation, dtype=float)
    r = np.asarray(reference_front, dtype=float)
    if a.ndim != 2 or r.ndim != 2 or a.shape[1] != r.shape[1]:
        raise ValueError("approximation/reference shape mismatch")
    if len(a) == 0 or len(r) == 0:
        raise ValueError("fronts must be non-empty")
    per_ref = []
    for ref in r:
        eps_to_each = np.max(a - ref, axis=1)
        per_ref.append(float(np.min(eps_to_each)))
    return float(np.max(per_ref))


def validation_optimizer_indicators(
    candidate_scores: pd.DataFrame,
    *,
    objectives: Sequence[str],
    hv_reference_value: float = 1.10,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """Compute common-reference validation indicators for all methods in one seed."""
    required = {"method", *objectives}
    missing = sorted(required - set(candidate_scores.columns))
    if missing:
        raise KeyError(f"candidate score table missing columns: {missing}")
    if candidate_scores.empty:
        raise ValueError("candidate_scores is empty")

    values = candidate_scores[list(objectives)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("candidate objective values must be finite")
    ideal = np.min(values, axis=0)
    worst = np.max(values, axis=0)
    spans = worst - ideal
    normalized = np.zeros_like(values, dtype=float)
    nondegenerate = spans > 1e-12
    normalized[:, nondegenerate] = (
        values[:, nondegenerate] - ideal[nondegenerate]
    ) / spans[nondegenerate]

    work = candidate_scores[["method"]].copy()
    for j, objective in enumerate(objectives):
        work[f"norm__{objective}"] = normalized[:, j]

    norm_cols = [f"norm__{o}" for o in objectives]
    union_reference = nondominated_points(work[norm_cols].to_numpy(dtype=float))
    hv_ref = np.full(len(objectives), float(hv_reference_value), dtype=float)

    rows = []
    for method, group in work.groupby("method", sort=True):
        front = nondominated_points(group[norm_cols].to_numpy(dtype=float))
        rows.append(
            {
                "method": method,
                "validation_front_size": int(len(front)),
                "hypervolume": exact_hypervolume(front, hv_ref),
                "igd_plus": igd_plus(front, union_reference),
                "additive_epsilon": additive_epsilon(front, union_reference),
            }
        )
    refs = {
        objective: {
            "ideal": float(ideal[j]),
            "observed_worst": float(worst[j]),
            "span": float(spans[j]),
            "degenerate": bool(not nondegenerate[j]),
        }
        for j, objective in enumerate(objectives)
    }
    return pd.DataFrame(rows), refs
