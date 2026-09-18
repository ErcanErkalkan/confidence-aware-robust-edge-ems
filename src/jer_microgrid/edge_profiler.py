import time
import tracemalloc
from contextlib import contextmanager

class ProfileResult:
    def __init__(self):
        self.cpu_ms: float = 0.0
        self.peak_mem_kb: float = 0.0
        self.current_mem_kb: float = 0.0

@contextmanager
def edge_profiler(result: ProfileResult):
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    
    tracemalloc.reset_peak()
    t0 = time.perf_counter()
    
    try:
        yield
    finally:
        t1 = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        
        result.cpu_ms = (t1 - t0) * 1000.0
        result.current_mem_kb = current / 1024.0
        result.peak_mem_kb = peak / 1024.0
