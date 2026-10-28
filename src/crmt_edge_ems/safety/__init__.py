"""Scenario safety veto and opt-in process containment; no field certification."""
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
import math
import time

import numpy as np
import pandas as pd

from ..contracts import ContractError, finite_array, integer
from .process_supervisor import ControllerExecutionError, ProcessSupervisorConfig, SupervisorSession


class SafetyBlocked(RuntimeError):
    def __init__(self, codes, *, receipt=None):
        self.codes = tuple(codes)
        self.receipt = receipt
        super().__init__("SAFETY_VETO:" + ",".join(self.codes))


@dataclass(frozen=True)
class SafetyLimits:
    soc_min: float
    soc_max: float
    charge_kw: float
    discharge_kw: float
    energy_kwh: float
    eta_charge: float
    eta_discharge: float
    dt_hours: float
    import_kw: float
    export_kw: float
    ramp_kw_per_min: float
    max_switches: int
    step_timeout_seconds: float
    basis: str = "SCENARIO_ASSUMPTIONS_NOT_CERTIFIED"

    def __post_init__(self):
        finite_array([
            self.soc_min, self.soc_max, self.charge_kw, self.discharge_kw,
            self.energy_kwh, self.eta_charge, self.eta_discharge, self.dt_hours,
            self.import_kw, self.export_kw, self.ramp_kw_per_min,
            self.step_timeout_seconds], "safety limits", ndim=1)
        integer(self.max_switches, "max_switches")
        if (not 0 <= self.soc_min < self.soc_max <= 1
                or min(self.charge_kw, self.discharge_kw, self.import_kw,
                       self.export_kw, self.ramp_kw_per_min) < 0
                or min(self.energy_kwh, self.dt_hours, self.step_timeout_seconds) <= 0
                or not (0 < self.eta_charge <= 1 and 0 < self.eta_discharge <= 1)):
            raise ContractError("invalid scenario safety limits")
        if self.basis != "SCENARIO_ASSUMPTIONS_NOT_CERTIFIED":
            raise ContractError("no certified physical authority is installed")

    @classmethod
    def from_site(cls, site, *, max_switches=2 ** 31 - 1, step_timeout_seconds=10.0):
        """Scenario assumptions only; no independent hardware attestation."""
        from jer_microgrid.controllers import compute_caps
        validate_site(site)
        caps = [compute_caps(flag, site) for flag in (0, 1)]
        return cls(
            soc_min=site.soc_min, soc_max=site.soc_max,
            charge_kw=site.p_ch_max, discharge_kw=site.p_dis_max,
            energy_kwh=site.e_nom_kwh, eta_charge=site.eta_ch,
            eta_discharge=site.eta_dis, dt_hours=site.ts_hours,
            import_kw=max(c[0] for c in caps), export_kw=max(c[1] for c in caps),
            ramp_kw_per_min=site.r_max_kw_per_tick / (site.ts_hours * 60),
            max_switches=max_switches, step_timeout_seconds=step_timeout_seconds)

    def veto(self, *, soc, command_kw, base_kw, previous_command_kw=0.0,
             switches=0, elapsed_seconds=0.0, dynamic_import_cap_kw=None,
             dynamic_export_cap_kw=None):
        codes = []
        try:
            finite_array([soc, command_kw, base_kw, previous_command_kw,
                          elapsed_seconds], "telemetry", ndim=1)
            integer(switches, "switches")
        except (ContractError, TypeError, ValueError):
            return ("INVALID_OR_MISSING_TELEMETRY",)
        if elapsed_seconds < 0:
            codes.append("INVALID_ELAPSED_TIME")
        if dynamic_import_cap_kw is not None or dynamic_export_cap_kw is not None:
            if dynamic_import_cap_kw is None or dynamic_export_cap_kw is None:
                return ("INVALID_DYNAMIC_GRID_CAP",)
            try:
                caps = finite_array([dynamic_import_cap_kw, dynamic_export_cap_kw],
                                    "dynamic grid caps", ndim=1)
            except (ContractError, TypeError, ValueError):
                return ("INVALID_DYNAMIC_GRID_CAP",)
            if np.any(caps < 0):
                return ("INVALID_DYNAMIC_GRID_CAP",)
        else:
            caps = None
        if not self.soc_min <= soc <= self.soc_max:
            codes.append("SOC_OUT_OF_RANGE")
        if command_kw < -self.charge_kw or command_kw > self.discharge_kw:
            codes.append("INVERTER_POWER_LIMIT")
        next_soc = (soc - self.dt_hours * command_kw / (self.energy_kwh * self.eta_discharge)
                    if command_kw >= 0 else
                    soc - self.dt_hours * command_kw * self.eta_charge / self.energy_kwh)
        if not self.soc_min - 1e-12 <= next_soc <= self.soc_max + 1e-12:
            codes.append("SOC_TRANSITION_LIMIT")
        grid = base_kw - command_kw
        effective_import = min(self.import_kw, float(caps[0])) if caps is not None else self.import_kw
        effective_export = min(self.export_kw, float(caps[1])) if caps is not None else self.export_kw
        if grid > effective_import + 1e-12 or grid < -effective_export - 1e-12:
            codes.append("GRID_LIMIT")
        if abs(command_kw - previous_command_kw) > self.ramp_kw_per_min * self.dt_hours * 60 + 1e-12:
            codes.append("COMMAND_RAMP_LIMIT")
        if switches > self.max_switches:
            codes.append("SWITCH_LIMIT")
        if elapsed_seconds > self.step_timeout_seconds:
            codes.append("STEP_TIMEOUT")
        return tuple(codes)


