
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from jer_microgrid.config import SiteConfig
from jer_microgrid.utils import clip


@dataclass
class ControllerState:
    mode: str = 'IDLE'
    rg_state: str = 'MID'
    dwell: int = 1
    prev_cmd: float = 0.0


class ControllerBase:
    name: str = 'BASE'

    def __init__(self, site: SiteConfig):
        self.site = site
        self.reset()

    def reset(self):
        self.state = ControllerState()

    def step(self, t: int, history_base: np.ndarray, soc: float, peak_flag: int) -> tuple[float, dict[str, Any]]:
        raise NotImplementedError


class NoControlController(ControllerBase):
    name = 'NC'

    def step(self, t, history_base, soc, peak_flag):
        debug = {
            'mode': 'IDLE',
            'rg_state': 'MID',
            'desired_kw': 0.0,
            'p_imp_cap': self.site.p_imp_contr,
            'p_exp_cap': self.site.p_exp_phys,
        }
        self.state.prev_cmd = 0.0
        self.state.mode = 'IDLE'
        return 0.0, debug


class GreedyRuleController(ControllerBase):
    name = 'GR'

    def step(self, t, history_base, soc, peak_flag):
        base = float(history_base[-1])
        p_imp_cap, p_exp_cap = compute_caps(peak_flag, self.site)
        pmin, pmax = compute_hard_bounds(soc, self.site)
        prev = self.state.prev_cmd
        if soc <= self.site.soc_min + self.site.delta_s:
            desired = -min(self.site.p_ch_max, -pmin)
            mode = 'RG'
            rg = 'LOW'
        elif soc >= self.site.soc_max - self.site.delta_s:
            desired = min(self.site.p_dis_max, pmax)
            mode = 'RG'
            rg = 'HIGH'
        elif base > p_imp_cap:
            desired = min(base - p_imp_cap, pmax)
            mode = 'PS'
            rg = 'MID'
        elif -base > p_exp_cap:
            desired = -min(-base - p_exp_cap, -pmin)
            mode = 'VF'
            rg = 'MID'
        else:
            desired = 0.0
            mode = 'RG'
            rg = 'MID'
        cmd = clip(desired, max(pmin, prev - self.site.r_max_kw_per_tick), min(pmax, prev + self.site.r_max_kw_per_tick))
        self.state.prev_cmd = float(cmd)
        self.state.mode = mode
        self.state.rg_state = rg
        return float(cmd), {
            'mode': mode,
            'rg_state': rg,
            'desired_kw': float(desired),
            'p_imp_cap': p_imp_cap,
            'p_exp_cap': p_exp_cap,
        }


class ReactiveSmoothingController(ControllerBase):
    name = 'RS'

    def step(self, t, history_base, soc, peak_flag):
        base = float(history_base[-1])
        p_imp_cap, p_exp_cap = compute_caps(peak_flag, self.site)
        pmin, pmax = compute_hard_bounds(soc, self.site)
        prev = self.state.prev_cmd
        ref = np.mean(history_base[max(0, len(history_base) - self.site.w_f):])
        desired = base - ref
        cmd = clip(desired, max(pmin, prev - self.site.r_max_kw_per_tick), min(pmax, prev + self.site.r_max_kw_per_tick))
        mode = 'PS' if cmd > 0 else ('VF' if cmd < 0 else 'RG')
        self.state.prev_cmd = float(cmd)
        self.state.mode = mode
        self.state.rg_state = 'MID'
        return float(cmd), {
            'mode': mode,
            'rg_state': 'MID',
            'desired_kw': float(desired),
            'p_imp_cap': p_imp_cap,
            'p_exp_cap': p_exp_cap,
        }


