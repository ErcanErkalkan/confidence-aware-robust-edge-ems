from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass

@dataclass
class NetworkConfig:
    disconnect_prob_per_hr: float = 0.05
    disconnect_duration_min: float = 30.0
    latency_base_ms: float = 50.0
    latency_noise_std_ms: float = 10.0

def inject_network_state(df: pd.DataFrame, seed: int, cfg: NetworkConfig, ts_hours: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 9999)
    n = len(df)
    
    latency = rng.normal(cfg.latency_base_ms, cfg.latency_noise_std_ms, n)
    latency = np.clip(latency, 5.0, None)
    
    is_disconnected = np.zeros(n, dtype=bool)
    prob_per_tick = cfg.disconnect_prob_per_hr * ts_hours
    disconnect_ticks = max(1, int(round(cfg.disconnect_duration_min / (ts_hours * 60.0))))
    
    remaining = 0
    for t in range(n):
        if remaining <= 0 and rng.random() < prob_per_tick:
            remaining = int(rng.integers(1, disconnect_ticks + 1))
        
        if remaining > 0:
            is_disconnected[t] = True
            remaining -= 1
            latency[t] = 9999.0
            
    df_net = df.copy()
    df_net['latency_ms'] = latency
    df_net['is_disconnected'] = is_disconnected
    return df_net
