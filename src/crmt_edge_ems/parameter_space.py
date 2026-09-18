from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np

from jer_microgrid.config import SiteConfig
from jer_microgrid.controllers import ProposedController


PARAMETERIZATION_VERSION = "normalized-v1"


@dataclass(frozen=True)
class ParamSpec:
    name: str
    lower: float
    upper: float

    def decode(self, u: float) -> float:
        u = float(np.clip(u, 0.0, 1.0))
        return self.lower + u * (self.upper - self.lower)

    def encode(self, x: float) -> float:
        if self.upper <= self.lower:
            raise ValueError(f"Invalid bounds for {self.name}")
        return float(np.clip((x - self.lower) / (self.upper - self.lower), 0.0, 1.0))


PARAM_SPECS: tuple[ParamSpec, ...] = (
    ParamSpec("base_soft_low", 0.24, 0.42),
    ParamSpec("base_soft_high", 0.58, 0.76),
    ParamSpec("prep_power_cap_frac", 0.02, 0.20),
    ParamSpec("lookahead_gain", 0.0, 0.08),
    ParamSpec("reserve_enter_margin", 0.0, 0.05),
    ParamSpec("reserve_exit_margin", 0.0, 0.04),
    ParamSpec("hold_decay", 0.35, 0.85),
    ParamSpec("near_cap_forecast_buffer_frac", 0.01, 0.10),
    ParamSpec("near_cap_soc_boost", 0.0, 0.08),
)
PARAM_NAMES: tuple[str, ...] = tuple(p.name for p in PARAM_SPECS)


def _battery_power_scale(site: SiteConfig) -> float:
    return max(1e-9, min(float(site.p_ch_max), float(site.p_dis_max)))


def _grid_cap_scale(site: SiteConfig) -> float:
    caps = [float(site.p_imp_peakcap), float(site.p_imp_offcap), float(site.p_exp_peakcap), float(site.p_exp_offcap)]
    positive = [x for x in caps if x > 0.0]
    return max(1e-9, min(positive) if positive else 1.0)


def decode_unit_vector(unit: Iterable[float]) -> dict[str, float]:
    values = np.asarray(list(unit), dtype=float)
    if values.shape != (len(PARAM_SPECS),):
        raise ValueError(f"Expected {len(PARAM_SPECS)} parameters, got shape {values.shape}")
    return {spec.name: spec.decode(float(u)) for spec, u in zip(PARAM_SPECS, values)}


def encode_physical(params: Mapping[str, float]) -> np.ndarray:
    return np.asarray([spec.encode(float(params[spec.name])) for spec in PARAM_SPECS], dtype=float)


def validate_physical(params: Mapping[str, float], site: SiteConfig | None = None) -> tuple[bool, tuple[str, ...]]:
    site = site or SiteConfig()
    errors: list[str] = []
    for spec in PARAM_SPECS:
        if spec.name not in params:
            errors.append(f"missing:{spec.name}")
            continue
        x = float(params[spec.name])
        if not (spec.lower <= x <= spec.upper):
            errors.append(f"out_of_bounds:{spec.name}")
    if errors:
        return False, tuple(errors)
    low = float(params["base_soft_low"]); high = float(params["base_soft_high"])
    if low < site.soc_min + 0.02: errors.append("soft_low_too_close_to_hard_soc_min")
    if high > site.soc_max - 0.02: errors.append("soft_high_too_close_to_hard_soc_max")
    if high - low < 0.12: errors.append("soft_reserve_band_too_narrow")
    if float(params["reserve_exit_margin"]) > float(params["reserve_enter_margin"]) + 1e-12:
        errors.append("reserve_exit_margin_exceeds_enter_margin")
    return len(errors) == 0, tuple(errors)


def build_tuned_controller(site: SiteConfig, params: Mapping[str, float]) -> ProposedController:
    ok, errors = validate_physical(params, site)
    if not ok: raise ValueError("Infeasible controller parameters: " + ", ".join(errors))
    ctrl = ProposedController(site)
    for name in ("base_soft_low","base_soft_high","lookahead_gain","reserve_enter_margin","reserve_exit_margin","hold_decay","near_cap_soc_boost"):
        setattr(ctrl, name, float(params[name]))
    ctrl.prep_power_cap_kw = float(params["prep_power_cap_frac"]) * _battery_power_scale(site)
    ctrl.near_cap_forecast_buffer_kw = float(params["near_cap_forecast_buffer_frac"]) * _grid_cap_scale(site)
    return ctrl


def fixed_controller_parameters(site: SiteConfig | None = None) -> dict[str, float]:
    site = site or SiteConfig(); ctrl = ProposedController(site)
    return {"base_soft_low":float(ctrl.base_soft_low),"base_soft_high":float(ctrl.base_soft_high),"prep_power_cap_frac":float(ctrl.prep_power_cap_kw)/_battery_power_scale(site),"lookahead_gain":float(ctrl.lookahead_gain),"reserve_enter_margin":float(ctrl.reserve_enter_margin),"reserve_exit_margin":float(ctrl.reserve_exit_margin),"hold_decay":float(ctrl.hold_decay),"near_cap_forecast_buffer_frac":float(ctrl.near_cap_forecast_buffer_kw)/_grid_cap_scale(site),"near_cap_soc_boost":float(ctrl.near_cap_soc_boost)}


def repair_unit_vector(unit: Iterable[float], site: SiteConfig | None = None) -> np.ndarray:
    site = site or SiteConfig(); u=np.clip(np.asarray(list(unit),dtype=float),0.0,1.0)
    if u.shape != (len(PARAM_SPECS),): raise ValueError(f"Expected {len(PARAM_SPECS)} parameters, got shape {u.shape}")
    p=decode_unit_vector(u)
    low_spec=next(s for s in PARAM_SPECS if s.name=="base_soft_low"); high_spec=next(s for s in PARAM_SPECS if s.name=="base_soft_high")
    low=max(float(p["base_soft_low"]),float(site.soc_min)+0.02,low_spec.lower); high=min(float(p["base_soft_high"]),float(site.soc_max)-0.02,high_spec.upper)
    if high-low<0.12:
        midpoint=0.5*(low+high); low=max(low_spec.lower,float(site.soc_min)+0.02,midpoint-0.06); high=min(high_spec.upper,float(site.soc_max)-0.02,low+0.12)
        if high-low<0.12: high=min(high_spec.upper,float(site.soc_max)-0.02); low=high-0.12
    p["base_soft_low"]=low; p["base_soft_high"]=high; p["reserve_exit_margin"]=min(float(p["reserve_exit_margin"]),float(p["reserve_enter_margin"]))
    repaired=encode_physical(p); ok,errors=validate_physical(decode_unit_vector(repaired),site)
    if not ok: raise RuntimeError("Feasibility projection failed: "+", ".join(errors))
    return repaired