class FilterBasedReferenceShapingController(ControllerBase):
    name = 'FBRL'

    def reset(self):
        super().reset()
        self.ema_ref = None

    def step(self, t, history_base, soc, peak_flag):
        base = float(history_base[-1])
        p_imp_cap, p_exp_cap = compute_caps(peak_flag, self.site)
        pmin, pmax = compute_hard_bounds(soc, self.site)
        prev = self.state.prev_cmd
        beta = 2.0 / (self.site.w_ema + 1.0)
        if self.ema_ref is None:
            self.ema_ref = base
        self.ema_ref = beta * base + (1.0 - beta) * self.ema_ref
        ref_cap = clip(self.ema_ref, -p_exp_cap, p_imp_cap)
        desired = base - ref_cap
        cmd = clip(desired, max(pmin, prev - self.site.r_max_kw_per_tick), min(pmax, prev + self.site.r_max_kw_per_tick))
        mode = 'PS' if cmd > 0 else ('VF' if cmd < 0 else 'RG')
        self.state.prev_cmd = float(cmd)
        self.state.mode = mode
        self.state.rg_state = 'MID'
        return float(cmd), {
            'mode': mode,
            'rg_state': 'MID',
            'desired_kw': float(desired),
            'p_imp_cap': p_imp_cap,
            'p_exp_cap': p_exp_cap,
            'ema_ref_kw': float(self.ema_ref),
        }


