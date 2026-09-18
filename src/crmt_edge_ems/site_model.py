from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from jer_microgrid.config import SiteConfig
from .temporal import derive_temporal_mapping

OPENCEM_INVERTER_RATED_KW = 8.0
OPENCEM_BATTERY_AH = 200.0
OPENCEM_BATTERY_NOMINAL_V = 51.2
OPENCEM_BATTERY_NOMINAL_KWH = OPENCEM_BATTERY_AH * OPENCEM_BATTERY_NOMINAL_V / 1000.0
OPENCEM_PV_PANELS = 26
OPENCEM_PV_PANEL_W = 480.0
OPENCEM_PV_NAMEPLATE_KWP = OPENCEM_PV_PANELS * OPENCEM_PV_PANEL_W / 1000.0

@dataclass(frozen=True)
class GridCapCalibration:
    import_quantile: float
    export_quantile: float
    import_cap_kw: float
    export_cap_kw: float
    n_import_samples: int
    n_export_samples: int

@dataclass(frozen=True)
class OpenCEMSubsystemAssumptions:
    battery_power_limit_kw: float
    eta_ch: float
    eta_dis: float
    soc_min: float
    soc_max: float
    soc_init: float
    command_ramp_kw_per_min: float
    import_cap_kw: float
    export_cap_kw: float
    def validate(self)->None:
        if not (0.0 < self.battery_power_limit_kw <= OPENCEM_INVERTER_RATED_KW): raise ValueError("battery_power_limit_kw must be in (0, inverter rated kW]")
        if not (0.0 < self.eta_ch <= 1.0 and 0.0 < self.eta_dis <= 1.0): raise ValueError("eta_ch and eta_dis must be in (0,1]")
        if not (0.0 <= self.soc_min < self.soc_init < self.soc_max <= 1.0): raise ValueError("Require 0 <= soc_min < soc_init < soc_max <= 1")
        if self.command_ramp_kw_per_tick <= 0.0: raise ValueError("command_ramp_kw_per_tick must be > 0")
        if self.import_cap_kw <= 0.0 or self.export_cap_kw <= 0.0: raise ValueError("import/export caps must be > 0")

def build_opencem_subsystem_site(
    assumptions: OpenCEMSubsystemAssumptions,
    *,
    cadence_minutes: int = 1,
) -> SiteConfig:
    """Build a per-subsystem SiteConfig with cadence-aware temporal semantics."""
    assumptions.validate()
    temporal = derive_temporal_mapping(
        cadence_minutes,
        base_r_max_kw_per_tick=float(assumptions.command_ramp_kw_per_min),
    )
    return SiteConfig(
        ts_hours=temporal.ts_hours,
        p_dis_max=float(assumptions.battery_power_limit_kw),
        p_ch_max=float(assumptions.battery_power_limit_kw),
        e_nom_kwh=float(OPENCEM_BATTERY_NOMINAL_KWH),
        eta_ch=float(assumptions.eta_ch),
        eta_dis=float(assumptions.eta_dis),
        soc_min=float(assumptions.soc_min),
        soc_max=float(assumptions.soc_max),
        soc_init=float(assumptions.soc_init),
        r_max_kw_per_tick=temporal.r_max_kw_per_tick,
        t_min_ticks=temporal.t_min_ticks,
        w_f=temporal.w_f_ticks,
        horizon_k=temporal.horizon_k_ticks,
        d_lim=temporal.d_lim_kw_per_tick,
        fbrl_ema_beta_override=temporal.ema_beta,
        proposed_cap_fix_hold_ticks_override=temporal.cap_fix_hold_ticks,
        proposed_prep_hold_ticks_override=temporal.prep_hold_ticks,
        proposed_near_cap_window_ticks_override=temporal.near_cap_window_ticks,
        proposed_hold_decay_override=temporal.hold_decay_per_tick,
        soc_low_thresh=float(assumptions.soc_min),
        soc_high_thresh=float(assumptions.soc_max),
        p_imp_contr=float(assumptions.import_cap_kw),
        p_exp_phys=float(assumptions.export_cap_kw),
        p_imp_peakcap=float(assumptions.import_cap_kw),
        p_imp_offcap=float(assumptions.import_cap_kw),
        p_exp_peakcap=float(assumptions.export_cap_kw),
        p_exp_offcap=float(assumptions.export_cap_kw),
    )


def calibrate_train_grid_caps(train_profiles: Iterable[pd.DataFrame],*,import_quantile:float=0.90,export_quantile:float=0.90,min_samples_each_direction:int=100)->GridCapCalibration:
    if not (0.5 <= import_quantile < 1.0 and 0.5 <= export_quantile < 1.0): raise ValueError("cap quantiles must be in [0.5, 1)")
    if min_samples_each_direction < 1: raise ValueError("min_samples_each_direction must be >= 1")
    arrays=[]
    for p in train_profiles:
        if "base_kw" not in p.columns: raise KeyError("all train profiles must contain base_kw")
        x=pd.to_numeric(p["base_kw"],errors="coerce").to_numpy(dtype=float); arrays.append(x[np.isfinite(x)])
    if not arrays: raise ValueError("no train profiles supplied")
    x=np.concatenate(arrays); imp=x[x>0.0]; exp=-x[x<0.0]
    if imp.size < min_samples_each_direction: raise ValueError(f"insufficient import samples for cap calibration: {imp.size}")
    if exp.size < min_samples_each_direction: raise ValueError(f"insufficient export samples for cap calibration: {exp.size}")
    return GridCapCalibration(float(import_quantile),float(export_quantile),float(np.quantile(imp,import_quantile)),float(np.quantile(exp,export_quantile)),int(imp.size),int(exp.size))
