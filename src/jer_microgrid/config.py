from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence


@dataclass
class SiteConfig:
    ts_hours: float = 1.0 / 60.0
    p_dis_max: float = 50.0
    p_ch_max: float = 50.0
    e_nom_kwh: float = 100.0
    eta_ch: float = 0.95
    eta_dis: float = 0.95
    soc_min: float = 0.20
    soc_max: float = 0.80
    soc_init: float = 0.50
    delta_s: float = 0.02
    r_max_kw_per_tick: float = 20.0
    t_min_ticks: int = 3
    h_rg_ticks: int = 10
    soc_high_thresh: float = 0.80
    soc_low_thresh: float = 0.20
    c_high: float = 0.50
    beta_dod: float = 2.0
    dmc: float = 0.02
    p_imp_contr: float = 40.0
    p_exp_phys: float = 40.0
    p_imp_peakcap: float = 40.0
    p_imp_offcap: float = 40.0
    p_exp_peakcap: float = 40.0
    p_exp_offcap: float = 40.0
    delta_imp: float = 0.0
    delta_exp: float = 0.0
    e_imp_on: float = 0.0
    e_imp_off: float = 0.0
    e_exp_on: float = 0.0
    e_exp_off: float = 0.0
    alpha: float = 0.30
    w_f: int = 5
    w_ema: int = 7
    horizon_k: int = 10
    d_lim: float = 8.0
    # Optional cadence-aware overrides. None preserves the frozen 1-minute behavior.
    fbrl_ema_beta_override: float | None = None
    proposed_cap_fix_hold_ticks_override: int | None = None
    proposed_prep_hold_ticks_override: int | None = None
    proposed_near_cap_window_ticks_override: int | None = None
    proposed_hold_decay_override: float | None = None
    ecrit_abs: float = 25.0
    gamma_crit: float = 0.20


@dataclass
class SyntheticConfig:
    hours: int = 24
    load_base_kw: float = 48.0
    load_daily_amp_kw: float = 12.0
    load_noise_std_kw: float = 2.5
    load_step_prob_per_hr: float = 0.30
    load_step_range_kw: tuple[float, float] = (-10.0, 14.0)
    pv_peak_kw: float = 45.0
    pv_cloud_prob_per_hr: float = 1.2
    pv_cloud_target_min: float = 0.20
    pv_cloud_target_max: float = 0.90
    pv_cloud_duration_min: int = 3
    wind_base_kw: float = 14.0
    wind_noise_std_kw: float = 2.5
    wind_gust_prob_per_hr: float = 0.7
    wind_gust_range_kw: tuple[float, float] = (8.0, 20.0)
    wind_ar_coef: float = 0.85
    scenario_names: Sequence[str] = field(default_factory=lambda: [
        'mixed', 'cloud_edge', 'wind_gust', 'load_step'
    ])


@dataclass
class OptimConfig:
    rho_imp: float = 1e4
    rho_exp: float = 1e4
    lambda_grid: Sequence[float] = field(default_factory=lambda: [1e-2, 1e-1, 1.0])
    mu_grid: Sequence[float] = field(default_factory=lambda: [1e-2])
    nu_grid: Sequence[float] = field(default_factory=lambda: [1e-3])
    soc_target: float = 0.50
    maxiter_qp: int = 120
    ftol_qp: float = 1e-6
    oracle_global_maxiter: int = 250
    enable_global_oracle: bool = False
    oracle_fallback_to_perfect_preview: bool = True


@dataclass
class ExperimentConfig:
    seeds: Sequence[int] = field(default_factory=lambda: list(range(5)))
    sensitivity_rmax: Sequence[float] = field(default_factory=lambda: [10.0, 15.0, 20.0, 25.0, 30.0])
    sensitivity_tmin: Sequence[int] = field(default_factory=lambda: [0, 1, 2, 3, 5])
    sensitivity_wf: Sequence[int] = field(default_factory=lambda: [3, 5, 7, 9])
    sensitivity_horizon: Sequence[int] = field(default_factory=lambda: [5, 10, 15])
    use_parallel: bool = True
    max_workers: int | None = None
    output_dir: str = 'outputs'
    representative_scenario: str = 'load_step'
    representative_seed: int = 0


PRIMARY_STRESS_METRICS: List[str] = [
    'throughput_kwh', 'efc', 'lfp_cycle_loss_pct', 't_high_soc_h', 'ceq_q95', 't_high_c_h', 'idod'
]

MAIN_METRICS: List[str] = [
    'ramp95_kw_per_min', 'cap_violation_pct_total', 'throughput_kwh', 'efc',
    'lfp_cycle_loss_pct', 't_high_soc_h', 'ceq_q95', 't_high_c_h', 'idod', 'n_micro', 'flip_per_day',
    'soc_band_residency'
]

CONTROLLERS_MAIN: List[str] = [
    'Proposed', 'NC', 'GR', 'RS', 'FBRL', 'MPC_best_ramp', 'MPC_best_balanced'
]

ABLATION_MAP = {
    'A0': 'full',
    'A1': 'no_forecast',
    'A2': 'no_lookahead',
    'A3': 'no_reserve_persistence',
    'A4': 'no_hysteresis_dwell',
    'A5': 'no_dynamic_reserve',
    'A6': 'no_reserve_correction',
}