class ProposedController(ControllerBase):
    """
    v6 balanced candidate.

    Relative to v5:
    - keeps the strict current cap-fix priority,
    - retains short action-hold logic to reduce one-tick mode chatter,
    - adds proximity-aware reserve shaping so near-cap forecast windows
      can trigger small preparation actions before a hard violation,
    - keeps the reserve behavior soft enough to avoid reverting to the
      high-throughput variants explored during tuning.
    """

    name = 'Proposed'

    def __init__(
        self,
        site: SiteConfig,
        *,
        no_forecast: bool = False,
        no_lookahead: bool = False,
        no_reserve_persistence: bool = False,
        no_hysteresis_dwell: bool = False,
        no_dynamic_reserve: bool = False,
        no_reserve_correction: bool = False,
    ):
        self.no_forecast = no_forecast
        self.no_lookahead = no_lookahead
        self.no_reserve_persistence = no_reserve_persistence
        self.no_hysteresis_dwell = no_hysteresis_dwell
        self.no_dynamic_reserve = no_dynamic_reserve
        self.no_reserve_correction = no_reserve_correction
        super().__init__(site)

        self.base_soft_low = 0.32
        self.base_soft_high = 0.62
        self.min_useful_cmd_kw = 0.25
        self.prep_power_cap_kw = 4.0
        self.lookahead_gain = 0.01

        # Slightly wider reserve hysteresis than v4.
        self.reserve_enter_margin = 0.02
        self.reserve_exit_margin = 0.01

        # Action-hold logic is anchored to the site-level minimum dwell time
        # so t_min_ticks is a real behavioral control rather than a dead knob.
        self.cap_fix_hold_ticks = max(1, int(site.t_min_ticks))
        self.prep_hold_ticks = max(self.cap_fix_hold_ticks + 2, int(site.t_min_ticks))
        self.near_cap_margin_kw = 0.8
        self.hold_decay = 0.60

        # Slightly softer reserve shaping than v4.
        self.prep_slack_gain = 0.70
        self.prep_slack_offset = 0.40
        self.near_cap_forecast_buffer_kw = 1.5
        self.near_cap_soc_boost = 0.03
        self.near_cap_prep_slack_kw = 1.2

    def step(self, t, history_base, soc, peak_flag):
        s = self.site
        prev_cmd = float(self.state.prev_cmd)
        prev_mode = self.state.mode
        prev_dwell = self.state.dwell
        reserve_enter_margin = 0.0 if self.no_hysteresis_dwell else self.reserve_enter_margin
        reserve_exit_margin = 0.0 if self.no_hysteresis_dwell else self.reserve_exit_margin
        cap_fix_hold_ticks = 0 if self.no_hysteresis_dwell else self.cap_fix_hold_ticks
        prep_hold_ticks = 0 if self.no_hysteresis_dwell else self.prep_hold_ticks

        base_now = float(history_base[-1])
        p_imp_cap, p_exp_cap = compute_caps(peak_flag, s)
        pmin, pmax = compute_hard_bounds(soc, s)
        hard_lo = max(pmin, prev_cmd - s.r_max_kw_per_tick)
        hard_hi = min(pmax, prev_cmd + s.r_max_kw_per_tick)

        forecast = forecast_base(history_base, s, no_forecast=self.no_forecast)
        imp_vec = np.maximum(0.0, forecast - p_imp_cap)
        exp_vec = np.maximum(0.0, -forecast - p_exp_cap)
        forecast_window = forecast[: min(3, forecast.size)] if forecast.size else forecast
        near_imp_signal = max(
            0.0,
            float(np.max(forecast_window)) - (p_imp_cap - self.near_cap_forecast_buffer_kw)
        ) if forecast_window.size else 0.0
        near_exp_signal = max(
            0.0,
            (-float(np.min(forecast_window))) - (p_exp_cap - self.near_cap_forecast_buffer_kw)
        ) if forecast_window.size else 0.0

        e_now_imp = max(0.0, base_now - p_imp_cap)
        e_now_exp = max(0.0, -base_now - p_exp_cap)
        e_peak_imp = max(e_now_imp, float(np.max(imp_vec)) if imp_vec.size else 0.0)
        e_peak_exp = max(e_now_exp, float(np.max(exp_vec)) if exp_vec.size else 0.0)
        reserve_need_imp = e_peak_imp >= s.e_imp_on
        reserve_need_exp = e_peak_exp >= s.e_exp_on
        reserve_hold_imp = e_peak_imp >= s.e_imp_off
        reserve_hold_exp = e_peak_exp >= s.e_exp_off

        if self.no_dynamic_reserve:
            reserve_low = self.base_soft_low
            reserve_high = self.base_soft_high
        else:
            reserve_low = float(np.clip(
                self.base_soft_low + 0.10 * min(1.0, e_peak_imp / max(p_imp_cap, 1.0)),
                self.base_soft_low,
                0.54,
            ))
            reserve_high = float(np.clip(
                self.base_soft_high - 0.06 * min(1.0, e_peak_exp / max(p_exp_cap, 1.0)),
                0.50,
                self.base_soft_high,
            ))
            reserve_low = float(np.clip(
                reserve_low + self.near_cap_soc_boost * min(1.0, near_imp_signal / max(self.near_cap_forecast_buffer_kw, 1e-9)),
                self.base_soft_low,
                0.58,
            ))
            reserve_high = float(np.clip(
                reserve_high - self.near_cap_soc_boost * min(1.0, near_exp_signal / max(self.near_cap_forecast_buffer_kw, 1e-9)),
                0.46,
                self.base_soft_high,
            ))

        imp_slack = max(0.0, p_imp_cap - base_now)
        exp_slack = max(0.0, p_exp_cap + base_now)

        desired = 0.0
        cmd = 0.0
        mode = 'IDLE'

        # 1) Current cap-fix has strict priority.
        if e_now_imp > 0.0:
            extra = 0.0 if self.no_lookahead else self.lookahead_gain * max(0.0, e_peak_imp - e_now_imp)
            desired = min(pmax, e_now_imp + extra)
            cmd = clip(desired, hard_lo, hard_hi)
            mode = 'PS' if cmd > 0.0 else 'IDLE'

        elif e_now_exp > 0.0:
            extra = 0.0 if self.no_lookahead else self.lookahead_gain * max(0.0, e_peak_exp - e_now_exp)
            desired = max(pmin, -(e_now_exp + extra))
            cmd = clip(desired, hard_lo, hard_hi)
            mode = 'VF' if cmd < 0.0 else 'IDLE'

        else:
            persistent_prep_ch = (
                (not self.no_reserve_persistence)
                and prev_mode == 'PREP_CH'
                and reserve_hold_imp
                and soc < reserve_low - reserve_exit_margin
                and imp_slack > 0.8
                and pmin < 0.0
            )
            persistent_prep_dis = (
                (not self.no_reserve_persistence)
                and prev_mode == 'PREP_DIS'
                and reserve_hold_exp
                and soc > reserve_high + reserve_exit_margin
                and exp_slack > 0.8
                and pmax > 0.0
            )

            enter_prep_ch = (
                (not self.no_reserve_correction)
                and (reserve_need_imp or near_imp_signal > 0.0)
                and soc < reserve_low - reserve_enter_margin
                and imp_slack > (self.near_cap_prep_slack_kw if near_imp_signal > 0.0 else 1.5)
                and pmin < 0.0
            )
            enter_prep_dis = (
                (not self.no_reserve_correction)
                and (reserve_need_exp or near_exp_signal > 0.0)
                and soc > reserve_high + reserve_enter_margin
                and exp_slack > (self.near_cap_prep_slack_kw if near_exp_signal > 0.0 else 1.5)
                and pmax > 0.0
            )

            if persistent_prep_ch or enter_prep_ch:
                desired = max(
                    pmin,
                    -min(self.prep_power_cap_kw, self.prep_slack_gain * max(0.0, imp_slack - self.prep_slack_offset)),
                )
                cmd = clip(desired, hard_lo, hard_hi)
                mode = 'PREP_CH' if cmd < 0.0 else 'IDLE'

            elif persistent_prep_dis or enter_prep_dis:
                desired = min(
                    pmax,
                    min(self.prep_power_cap_kw, self.prep_slack_gain * max(0.0, exp_slack - self.prep_slack_offset)),
                )
                cmd = clip(desired, hard_lo, hard_hi)
                mode = 'PREP_DIS' if cmd > 0.0 else 'IDLE'

            # Short action-hold logic: reduce mode chatter without forcing
            # long persistence.
            if prev_mode == 'PS' and mode == 'IDLE' and prev_dwell < cap_fix_hold_ticks:
                near_imp_cap = bool(forecast.size) and float(np.max(forecast[: min(3, forecast.size)])) > (p_imp_cap - self.near_cap_margin_kw)
                if near_imp_cap:
                    desired = max(0.0, prev_cmd * self.hold_decay)
                    cmd = clip(desired, hard_lo, hard_hi)
                    mode = 'PS' if cmd > 0.0 else 'IDLE'

            elif prev_mode == 'VF' and mode == 'IDLE' and prev_dwell < cap_fix_hold_ticks:
                near_exp_cap = bool(forecast.size) and float(np.min(forecast[: min(3, forecast.size)])) < (-p_exp_cap + self.near_cap_margin_kw)
                if near_exp_cap:
                    desired = min(0.0, prev_cmd * self.hold_decay)
                    cmd = clip(desired, hard_lo, hard_hi)
                    mode = 'VF' if cmd < 0.0 else 'IDLE'

            elif prev_mode == 'PREP_CH' and mode == 'IDLE' and prev_dwell < prep_hold_ticks:
                if reserve_hold_imp and soc < reserve_low and imp_slack > 0.6:
                    desired = max(pmin, prev_cmd * self.hold_decay)
                    cmd = clip(desired, hard_lo, hard_hi)
                    mode = 'PREP_CH' if cmd < -self.min_useful_cmd_kw else 'IDLE'

            elif prev_mode == 'PREP_DIS' and mode == 'IDLE' and prev_dwell < prep_hold_ticks:
                if reserve_hold_exp and soc > reserve_high and exp_slack > 0.6:
                    desired = min(pmax, prev_cmd * self.hold_decay)
                    cmd = clip(desired, hard_lo, hard_hi)
                    mode = 'PREP_DIS' if cmd > self.min_useful_cmd_kw else 'IDLE'

            if abs(cmd) < self.min_useful_cmd_kw:
                cmd = 0.0
                desired = 0.0
                mode = 'IDLE'

        dwell = prev_dwell + 1 if mode == prev_mode else 1
        rg_state = 'LOW' if soc < reserve_low else ('HIGH' if soc > reserve_high else 'MID')
        self.state = ControllerState(mode=mode, rg_state=rg_state, dwell=dwell, prev_cmd=float(cmd))

        return float(cmd), {
            'mode': mode,
            'rg_state': rg_state,
            'desired_kw': float(desired),
            'p_imp_cap': float(p_imp_cap),
            'p_exp_cap': float(p_exp_cap),
            'e_imp': float(e_peak_imp),
            'e_exp': float(e_peak_exp),
            'e1_imp': float(e_now_imp),
            'e1_exp': float(e_now_exp),
            'near_imp_signal': float(near_imp_signal),
            'near_exp_signal': float(near_exp_signal),
        }


