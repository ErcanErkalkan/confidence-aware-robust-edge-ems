from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import SiteConfig
from .controllers import ControllerBase, compute_caps
from .optimization_refs import LinearMPCQPController


@dataclass
class SimResult:
    series: pd.DataFrame
    meta: dict[str, Any]



def soc_update(soc: float, cmd_kw: float, site: SiteConfig) -> float:
    if cmd_kw >= 0:
        soc_next = soc - (site.ts_hours / site.e_nom_kwh) * (cmd_kw / site.eta_dis)
    else:
        soc_next = soc + (site.ts_hours / site.e_nom_kwh) * (site.eta_ch * (-cmd_kw))
    return float(np.clip(soc_next, 0.0, 1.0))



def simulate_controller(profile: pd.DataFrame, controller: ControllerBase, site: SiteConfig,
                        *, future_preview: bool = False) -> SimResult:
    controller.reset()
    base = profile['base_kw'].to_numpy(dtype=float)
    peak = profile['peak_flag'].to_numpy(dtype=int)
    ts = profile['timestamp'].to_numpy()
    n = len(profile)
    is_disconnected = profile['is_disconnected'].to_numpy(dtype=bool) if 'is_disconnected' in profile else np.zeros(n, dtype=bool)
    soc = site.soc_init
    rows = []
    total_cpu = 0.0
    
    is_cloud_dependent = getattr(controller, 'is_cloud_dependent', False)
    if isinstance(controller, LinearMPCQPController):
        is_cloud_dependent = True

    prev_valid_cmd = 0.0

    for t in range(n):
        history = base[: t + 1]
        if is_cloud_dependent and is_disconnected[t]:
            cmd = prev_valid_cmd
            debug = {'mode': 'OFFLINE', 'rg_state': 'MID'}
            cpu = 0.0
        else:
            t0 = time.perf_counter()
            if isinstance(controller, LinearMPCQPController):
                cmd, debug = controller.step(
                    t,
                    history,
                    soc,
                    int(peak[t]),
                    future_base=base[t: t + site.horizon_k] if future_preview else None,
                    future_peak_flags=peak[t: t + site.horizon_k] if future_preview else None,
                )
            else:
                cmd, debug = controller.step(t, history, soc, int(peak[t]))
            cpu = time.perf_counter() - t0
            prev_valid_cmd = cmd
            
        total_cpu += cpu
        grid = base[t] - cmd
        soc_next = soc_update(soc, cmd, site)
        rows.append({
            'timestamp': ts[t],
            'base_kw': base[t],
            'cmd_kw': cmd,
            'grid_kw': grid,
            'soc': soc,
            'soc_next': soc_next,
            'mode': debug.get('mode', 'RG'),
            'rg_state': debug.get('rg_state', 'MID'),
            'desired_kw': debug.get('desired_kw', np.nan),
            'p_imp_cap': debug.get('p_imp_cap', np.nan),
            'p_exp_cap': debug.get('p_exp_cap', np.nan),
            'e_imp': debug.get('e_imp', np.nan),
            'e_exp': debug.get('e_exp', np.nan),
            'e1_imp': debug.get('e1_imp', np.nan),
            'e1_exp': debug.get('e1_exp', np.nan),
            'cpu_ms': cpu * 1000.0,
        })
        soc = soc_next
    out = pd.DataFrame(rows)
    meta = {
        'controller': getattr(controller, 'name', controller.__class__.__name__),
        'avg_cpu_ms': total_cpu * 1000.0 / max(n, 1),
        'max_cpu_ms': float(out['cpu_ms'].max()) if not out.empty else 0.0,
    }
    return SimResult(series=out, meta=meta)


def replay_command_profile(profile: pd.DataFrame, cmd_kw: np.ndarray, site: SiteConfig, *, cpu_ms: float | np.ndarray | None = None) -> pd.DataFrame:
    base = profile['base_kw'].to_numpy(dtype=float)
    peak = profile['peak_flag'].to_numpy(dtype=int)
    ts = profile['timestamp'].to_numpy()
    cmd = np.asarray(cmd_kw, dtype=float)
    if cmd.size != len(profile):
        raise ValueError('Command trajectory length must match the profile length.')

    if cpu_ms is None:
        cpu_vals = np.full(len(profile), np.nan, dtype=float)
    else:
        cpu_vals = np.asarray(cpu_ms, dtype=float)
        if cpu_vals.ndim == 0:
            cpu_vals = np.full(len(profile), float(cpu_vals), dtype=float)
        elif cpu_vals.size != len(profile):
            raise ValueError('cpu_ms must be a scalar or match the profile length.')

    soc = site.soc_init
    rows = []
    for t in range(len(profile)):
        p_imp_cap, p_exp_cap = compute_caps(int(peak[t]), site)
        e_now_imp = max(0.0, float(base[t]) - p_imp_cap)
        e_now_exp = max(0.0, -float(base[t]) - p_exp_cap)
        soc_next = soc_update(soc, float(cmd[t]), site)
        rows.append({
            'timestamp': ts[t],
            'base_kw': float(base[t]),
            'cmd_kw': float(cmd[t]),
            'grid_kw': float(base[t] - cmd[t]),
            'soc': float(soc),
            'soc_next': float(soc_next),
            'mode': 'PS' if cmd[t] > 1e-9 else ('VF' if cmd[t] < -1e-9 else 'RG'),
            'rg_state': 'MID',
            'desired_kw': float(cmd[t]),
            'p_imp_cap': float(p_imp_cap),
            'p_exp_cap': float(p_exp_cap),
            'e_imp': float(e_now_imp),
            'e_exp': float(e_now_exp),
            'e1_imp': float(e_now_imp),
            'e1_exp': float(e_now_exp),
            'cpu_ms': float(cpu_vals[t]),
        })
        soc = soc_next
    return pd.DataFrame(rows)


def attach_profile_columns(sim_df: pd.DataFrame, profile: pd.DataFrame) -> pd.DataFrame:
    cols = ['scenario', 'seed', 'scenario_seed', 'day_id', 'load_kw', 'pv_kw', 'wind_kw', 'peak_flag']
    merged = sim_df.copy()
    for col in cols:
        merged[col] = profile[col].to_numpy()
    return merged