def validate_site(site):
    """Validate physical assumptions before budget reservation or controller calls."""
    names = (
        "ts_hours", "p_dis_max", "p_ch_max", "e_nom_kwh", "eta_ch", "eta_dis",
        "soc_min", "soc_max", "soc_init", "r_max_kw_per_tick", "p_imp_contr",
        "p_exp_phys", "p_imp_peakcap", "p_imp_offcap", "p_exp_peakcap",
        "p_exp_offcap", "delta_imp", "delta_exp")
    try:
        values = {name: getattr(site, name) for name in names}
        finite_array(list(values.values()), "site physical assumptions", ndim=1)
    except (AttributeError, TypeError, ValueError) as exc:
        raise SafetyBlocked(("INVALID_SITE_CONFIG",)) from exc
    if (site.ts_hours <= 0 or site.e_nom_kwh <= 0
            or not 0 < site.eta_ch <= 1 or not 0 < site.eta_dis <= 1
            or not 0 <= site.soc_min < site.soc_max <= 1
            or not site.soc_min <= site.soc_init <= site.soc_max
            or min(values[name] for name in (
                "p_dis_max", "p_ch_max", "r_max_kw_per_tick", "p_imp_contr",
                "p_exp_phys", "p_imp_peakcap", "p_imp_offcap", "p_exp_peakcap",
                "p_exp_offcap", "delta_imp", "delta_exp")) < 0):
        raise SafetyBlocked(("INVALID_SITE_CONFIG",))
    return site


def validate_simulation_inputs(profile, site, limits):
    """Pure preflight, shared by the strict evaluator and the checked simulator."""
    from jer_microgrid.controllers import compute_caps
    validate_site(site)
    if not isinstance(limits, SafetyLimits):
        raise SafetyBlocked(("INVALID_SAFETY_LIMITS",))
    required = {"timestamp", "base_kw", "peak_flag"}
    if not isinstance(profile, pd.DataFrame) or not required <= set(profile) or profile.empty:
        raise SafetyBlocked(("PROFILE_SCHEMA",))
    try:
        ts = pd.DatetimeIndex(profile["timestamp"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise SafetyBlocked(("PROFILE_TIME_SUPPORT",)) from exc
    if ts.tz is None or ts.hasnans or ts.has_duplicates or not ts.is_monotonic_increasing:
        raise SafetyBlocked(("PROFILE_TIME_SUPPORT",))
    if len(ts) > 1 and not np.allclose(
            np.diff(ts.as_unit("ns").asi8) / 3.6e12,
            limits.dt_hours, atol=1e-12, rtol=0):
        raise SafetyBlocked(("PROFILE_CADENCE",))
    base = finite_array(profile["base_kw"].to_numpy(), "base", ndim=1)
    peak = finite_array(profile["peak_flag"].to_numpy(), "peak", ndim=1)
    if not np.isin(peak, [0, 1]).all():
        raise SafetyBlocked(("PROFILE_PEAK_FLAG",))
    pairs = ((site.e_nom_kwh, limits.energy_kwh), (site.ts_hours, limits.dt_hours),
             (site.eta_ch, limits.eta_charge), (site.eta_dis, limits.eta_discharge))
    if any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-12) for a, b in pairs):
        raise SafetyBlocked(("SITE_LIMIT_MISMATCH",))
    if (limits.soc_min < site.soc_min - 1e-12
            or limits.soc_max > site.soc_max + 1e-12
            or limits.charge_kw > site.p_ch_max + 1e-12
            or limits.discharge_kw > site.p_dis_max + 1e-12
            or limits.ramp_kw_per_min * limits.dt_hours * 60 > site.r_max_kw_per_tick + 1e-12):
        raise SafetyBlocked(("SITE_LIMIT_MISMATCH",))
    if not limits.soc_min <= site.soc_init <= limits.soc_max:
        raise SafetyBlocked(("SOC_OUT_OF_RANGE",))
    for flag in (0, 1):
        caps = finite_array(compute_caps(flag, site), "dynamic grid caps", ndim=1)
        if np.any(caps < 0):
            raise SafetyBlocked(("INVALID_DYNAMIC_GRID_CAP",))
    return ts, base, peak


def require_population(accepted):
    if not accepted:
        raise SafetyBlocked(("BLOCKED_ALL_CANDIDATES_REJECTED",))
    return accepted


