from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import numpy as np
import pandas as pd

from .config import SiteConfig, SyntheticConfig
from .utils import scenario_seed_id, time_of_use_peak_flag


_BASE_TS_HOURS = 1.0 / 60.0


def _scaled_decay(per_minute_decay: float, ts_hours: float) -> float:
    scale = float(ts_hours / _BASE_TS_HOURS)
    return float(per_minute_decay ** scale)


def _scaled_alpha(per_minute_alpha: float, ts_hours: float) -> float:
    scale = float(ts_hours / _BASE_TS_HOURS)
    return float(1.0 - (1.0 - per_minute_alpha) ** scale)


def _inject_step_events(signal: np.ndarray, rng: np.random.Generator, prob_per_hr: float, range_kw: tuple[float, float], ts_hours: float) -> np.ndarray:
    n = signal.size
    p = prob_per_hr * ts_hours
    decay = _scaled_decay(0.995, ts_hours)
    offsets = np.zeros(n)
    active = 0.0
    for t in range(n):
        if rng.random() < p:
            active += rng.uniform(*range_kw)
        # decay back toward zero slowly
        active *= decay
        offsets[t] = active
    return signal + offsets


def _pv_profile(index: pd.DatetimeIndex, cfg: SyntheticConfig, rng: np.random.Generator, scenario: str, ts_hours: float) -> np.ndarray:
    hour = index.hour + index.minute / 60.0
    daylight = np.clip(np.sin(np.pi * (hour - 6.0) / 12.0), 0.0, None)
    trans = np.ones(len(index))
    cloud_p = cfg.pv_cloud_prob_per_hr * ts_hours
    step_minutes = max(ts_hours * 60.0, 1e-9)
    cloud_duration_ticks = max(1, int(round(cfg.pv_cloud_duration_min / step_minutes)))
    chase_alpha = _scaled_alpha(0.7, ts_hours)
    recover_alpha = _scaled_alpha(0.3, ts_hours)
    if scenario == 'cloud_edge':
        cloud_p *= 1.8
    elif scenario == 'load_step':
        cloud_p *= 0.6
    target = 1.0
    remaining = 0
    for t in range(len(index)):
        if daylight[t] <= 0:
            trans[t] = 0.0
            target = 1.0
            remaining = 0
            continue
        if remaining <= 0 and rng.random() < cloud_p:
            target = rng.uniform(cfg.pv_cloud_target_min, cfg.pv_cloud_target_max)
            remaining = int(rng.integers(1, cloud_duration_ticks + 1))
        if remaining > 0:
            trans[t] = trans[t - 1] + chase_alpha * (target - trans[t - 1]) if t > 0 else target
            remaining -= 1
        else:
            prev = trans[t - 1] if t > 0 else 1.0
            trans[t] = prev + recover_alpha * (1.0 - prev)
        trans[t] = float(np.clip(trans[t], cfg.pv_cloud_target_min, 1.0))
    pv = cfg.pv_peak_kw * daylight * trans
    pv += rng.normal(0.0, 0.6, len(index))
    return np.clip(pv, 0.0, None)


def _wind_profile(index: pd.DatetimeIndex, cfg: SyntheticConfig, rng: np.random.Generator, scenario: str, ts_hours: float) -> np.ndarray:
    n = len(index)
    wind = np.zeros(n)
    gust_p = cfg.wind_gust_prob_per_hr * ts_hours
    ar_coef = _scaled_decay(cfg.wind_ar_coef, ts_hours)
    gust_decay = _scaled_decay(0.90, ts_hours)
    if scenario == 'wind_gust':
        gust_p *= 2.0
    elif scenario == 'cloud_edge':
        gust_p *= 0.9
    state = cfg.wind_base_kw
    gust = 0.0
    for t in range(n):
        noise = rng.normal(0.0, cfg.wind_noise_std_kw)
        state = ar_coef * state + (1.0 - ar_coef) * cfg.wind_base_kw + noise
        if rng.random() < gust_p:
            gust += rng.uniform(*cfg.wind_gust_range_kw)
        gust *= gust_decay
        wind[t] = max(0.0, state + gust)
    return wind


def _load_profile(index: pd.DatetimeIndex, cfg: SyntheticConfig, rng: np.random.Generator, scenario: str, ts_hours: float) -> np.ndarray:
    hour = index.hour + index.minute / 60.0
    daily = cfg.load_base_kw + cfg.load_daily_amp_kw * np.sin(2 * np.pi * (hour - 8.0) / 24.0)
    load = daily + rng.normal(0.0, cfg.load_noise_std_kw, len(index))
    prob = cfg.load_step_prob_per_hr
    if scenario == 'load_step':
        prob *= 2.0
    elif scenario == 'wind_gust':
        prob *= 0.8
    load = _inject_step_events(load, rng, prob, cfg.load_step_range_kw, ts_hours)
    return np.clip(load, 5.0, None)


def generate_profile(seed: int, scenario: str, site: SiteConfig, synth: SyntheticConfig) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = int(round(synth.hours / site.ts_hours))
    step_seconds = max(1, int(round(site.ts_hours * 3600.0)))
    index = pd.date_range('2026-01-01', periods=n, freq=pd.to_timedelta(step_seconds, unit='s'))
    load = _load_profile(index, synth, rng, scenario, site.ts_hours)
    pv = _pv_profile(index, synth, rng, scenario, site.ts_hours)
    wind = _wind_profile(index, synth, rng, scenario, site.ts_hours)
    base = load - (pv + wind)
    peak_flag = time_of_use_peak_flag(index)
    df = pd.DataFrame({
        'timestamp': index,
        'load_kw': load,
        'pv_kw': pv,
        'wind_kw': wind,
        'base_kw': base,
        'peak_flag': peak_flag,
        'scenario': scenario,
        'seed': seed,
        'scenario_seed': scenario_seed_id(scenario, seed),
    })
    df['day_id'] = (np.arange(len(df)) // int(round(24 / site.ts_hours))).astype(int)
    return df


def generate_dataset(seeds: Iterable[int], site: SiteConfig, synth: SyntheticConfig) -> pd.DataFrame:
    frames = [generate_profile(seed, scenario, site, synth) for scenario in synth.scenario_names for seed in seeds]
    return pd.concat(frames, ignore_index=True)
