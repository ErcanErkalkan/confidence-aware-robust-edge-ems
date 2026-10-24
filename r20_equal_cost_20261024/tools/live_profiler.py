"""R20 prospective telemetry; additive opt-in timing around original callables.

This instrumenter does not imply historical CPU measurements are known.
Examples: with p.measure('sim'): original_ems_evaluation();
No TEST calls; exported json remains DRAFT until externally authenticated.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import platform
import resource
import sys
import time
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass,field

PHASES=('sim','optimizer','archive','selection','audit')

class InstrumentationError(RuntimeError):pass

@dataclass
class PhaseProfiler:
    """A non-overlapping single-process CPU/wall timer with event identity ledger.

    For distributed/parallel execution every worker needs separate tracing and
    aggregation; the sum of process CPU times need not equal a wall duration.
    """
    seed:int
    arm:str
    run_sha:str
    benchmark_mode:bool=False
    times:dict=field(default_factory=lambda:{k:{'cpu_ns':0,'wall_ns':0,'calls':0} for k in PHASES})
    eval_ids:set=field(default_factory=set)
    confidence_pair_calls:int=0
    pair_comparisons:int=0
    bootstrap_draws_per_pair:int=0
    max_native_archive_members:int=0
    final_export_members:int=0
    archive_peak_tracemalloc_bytes:int=0
    _active:str|None=field(default=None,init=False)
    _initial_rss:int=field(default=0,init=False)

    def __post_init__(self):
        if type(self.seed)!=int or self.arm not in ('F0','F1'):
            raise InstrumentationError('invalid seed/arm')
        if len(self.run_sha)!=40 or any(x not in '0123456789abcdef' for x in self.run_sha):
            raise InstrumentationError('invalid execution Git SHA')
        if self.benchmark_mode is not True:
            # This code is intended for opt-in use after prospective approval;
            # a run must make its execution mode explicit.
            raise InstrumentationError('experimental profile requires explicit benchmark_mode=True')
        self._initial_rss=self.rss_bytes()

    @staticmethod
    def rss_bytes():
        # ru_maxrss is a process-wide high water mark (KiB on Linux).
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak*(1 if sys.platform=='darwin' else 1024))

    @contextlib.contextmanager
    def measure(self,phase:str):
        if phase not in PHASES:raise InstrumentationError(f'unknown phase: {phase}')
        if self._active is not None:raise InstrumentationError('cannot nest phase time; avoid double counting')
        self._active=phase
        wall=time.perf_counter_ns();cpu=time.process_time_ns()
        if phase=='archive':
            if tracemalloc.is_tracing():raise InstrumentationError('tracemalloc already started')
            tracemalloc.start()
        try:
            yield
        finally:
            c=time.process_time_ns()-cpu; w=time.perf_counter_ns()-wall
            self.times[phase]['cpu_ns']+=c
            self.times[phase]['wall_ns']+=w
            self.times[phase]['calls']+=1
            if phase=='archive' and tracemalloc.is_tracing():
                self.archive_peak_tracemalloc_bytes=max(self.archive_peak_tracemalloc_bytes,tracemalloc.get_traced_memory()[1])
                tracemalloc.stop()
            self._active=None

    def reserve_actual_evaluation(self,candidate_id:str,block_id:str):
        if self._active!='sim':raise InstrumentationError('eval identity must be counted inside sim phase')
        if not candidate_id or not block_id:raise InstrumentationError('empty candidate or block ID')
        pair=(str(candidate_id),str(block_id))
        if pair in self.eval_ids:raise InstrumentationError('duplicated candidate-block')
        self.eval_ids.add(pair)

    def record_archive_candidate_count(self,n:int):
        if self._active!='archive' or type(n)!=int or n<0:raise InstrumentationError('archive size event invalid')
        self.max_native_archive_members=max(self.max_native_archive_members,n)

    def record_pair_test(self,*,confidence:bool,bootstrap_draws_per_pair:int=0):
        if self._active!='archive':raise InstrumentationError('pair test outside archive')
        if confidence:
            if self.arm!='F1' or type(bootstrap_draws_per_pair)!=int or bootstrap_draws_per_pair<200:
                raise InstrumentationError('invalid confidence bootstrap telemetry')
            if self.bootstrap_draws_per_pair not in (0,bootstrap_draws_per_pair):
                raise InstrumentationError('mixed bootstrap settings')
            self.pair_comparisons+=1
            self.confidence_pair_calls+=1
            self.bootstrap_draws_per_pair=bootstrap_draws_per_pair
        else:
            if self.arm!='F0' or bootstrap_draws_per_pair:
                raise InstrumentationError('F0 cannot fake F1 bootstrap')
            self.pair_comparisons+=1

    def record_selection(self,n:int):
        if self._active!='selection' or type(n)!=int or n<0:raise InstrumentationError('invalid selection record')
        self.final_export_members=n

    def emit(self,*,input_ledger_sha256:str,environment_sha256:str):
        if self._active:raise InstrumentationError('cannot emit during active phase')
        if len(self.eval_ids)!=12600:
            raise InstrumentationError('incomplete 12600 evaluation ledger; partial artifacts are not success')
        for value in (input_ledger_sha256,environment_sha256):
            if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise InstrumentationError('invalid ledger or environment SHA')
        r={'seed':self.seed,'arm':self.arm,'run_sha':self.run_sha,
           'input_ledger_sha256':input_ledger_sha256,'runtime_environment_sha256':environment_sha256,
           'n_controller_blocks':len(self.eval_ids),'peak_rss_bytes':self.rss_bytes(),
           'archive_peak_tracemalloc_bytes':self.archive_peak_tracemalloc_bytes,
           'peak_native_archive_members':self.max_native_archive_members,
           'final_export_members':self.final_export_members,
           'pair_comparisons':self.pair_comparisons,
           'bootstrap_draws_per_pair':self.bootstrap_draws_per_pair,
           'confidence_pair_calls':self.confidence_pair_calls}
        for name,stats in self.times.items():
            r[name+'_cpu_ns']=stats['cpu_ns'];r[name+'_wall_ns']=stats['wall_ns']
        from cost_audit import parse_cost_record
        return parse_cost_record(r)

def environment_fingerprint():
    env={'python':sys.version,'platform':platform.platform(),
         'processor':platform.processor(),'cpu_count':os.cpu_count(),
         'numpy_imported':False,'measurement_clock':'time.process_time_ns + time.perf_counter_ns',
         'resident_memory':'ru_maxrss (process high-water, not per-phase peak)'}
    return hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest(),env