def simulate_checked(profile, controller, site, limits, *, supervisor=None, seed=0,
                     event_binding=None):
    """Run causal EMS steps and veto transitions before accepting them.

    Inline mode retains engineering compatibility and cannot interrupt a hung
    controller. ProcessSupervisorConfig enables terminate-and-join containment.
    Neither mode certifies field safety or hard real-time execution.
    """
    from jer_microgrid.simulation import SimResult
    from jer_microgrid.controllers import compute_caps
    integer(seed, "seed")
    ts, base, peak = validate_simulation_inputs(profile, site, limits)
    if (getattr(controller, "is_cloud_dependent", False)
            or controller.__class__.__name__ == "LinearMPCQPController"):
        raise SafetyBlocked(("UNSUPPORTED_CONTROLLER_INTERFACE",))
    if supervisor is not None and not isinstance(supervisor, ProcessSupervisorConfig):
        raise ContractError("supervisor must be ProcessSupervisorConfig or None")
    binding = dict(event_binding or {})
    session = (None if supervisor is None else SupervisorSession(
        controller, step_timeout_seconds=limits.step_timeout_seconds, seed=seed,
        config=supervisor, event_binding=binding))
    soc = site.soc_init
    previous = 0.0
    previous_mode = None
    switches = 0
    rows = []
    step_index = None
    try:
        with (nullcontext() if session is None else session):
            if session is None:
                try:
                    controller.reset()
                except Exception as exc:
                    raise SafetyBlocked(("CONTROLLER_RESET_EXCEPTION",)) from exc
            for t in range(len(base)):
                step_index = t
                start = time.perf_counter()
                if session is None:
                    try:
                        command, debug = controller.step(t, base[:t + 1], soc, int(peak[t]))
                    except Exception as exc:
                        raise SafetyBlocked(("CONTROLLER_EXCEPTION",)) from exc
                    elapsed = time.perf_counter() - start
                else:
                    command, debug, elapsed = session.step(t, base[:t + 1], soc, int(peak[t]))
                try:
                    if (isinstance(command, (bool, np.bool_)) or not np.isscalar(command)
                            or not math.isfinite(command)):
                        raise ValueError()
                    command = float(command)
                except (TypeError, ValueError):
                    raise SafetyBlocked(("NONFINITE_OR_INVALID_COMMAND",))
                if (not isinstance(debug, dict) or not isinstance(debug.get("mode"), str)
                        or not debug["mode"].strip()):
                    raise SafetyBlocked(("INVALID_CONTROLLER_MODE",))
                mode = debug["mode"]
                if previous_mode is not None and mode != previous_mode:
                    switches += 1
                previous_mode = mode
                import_cap, export_cap = compute_caps(int(peak[t]), site)
                codes = limits.veto(
                    soc=soc, command_kw=command, base_kw=float(base[t]),
                    previous_command_kw=previous, switches=switches,
                    elapsed_seconds=elapsed, dynamic_import_cap_kw=import_cap,
                    dynamic_export_cap_kw=export_cap)
                if codes:
                    raise SafetyBlocked(codes)
                next_soc = (soc - limits.dt_hours * command / (limits.energy_kwh * limits.eta_discharge)
                            if command >= 0 else
                            soc - limits.dt_hours * command * limits.eta_charge / limits.energy_kwh)
                rows.append({
                    "timestamp": ts[t], "base_kw": base[t], "cmd_kw": command,
                    "grid_kw": base[t] - command, "soc": soc, "soc_next": next_soc,
                    "p_imp_cap": import_cap, "p_exp_cap": export_cap,
                    "cpu_ms": elapsed * 1000, "mode": mode,
                    "rg_state": debug.get("rg_state", "MID")})
                soc = next_soc
                previous = command
    except ControllerExecutionError as exc:
        receipt = {**exc.receipt, "accepted_transitions": len(rows),
                   "result_policy": "INVALID_RUN_EXCLUDED_NO_PARTIAL_METRICS"}
        raise SafetyBlocked((exc.receipt["code"],), receipt=receipt) from exc
    except SafetyBlocked as exc:
        receipt = {
            "status": "FAILED", "codes": list(exc.codes), "step": step_index,
            "seed": seed, "event_binding": binding,
            "accepted_transitions": len(rows),
            "result_policy": "INVALID_RUN_EXCLUDED_NO_PARTIAL_METRICS",
            "supervision": "INLINE" if session is None else session.report(),
            "exception_type": None if exc.__cause__ is None else type(exc.__cause__).__name__,
            "exception_message": None if exc.__cause__ is None else str(exc.__cause__)[:512]}
        raise SafetyBlocked(exc.codes, receipt=receipt) from exc
    return SimResult(pd.DataFrame(rows), {
        "safety_basis": limits.basis, "status": "SCENARIO_VETO_PASSED",
        "switches": switches, "switch_policy": "MODE_TRANSITIONS_MATCH_FLIP_PER_DAY",
        "seed": seed, "event_binding": binding,
        "supervision": "INLINE_LATE_RETURN_CHECK_ONLY" if session is None else session.report()})