def compute_caps(peak_flag: int, site: SiteConfig) -> tuple[float, float]:
    p_imp = max(0.0, min(site.p_imp_contr, peak_flag * site.p_imp_peakcap + (1 - peak_flag) * site.p_imp_offcap) - site.delta_imp)
    p_exp = max(0.0, min(site.p_exp_phys, peak_flag * site.p_exp_peakcap + (1 - peak_flag) * site.p_exp_offcap) - site.delta_exp)
    return float(p_imp), float(p_exp)


def compute_hard_bounds(soc: float, site: SiteConfig) -> tuple[float, float]:
    p_dis_soc = max(0.0, (soc - site.soc_min) * site.e_nom_kwh * site.eta_dis / site.ts_hours)
    p_ch_soc = max(0.0, (site.soc_max - soc) * site.e_nom_kwh / (site.eta_ch * site.ts_hours))
    pmax = min(site.p_dis_max, p_dis_soc)
    pmin = -min(site.p_ch_max, p_ch_soc)
    return float(pmin), float(pmax)


def forecast_base(history_base: np.ndarray, site: SiteConfig, *, no_forecast: bool = False) -> np.ndarray:
    cur = float(history_base[-1])
    if no_forecast or history_base.size < 2:
        return np.full(site.horizon_k, cur, dtype=float)
    wf = min(site.w_f, history_base.size)
    recent = history_base[-wf:]
    delta = np.diff(history_base[-(wf + 1):]) if history_base.size >= wf + 1 else np.diff(history_base)
    tau = float(np.mean(delta)) if delta.size else 0.0
    tau_sat = float(clip(tau, -site.d_lim, site.d_lim))
    ma = float(np.mean(recent))
    base0 = site.alpha * cur + (1.0 - site.alpha) * ma
    return np.array([base0 + (k + 1) * tau_sat for k in range(site.horizon_k)], dtype=float)


