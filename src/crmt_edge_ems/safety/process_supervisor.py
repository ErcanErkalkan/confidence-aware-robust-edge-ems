"""Opt-in process containment for simulated controllers; no hardware certification.

The worker persists across steps so stateful EMS controllers keep their state.
Only bounded scalar/debug responses cross the pipe. A timeout terminates and
joins the worker before returning a failure. Descendant process containment and
hard real-time scheduling are outside this simulator-only mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import multiprocessing as mp
import numbers
import os
import random
import sys
import time
import traceback
from typing import Any

import numpy as np

from ..contracts import ContractError, integer


@dataclass(frozen=True)
class ResourceLimits:
    cpu_seconds: int | None = None
    address_space_bytes: int | None = None

    def __post_init__(self):
        for name in ("cpu_seconds", "address_space_bytes"):
            value = getattr(self, name)
            if value is not None:
                integer(value, name, 1)


@dataclass(frozen=True)
class ProcessSupervisorConfig:
    startup_timeout_seconds: float = 30.0
    shutdown_timeout_seconds: float = 1.0
    resources: ResourceLimits = field(default_factory=ResourceLimits)

    def __post_init__(self):
        for name in ("startup_timeout_seconds", "shutdown_timeout_seconds"):
            value = getattr(self, name)
            if (isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real)
                    or not math.isfinite(value) or value <= 0):
                raise ContractError(f"{name}: finite positive timeout required")
        if not isinstance(self.resources, ResourceLimits):
            raise ContractError("resources must be ResourceLimits")


class ControllerExecutionError(RuntimeError):
    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__(receipt["code"])


def _resource_limits(limits):
    requested = {key: getattr(limits, key) for key in ("cpu_seconds", "address_space_bytes")
                 if getattr(limits, key) is not None}
    if not requested:
        return {"requested": {}, "enforced": {}, "platform": os.name}
    if os.name != "posix":
        raise RuntimeError("RESOURCE_LIMIT_UNSUPPORTED: requested limits need POSIX resource")
    import resource
    enforced = {}
    for name, value in requested.items():
        symbol = "RLIMIT_CPU" if name == "cpu_seconds" else "RLIMIT_AS"
        if not hasattr(resource, symbol):
            raise RuntimeError(f"RESOURCE_LIMIT_UNSUPPORTED: {symbol}")
        target = getattr(resource, symbol)
        _, hard = resource.getrlimit(target)
        effective = value if hard == resource.RLIM_INFINITY else min(value, hard)
        resource.setrlimit(target, (effective, effective))
        enforced[name] = effective
    return {"requested": requested, "enforced": enforced, "platform": os.name}


def _safe_debug(debug):
    if not isinstance(debug, dict):
        raise ValueError("controller debug must be a dict")
    mode = debug.get("mode")
    state = debug.get("rg_state", "MID")
    if not isinstance(mode, str) or not mode.strip() or len(mode) > 128:
        raise ValueError("controller mode must be a nonblank bounded string")
    if not isinstance(state, str) or len(state) > 128:
        raise ValueError("controller rg_state must be a bounded string")
    return {"mode": mode, "rg_state": state}


def _worker_measurements(started_cpu):
    """CPU through this receipt; peak RSS is process lifetime, including startup."""
    rss = None
    error = None
    try:
        if os.name == "posix":
            import resource
            raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            rss = int(raw if sys.platform == "darwin" else raw * 1024)
        elif os.name == "nt":
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(
                    kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                raise OSError(ctypes.get_last_error())
            rss = int(counters.PeakWorkingSetSize)
    except Exception as exc:
        error = type(exc).__name__
    return {"worker_cpu_seconds": time.process_time() - started_cpu,
            "worker_cpu_scope": "WORKER_TARGET_ENTRY_THROUGH_RECEIPT_INCLUDING_RESET_AND_STEPS",
            "worker_peak_rss_bytes": rss,
            "worker_peak_rss_scope": "WORKER_PROCESS_LIFETIME",
            "measurement_error": error}


def _worker(connection, controller, seed, resources):
    started_cpu = time.process_time()
    try:
        random.seed(seed)
        np.random.seed(seed % (2 ** 32))
        applied = _resource_limits(resources)
        controller.reset()
        connection.send({"status": "READY", "resources": applied})
        while True:
            request = connection.recv()
            if request["operation"] == "STOP":
                connection.send({"status": "STOPPED",
                                 "measurements": _worker_measurements(started_cpu)})
                return
            started = time.perf_counter()
            command, debug = controller.step(
                request["t"], request["history"], request["soc"], request["peak_flag"])
            if (isinstance(command, (bool, np.bool_)) or not np.isscalar(command)
                    or not math.isfinite(command)):
                raise ValueError("NONFINITE_OR_INVALID_COMMAND")
            response = {"status": "OK", "command": float(command),
                        "debug": _safe_debug(debug),
                        "controller_wall_seconds": time.perf_counter() - started}
            connection.send(response)
    except BaseException as exc:
        try:
            message = str(exc)[:512]
            connection.send({"status": "ERROR", "type": type(exc).__name__,
                             "message": message,
                             "traceback": traceback.format_exc(limit=8)[-4096:],
                             "measurements": _worker_measurements(started_cpu)})
        except BaseException:
            pass
    finally:
        connection.close()


class SupervisorSession:
    """Own a single spawned worker and preserve controller state until close."""

    def __init__(self, controller, *, step_timeout_seconds, seed=0, config=None,
                 event_binding=None):
        integer(seed, "seed")
        if (isinstance(step_timeout_seconds, (bool, np.bool_))
                or not isinstance(step_timeout_seconds, numbers.Real)
                or not math.isfinite(step_timeout_seconds) or step_timeout_seconds <= 0):
            raise ContractError("finite positive step timeout required")
        self.config = config or ProcessSupervisorConfig()
        if not isinstance(self.config, ProcessSupervisorConfig):
            raise ContractError("invalid process supervisor configuration")
        self.controller = controller
        self.timeout = float(step_timeout_seconds)
        self.seed = int(seed)
        self.binding = dict(event_binding or {})
        self.process = None
        self.connection = None
        self.resource_receipt = None
        self.worker_measurements = None
        self.receipts = []

    def _stop(self, *, abort):
        if self.connection is not None and not abort:
            try:
                self.connection.send({"operation": "STOP"})
                if self.connection.poll(self.config.shutdown_timeout_seconds):
                    response = self.connection.recv()
                    if isinstance(response, dict) and response.get("status") == "STOPPED":
                        self.worker_measurements = response.get("measurements")
            except (BrokenPipeError, EOFError, OSError):
                pass
        if self.process is not None:
            if abort and self.process.is_alive():
                self.worker_measurements = None
                self.process.terminate()
            self.process.join(self.config.shutdown_timeout_seconds)
            if self.process.is_alive():
                self.worker_measurements = None
                self.process.terminate()
                self.process.join(self.config.shutdown_timeout_seconds)
            if self.process.is_alive():
                self.worker_measurements = None
                self.process.kill()
                self.process.join(self.config.shutdown_timeout_seconds)
            if self.process.is_alive():
                # Never claim containment if the OS failed to terminate the child.
                raise RuntimeError("CONTROLLER_TERMINATION_FAILED")
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _fail(self, code, *, stage, step=None, elapsed=None, detail=None):
        self._stop(abort=True)
        receipt = {
            "status": "FAILED", "code": code, "stage": stage, "step": step,
            "seed": self.seed, "event_binding": self.binding,
            "elapsed_seconds": elapsed, "detail": detail,
            "worker_pid": None if self.process is None else self.process.pid,
            "worker_exitcode": None if self.process is None else self.process.exitcode,
            "worker_terminated": self.process is None or not self.process.is_alive(),
            "resources": self.resource_receipt,
            "worker_measurements": self.worker_measurements,
            "scope": "SIMULATION_PROCESS_CONTAINMENT_NOT_HARDWARE_SAFETY",
        }
        self.receipts.append(receipt)
        raise ControllerExecutionError(receipt)

    def _receive(self, timeout, *, stage, step=None):
        started = time.perf_counter()
        if not self.connection.poll(timeout):
            self._fail("CONTROLLER_TIMEOUT", stage=stage, step=step,
                       elapsed=time.perf_counter() - started)
        try:
            response = self.connection.recv()
        except (EOFError, OSError) as exc:
            self._fail("CONTROLLER_PROCESS_EXIT", stage=stage, step=step,
                       elapsed=time.perf_counter() - started, detail=type(exc).__name__)
        if not isinstance(response, dict) or response.get("status") not in {"READY", "OK"}:
            if isinstance(response, dict) and response.get("status") == "ERROR":
                self.worker_measurements = response.get("measurements")
            self._fail("CONTROLLER_EXCEPTION", stage=stage, step=step,
                       elapsed=time.perf_counter() - started, detail=response)
        return response

    def __enter__(self):
        context = mp.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        self.connection = parent
        self.process = context.Process(
            target=_worker, args=(child, self.controller, self.seed, self.config.resources),
            name="crmt-controller-worker", daemon=True)
        try:
            self.process.start()
        except Exception as exc:
            child.close()
            # An unstarted Process cannot be joined.
            self.process = None
            self._fail("CONTROLLER_STARTUP_ERROR", stage="STARTUP",
                       detail={"type": type(exc).__name__, "message": str(exc)[:512]})
        child.close()
        response = self._receive(self.config.startup_timeout_seconds, stage="STARTUP")
        if response.get("status") != "READY":
            self._fail("CONTROLLER_PROTOCOL_ERROR", stage="STARTUP")
        self.resource_receipt = response["resources"]
        return self

    def step(self, t, history, soc, peak_flag):
        started = time.perf_counter()
        try:
            self.connection.send({"operation": "STEP", "t": int(t), "history": history,
                                  "soc": float(soc), "peak_flag": int(peak_flag)})
        except (EOFError, OSError) as exc:
            self._fail("CONTROLLER_PROCESS_EXIT", stage="STEP", step=t,
                       elapsed=time.perf_counter() - started, detail=type(exc).__name__)
        response = self._receive(self.timeout, stage="STEP", step=t)
        elapsed = time.perf_counter() - started
        if elapsed > self.timeout:
            self._fail("CONTROLLER_TIMEOUT", stage="STEP", step=t, elapsed=elapsed)
        if response.get("status") != "OK":
            self._fail("CONTROLLER_PROTOCOL_ERROR", stage="STEP", step=t, elapsed=elapsed)
        return response["command"], response["debug"], elapsed

    def __exit__(self, exc_type, exc, tb):
        self._stop(abort=exc_type is not None)
        return False

    def report(self):
        return {"worker_pid": None if self.process is None else self.process.pid,
                "worker_exitcode": None if self.process is None else self.process.exitcode,
                "worker_terminated": self.process is None or not self.process.is_alive(),
                "seed": self.seed, "resources": self.resource_receipt,
                "worker_measurements": self.worker_measurements,
                "scope": "SIMULATION_PROCESS_CONTAINMENT_NOT_HARDWARE_SAFETY"}
