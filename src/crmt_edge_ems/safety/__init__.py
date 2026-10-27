"""Scenario safety veto, not certified field/hardware safety."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from ..contracts import ContractError, finite_array, integer

class SafetyBlocked(RuntimeError):
    def __init__(self,codes):
        self.codes=tuple(codes); super().__init__('SAFETY_VETO:'+','.join(self.codes))

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
    basis: str='SCENARIO_ASSUMPTIONS_NOT_CERTIFIED'

    def __post_init__(self):
        finite_array([self.soc_min,self.soc_max,self.charge_kw,self.discharge_kw,self.energy_kwh,
            self.eta_charge,self.eta_discharge,self.dt_hours,self.import_kw,self.export_kw,
            self.ramp_kw_per_min,self.step_timeout_seconds],'safety limits',ndim=1)
        integer(self.max_switches,'max_switches')
        if not 0<=self.soc_min<self.soc_max<=1 or min(self.charge_kw,self.discharge_kw,self.import_kw,self.export_kw)<0 or min(self.energy_kwh,self.dt_hours,self.ramp_kw_per_min,self.step_timeout_seconds)<=0 or not (0<self.eta_charge<=1 and 0<self.eta_discharge<=1):
            raise ContractError('invalid scenario safety limits')
        if self.basis!='SCENARIO_ASSUMPTIONS_NOT_CERTIFIED': raise ContractError('no certified physical authority is installed')

    def veto(self,*,soc,command_kw,base_kw,previous_command_kw=0.0,switches=0,elapsed_seconds=0.0,
             dynamic_import_cap_kw=None,dynamic_export_cap_kw=None):
        codes=[]
        try:
            vals=finite_array([soc,command_kw,base_kw,previous_command_kw,elapsed_seconds],'telemetry',ndim=1)
            integer(switches,'switches')
        except (ContractError,TypeError,ValueError): return ('INVALID_OR_MISSING_TELEMETRY',)
        if elapsed_seconds<0: codes.append('INVALID_ELAPSED_TIME')
        if dynamic_import_cap_kw is not None or dynamic_export_cap_kw is not None:
            if dynamic_import_cap_kw is None or dynamic_export_cap_kw is None:
                return ('INVALID_DYNAMIC_GRID_CAP',)
            try:
                caps=finite_array([dynamic_import_cap_kw,dynamic_export_cap_kw], 'dynamic grid caps',ndim=1)
            except (ContractError,TypeError,ValueError):
                return ('INVALID_DYNAMIC_GRID_CAP',)
            if np.any(caps<0): return ('INVALID_DYNAMIC_GRID_CAP',)
        else: caps=None
        if not self.soc_min<=soc<=self.soc_max: codes.append('SOC_OUT_OF_RANGE')
        if command_kw < -self.charge_kw or command_kw>self.discharge_kw: codes.append('INVERTER_POWER_LIMIT')
        next_soc=soc-self.dt_hours*command_kw/(self.energy_kwh*self.eta_discharge) if command_kw>=0 else soc-self.dt_hours*command_kw*self.eta_charge/self.energy_kwh
        if not self.soc_min-1e-12<=next_soc<=self.soc_max+1e-12: codes.append('SOC_TRANSITION_LIMIT')
        grid=base_kw-command_kw
        effective_import=min(self.import_kw,float(caps[0])) if caps is not None else self.import_kw
        effective_export=min(self.export_kw,float(caps[1])) if caps is not None else self.export_kw
        if grid>effective_import+1e-12 or grid < -effective_export-1e-12: codes.append('GRID_LIMIT')
        if abs(command_kw-previous_command_kw)>self.ramp_kw_per_min*self.dt_hours*60+1e-12: codes.append('COMMAND_RAMP_LIMIT')
        if switches>self.max_switches: codes.append('SWITCH_LIMIT')
        if elapsed_seconds>self.step_timeout_seconds: codes.append('STEP_TIMEOUT')
        return tuple(codes)

def require_population(accepted):
    if not accepted: raise SafetyBlocked(('BLOCKED_ALL_CANDIDATES_REJECTED',))
    return accepted

def simulate_checked(profile, controller, site, limits):
    """Call the existing causal controller, veto before accepting each transition.

    Timeouts detect a returned late step. This function cannot interrupt a hung
    controller; isolated process supervision is still required for deployment.
    """
    import time
    from jer_microgrid.simulation import SimResult
    from jer_microgrid.controllers import compute_caps
    required={'timestamp','base_kw','peak_flag'}
    if not required<=set(profile) or profile.empty: raise SafetyBlocked(('PROFILE_SCHEMA',))
    ts=pd.DatetimeIndex(profile['timestamp'])
    if ts.tz is None or ts.hasnans or ts.has_duplicates or not ts.is_monotonic_increasing: raise SafetyBlocked(('PROFILE_TIME_SUPPORT',))
    if len(ts)>1 and not np.allclose(np.diff(ts.as_unit('ns').asi8)/3.6e12,limits.dt_hours,atol=1e-12,rtol=0): raise SafetyBlocked(('PROFILE_CADENCE',))
    base=finite_array(profile['base_kw'].to_numpy(),'base',ndim=1)
    peak=finite_array(profile['peak_flag'].to_numpy(),'peak',ndim=1)
    if not np.isin(peak,[0,1]).all(): raise SafetyBlocked(('PROFILE_PEAK_FLAG',))
    pairs=((site.e_nom_kwh,limits.energy_kwh),(site.ts_hours,limits.dt_hours),(site.eta_ch,limits.eta_charge),(site.eta_dis,limits.eta_discharge))
    if any(not math.isclose(a,b,rel_tol=0,abs_tol=1e-12) for a,b in pairs): raise SafetyBlocked(('SITE_LIMIT_MISMATCH',))
    # Fail closed when the scenario veto is less restrictive than the source
    # site's documented physical constraints. The historical EMS is unchanged.
    site_safety=((getattr(site,'soc_min',limits.soc_min),limits.soc_min,'minimum'),
                 (getattr(site,'soc_max',limits.soc_max),limits.soc_max,'maximum'))
    if (limits.soc_min < site_safety[0][0]-1e-12 or
        limits.soc_max > site_safety[1][0]+1e-12 or
        limits.charge_kw > getattr(site,'p_ch_max',limits.charge_kw)+1e-12 or
        limits.discharge_kw > getattr(site,'p_dis_max',limits.discharge_kw)+1e-12 or
        limits.ramp_kw_per_min*limits.dt_hours*60 > getattr(site,'r_max_kw_per_tick',float('inf'))+1e-12):
        raise SafetyBlocked(('SITE_LIMIT_MISMATCH',))
    if getattr(controller,'is_cloud_dependent',False) or controller.__class__.__name__=='LinearMPCQPController': raise SafetyBlocked(('UNSUPPORTED_CONTROLLER_INTERFACE',))
    controller.reset(); soc=site.soc_init; previous=0.0; previous_mode=None; switches=0; rows=[]
    for t in range(len(base)):
        start=time.perf_counter()
        try: command,debug=controller.step(t,base[:t+1],soc,int(peak[t]))
        except Exception as exc: raise SafetyBlocked(('CONTROLLER_EXCEPTION',)) from exc
        elapsed=time.perf_counter()-start
        try:
            if isinstance(command,(bool,np.bool_)) or not np.isscalar(command) or not math.isfinite(command): raise ValueError()
            command=float(command)
        except (TypeError,ValueError): raise SafetyBlocked(('NONFINITE_OR_INVALID_COMMAND',))
        # Match jer_microgrid.metrics.compute_metrics flip_per_day: mode changes,
        # including IDLE↔PS, count; command-sign reversals alone are insufficient.
        if not isinstance(debug,dict) or not isinstance(debug.get('mode'),str) or not debug['mode'].strip():
            raise SafetyBlocked(('INVALID_CONTROLLER_MODE',))
        mode=debug['mode']
        if previous_mode is not None and mode!=previous_mode: switches+=1
        previous_mode=mode
        import_cap,export_cap=compute_caps(int(peak[t]),site)
        if not np.isfinite([import_cap,export_cap]).all() or min(import_cap,export_cap)<0: raise SafetyBlocked(('INVALID_DYNAMIC_GRID_CAP',))
        codes=limits.veto(soc=soc,command_kw=command,base_kw=float(base[t]),previous_command_kw=previous,switches=switches,elapsed_seconds=elapsed,
            dynamic_import_cap_kw=import_cap,dynamic_export_cap_kw=export_cap)
        if codes: raise SafetyBlocked(codes)
        next_soc=soc-limits.dt_hours*command/(limits.energy_kwh*limits.eta_discharge) if command>=0 else soc-limits.dt_hours*command*limits.eta_charge/limits.energy_kwh
        rows.append({'timestamp':ts[t],'base_kw':base[t],'cmd_kw':command,'grid_kw':base[t]-command,'soc':soc,'soc_next':next_soc,
            'p_imp_cap':import_cap,'p_exp_cap':export_cap,
            'cpu_ms':elapsed*1000,'mode':mode,'rg_state':debug.get('rg_state','MID')})
        soc=next_soc; previous=command
    return SimResult(pd.DataFrame(rows),{'safety_basis':limits.basis,'status':'SCENARIO_VETO_PASSED',
        'switches':switches,'switch_policy':'MODE_TRANSITIONS_MATCH_FLIP_PER_DAY'})