def build_controller(name: str, site: SiteConfig) -> ControllerBase:
    name = name.strip()
    if name == 'NC':
        return NoControlController(site)
    if name == 'GR':
        return GreedyRuleController(site)
    if name == 'RS':
        return ReactiveSmoothingController(site)
    if name == 'FBRL':
        return FilterBasedReferenceShapingController(site)
    if name in {'Proposed', 'A0'}:
        return ProposedController(site)
    if name == 'A1':
        return ProposedController(site, no_forecast=True)
    if name == 'A2':
        return ProposedController(site, no_lookahead=True)
    if name == 'A3':
        return ProposedController(site, no_reserve_persistence=True)
    if name == 'A4':
        return ProposedController(site, no_hysteresis_dwell=True)
    if name == 'A5':
        return ProposedController(site, no_dynamic_reserve=True)
    if name == 'A6':
        return ProposedController(site, no_reserve_correction=True)
    raise ValueError(f'Unknown controller: {name}')


def get_proposed_controller_params(site: SiteConfig) -> dict[str, float | int | bool]:
    ctrl = ProposedController(site)
    return {
        'base_soft_low': float(ctrl.base_soft_low),
        'base_soft_high': float(ctrl.base_soft_high),
        'min_useful_cmd_kw': float(ctrl.min_useful_cmd_kw),
        'prep_power_cap_kw': float(ctrl.prep_power_cap_kw),
        'lookahead_gain': float(ctrl.lookahead_gain),
        'reserve_enter_margin': float(ctrl.reserve_enter_margin),
        'reserve_exit_margin': float(ctrl.reserve_exit_margin),
        'cap_fix_hold_ticks': int(ctrl.cap_fix_hold_ticks),
        'prep_hold_ticks': int(ctrl.prep_hold_ticks),
        'near_cap_margin_kw': float(ctrl.near_cap_margin_kw),
        'hold_decay': float(ctrl.hold_decay),
        'prep_slack_gain': float(ctrl.prep_slack_gain),
        'prep_slack_offset': float(ctrl.prep_slack_offset),
        'near_cap_forecast_buffer_kw': float(ctrl.near_cap_forecast_buffer_kw),
        'near_cap_soc_boost': float(ctrl.near_cap_soc_boost),
        'near_cap_prep_slack_kw': float(ctrl.near_cap_prep_slack_kw),
        'no_forecast': bool(ctrl.no_forecast),
        'no_lookahead': bool(ctrl.no_lookahead),
        'no_reserve_persistence': bool(ctrl.no_reserve_persistence),
        'no_hysteresis_dwell': bool(ctrl.no_hysteresis_dwell),
        'no_dynamic_reserve': bool(ctrl.no_dynamic_reserve),
        'no_reserve_correction': bool(ctrl.no_reserve_correction),
    }
