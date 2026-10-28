"""Versioned future metrics correcting rainflow and terminal-SOC accounting.

Historical jer_microgrid.metrics and its stored results are deliberately intact.
Battery loss remains a model proxy, not a measured battery-lifetime outcome.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd

from .contracts import ContractError, finite_array
from .safety import validate_site
from jer_microgrid.metrics import compute_metrics as legacy_compute_metrics
from jer_microgrid.metrics import _lfp_interval_life_loss

METRICS_VERSION = "CRMT-METRICS-v2-RAINFLOW-TERMINAL-SOC"


def rainflow_cycles_detailed_v2(series):
    """Three-point rainflow counting, retaining the current reversal after a half cycle."""
    x = finite_array(series, "SOC trajectory", ndim=1)
    compact = [float(x[0])]
    for value in x[1:]:
        if value != compact[-1]:
            compact.append(float(value))
    if len(compact) < 2:
        return []
    points = [compact[0]]
    for previous, current, following in zip(compact, compact[1:], compact[2:]):
        if (current > previous) != (following > current):
            points.append(current)
    points.append(compact[-1])
    stack = []
    cycles = []
    for point in points:
        stack.append(point)
        while len(stack) >= 3:
            a, b, c = stack[-3:]
            first, second = abs(b - a), abs(c - b)
            if second < first:
                break
            lo, hi = min(a, b), max(a, b)
            if len(stack) == 3:
                cycles.append((first, 0.5, lo, hi))
                # The oldest reversal is discarded. Removing the middle point
                # would lose the return half-cycle of [low, high, low].
                del stack[0]
            else:
                cycles.append((first, 1.0, lo, hi))
                del stack[-3:-1]
    for a, b in zip(stack, stack[1:]):
        cycles.append((abs(b - a), 0.5, min(a, b), max(a, b)))
    return cycles


def compute_metrics_v2(sim, site):
    """Four-objective future metric path with full state trajectory validation."""
    validate_site(site)
    required = {"timestamp", "grid_kw", "cmd_kw", "soc", "soc_next",
                "p_imp_cap", "p_exp_cap", "cpu_ms", "mode"}
    if not isinstance(sim, pd.DataFrame) or sim.empty or not required <= set(sim):
        raise ContractError("future metrics require a nonempty checked simulation")
    for name in required - {"timestamp", "mode"}:
        finite_array(sim[name].to_numpy(), name, ndim=1)
    times = pd.DatetimeIndex(sim["timestamp"])
    if (times.tz is None or times.hasnans or times.has_duplicates
            or not times.is_monotonic_increasing):
        raise ContractError("future metric timestamps must be aware, unique and ordered")
    if len(times) > 1 and not np.allclose(
            np.diff(times.as_unit("ns").asi8) / 3.6e12,
            site.ts_hours, atol=1e-12, rtol=0):
        raise ContractError("future metric cadence differs from site model")
    soc = sim["soc"].to_numpy(dtype=float)
    following = sim["soc_next"].to_numpy(dtype=float)
    if not math.isclose(float(soc[0]), site.soc_init, abs_tol=1e-12, rel_tol=0):
        raise ContractError("initial SOC differs from site model")
    if len(soc) > 1 and not np.allclose(following[:-1], soc[1:], atol=1e-12, rtol=0):
        raise ContractError("discontinuous SOC trajectory")
    trajectory = np.concatenate([soc, following[-1:]])
    if np.any(trajectory < site.soc_min - 1e-12) or np.any(trajectory > site.soc_max + 1e-12):
        raise ContractError("SOC trajectory exceeds declared bounds")
    commands = sim["cmd_kw"].to_numpy(dtype=float)
    expected_next = np.where(
        commands >= 0,
        soc - site.ts_hours * commands / (site.e_nom_kwh * site.eta_dis),
        soc - site.ts_hours * commands * site.eta_ch / site.e_nom_kwh)
    if not np.allclose(expected_next, following, atol=1e-12, rtol=0):
        raise ContractError("SOC transitions disagree with command/efficiency model")
    if np.any(commands < -site.p_ch_max - 1e-12) or np.any(commands > site.p_dis_max + 1e-12):
        raise ContractError("commands exceed declared battery power")
    if not np.isfinite([site.beta_dod, site.dmc]).all() or site.beta_dod <= 0 or site.dmc < 0:
        raise ContractError("invalid battery proxy parameters")
    result = legacy_compute_metrics(sim, site)
    cycles = rainflow_cycles_detailed_v2(trajectory)
    depths = np.asarray([row[0] for row in cycles], dtype=float)
    weights = np.asarray([row[1] for row in cycles], dtype=float)
    result["efcrf"] = float(np.sum(weights * depths))
    result["idod"] = float(np.sum(weights * depths ** site.beta_dod))
    result["n_micro"] = float(np.sum(weights * (depths <= site.dmc)))
    result["lfp_cycle_loss_pct"] = 100 * float(sum(
        _lfp_interval_life_loss(low, high, weight)
        for _, weight, low, high in cycles))
    if cycles:
        bins = np.array([0.0, 0.1, 0.2, 0.4, 0.6, 1.0 + 1e-9])
        counts, edges = np.histogram(depths, bins=bins, weights=weights)
        result["rainflow_hist"] = {
            f"[{edges[i]:.1f},{edges[i + 1]:.1f})": float(counts[i])
            for i in range(len(counts))}
    else:
        result["rainflow_hist"] = {}
    result["metrics_version"] = METRICS_VERSION
    result["battery_lifetime_evidence"] = "MODEL_PROXY_NOT_PHYSICAL_LIFETIME"
    return result
