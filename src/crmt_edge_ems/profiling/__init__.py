"""Measured runtime, OS peak RSS and unique simulator-event accounting."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, field
import os
import sys
import time
from ..contracts import ContractError, integer

def peak_rss_bytes():
    """Process lifetime high-water mark, never a phase-specific memory delta."""
    if os.name!='nt':
        import resource
        value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value*(1 if sys.platform=='darwin' else 1024))
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in (
            'PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
            'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True); psapi=ctypes.WinDLL('psapi',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE; kernel.GetCurrentProcess.argtypes=[]
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    counters=Counters(); counters.cb=ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb): raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.PeakWorkingSetSize)

@dataclass
class CostTracker:
    budget: int
    events: dict=field(default_factory=dict,init=False)
    phases: dict=field(default_factory=dict,init=False)
    _active: bool=field(default=False,init=False)

    def __post_init__(self): integer(self.budget,'budget',1)

    def reserve(self, split, candidate, block):
        return self.reserve_many(split,candidate,[block])[0]

    def reserve_many(self, split, candidate, blocks):
        blocks=tuple(blocks)
        if not blocks or len(set(blocks))!=len(blocks): raise ContractError('nonempty unique block batch required')
        keys=[]
        for block in blocks:
            if split not in {'TRAIN','AUDIT','VALIDATION','TEST'} or any(not isinstance(x,str) or not x.strip() for x in (candidate,block)):
                raise ContractError('invalid cost event')
            key=(split,candidate,block)
            if key in self.events: raise ContractError('duplicate simulator event: explicitly reuse cached result instead')
            keys.append(key)
        if len(self.events)+len(keys)>self.budget: raise ContractError('BUDGET_EXCEEDED')
        for key in keys: self.events[key]='RESERVED'
        return tuple(keys)

    def finish(self,key,*,success):
        if type(success) is not bool or self.events.get(key)!='RESERVED': raise ContractError('invalid event completion')
        self.events[key]='COMPLETE' if success else 'FAILED_CHARGED'

    @contextmanager
    def measure(self, phase):
        if phase not in {'optimizer','archive_construction','bootstrap','candidate_selection','simulation'}: raise ContractError('unknown phase')
        if self._active: raise ContractError('nested profiling would double-count time')
        self._active=True; wall=time.perf_counter(); cpu=time.process_time()
        try: yield
        finally:
            row=self.phases.setdefault(phase,{'calls':0,'cpu_seconds':0.0,'wall_seconds':0.0})
            row['calls']+=1; row['cpu_seconds']+=time.process_time()-cpu; row['wall_seconds']+=time.perf_counter()-wall
            self._active=False

    def report(self):
        counts={name:sum(k[0]==split for k in self.events) for name,split in (
            ('train_controller_block_evaluations','TRAIN'),('audit_controller_block_evaluations','AUDIT'),
            ('validation_evaluations','VALIDATION'),('test_evaluations','TEST'))}
        return {'schema_version':1,**counts,'total_controller_block_events':len(self.events),
            'failed_charged_events':sum(v=='FAILED_CHARGED' for v in self.events.values()),
            'incomplete_events':sum(v=='RESERVED' for v in self.events.values()),'phases':self.phases,
            'optimizer_cpu_time':self.phases.get('optimizer',{}).get('cpu_seconds'),
            'optimizer_wall_time':self.phases.get('optimizer',{}).get('wall_seconds'),
            'archive_construction_time':self.phases.get('archive_construction',{}).get('wall_seconds'),
            'bootstrap_calls':self.phases.get('bootstrap',{}).get('calls',0),
            'bootstrap_cpu_time':self.phases.get('bootstrap',{}).get('cpu_seconds'),
            'candidate_selection_time':self.phases.get('candidate_selection',{}).get('wall_seconds'),
            'peak_process_rss':peak_rss_bytes(),'memory_scope':'PROCESS_LIFETIME_HIGH_WATER_MARK_BYTES',
            'energy_consumption_estimate':None,'energy_reason':'No validated power measurement model available',
            'per_candidate_cost':{c:sum(k[1]==c for k in self.events) for c in sorted({k[1] for k in self.events})},
            'per_seed_cost':None,'per_seed_reason':'One tracker per seed; seed binding belongs in run manifest'}
