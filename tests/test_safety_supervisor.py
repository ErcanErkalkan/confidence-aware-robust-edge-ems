"""Real spawned-process tests; these are simulation engineering evidence only."""
from dataclasses import replace
import multiprocessing as mp
import os
import time

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.safety import SafetyBlocked, SafetyLimits, simulate_checked
from crmt_edge_ems.safety.process_supervisor import ProcessSupervisorConfig, ResourceLimits
from jer_microgrid.config import SiteConfig


class StatefulController:
    def reset(self):
        self.calls = 0

    def step(self, *args):
        self.calls += 1
        return self.calls * 0.1, {"mode": "PS", "rg_state": "MID"}


class HungController:
    def reset(self):
        pass

    def step(self, *args):
        while True:
            time.sleep(0.01)


class HungResetController(HungController):
    def reset(self):
        while True:
            time.sleep(0.01)


class ExceptionController(StatefulController):
    def step(self, *args):
        raise RuntimeError("deliberate controller failure")


class RandomController(StatefulController):
    def step(self, *args):
        return float(np.random.uniform(-0.01, 0.01)), {"mode": "RG"}


class NonfiniteController(StatefulController):
    def step(self, *args):
        return float("inf"), {"mode": "PS"}


def profile(n=3):
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="min", tz="UTC"),
        "base_kw": [0.0] * n, "peak_flag": [0] * n})


def run(controller, *, seed=7, limits=None, config=None):
    site = SiteConfig()
    return simulate_checked(
        profile(), controller, site,
        limits or SafetyLimits.from_site(site), seed=seed,
        supervisor=config or ProcessSupervisorConfig(),
        event_binding={"scope": "SYNTHETIC_ENGINEERING_FIXTURE"})


def test_process_worker_preserves_state_and_exits_with_measurements():
    result = run(StatefulController())
    np.testing.assert_allclose(result.series["cmd_kw"], [0.1, 0.2, 0.3])
    supervision = result.meta["supervision"]
    assert supervision["worker_terminated"]
    assert supervision["worker_exitcode"] == 0
    assert supervision["worker_pid"] not in {p.pid for p in mp.active_children()}
    measurement = supervision["worker_measurements"]
    assert measurement["worker_cpu_seconds"] >= 0
    assert measurement["worker_cpu_scope"].endswith("INCLUDING_RESET_AND_STEPS")
    assert measurement["worker_peak_rss_scope"] == "WORKER_PROCESS_LIFETIME"
    if os.name in {"posix", "nt"}:
        assert measurement["worker_peak_rss_bytes"] > 0


@pytest.mark.parametrize("controller,stage", [
    (HungController, "STEP"), (HungResetController, "STARTUP")])
def test_hung_controller_is_terminated_before_failure_returns(controller, stage):
    limits = replace(SafetyLimits.from_site(SiteConfig()), step_timeout_seconds=0.15)
    # Interpreter/module startup is allowed to finish; reset hangs use the
    # startup deadline and ordinary hangs use the separate step deadline.
    config = ProcessSupervisorConfig(startup_timeout_seconds=8 if stage == "STARTUP" else 30,
                                     shutdown_timeout_seconds=0.5)
    with pytest.raises(SafetyBlocked, match="CONTROLLER_TIMEOUT") as error:
        run(controller(), limits=limits, config=config)
    receipt = error.value.receipt
    assert receipt["stage"] == stage
    assert receipt["worker_terminated"]
    assert receipt["worker_pid"] not in {p.pid for p in mp.active_children()}
    assert receipt["worker_measurements"] is None
    assert receipt["result_policy"] == "INVALID_RUN_EXCLUDED_NO_PARTIAL_METRICS"


@pytest.mark.parametrize("controller,message", [
    (ExceptionController, "deliberate controller failure"),
    (NonfiniteController, "NONFINITE_OR_INVALID_COMMAND")])
def test_controller_failures_return_traceback_and_no_result(controller, message):
    with pytest.raises(SafetyBlocked, match="CONTROLLER_EXCEPTION") as error:
        run(controller())
    receipt = error.value.receipt
    assert receipt["worker_terminated"]
    assert receipt["accepted_transitions"] == 0
    assert message in receipt["detail"]["message"]
    assert "Traceback" in receipt["detail"]["traceback"]


def test_seeded_worker_rerun_has_identical_controller_commands():
    first = run(RandomController(), seed=112)
    second = run(RandomController(), seed=112)
    np.testing.assert_array_equal(first.series["cmd_kw"], second.series["cmd_kw"])


def test_requested_resource_limits_are_enforced_or_fail_closed():
    config = ProcessSupervisorConfig(resources=ResourceLimits(cpu_seconds=10))
    if os.name == "posix":
        result = run(StatefulController(), config=config)
        receipt = result.meta["supervision"]["resources"]
        assert 0 < receipt["enforced"]["cpu_seconds"] <= 10
    else:
        with pytest.raises(SafetyBlocked, match="CONTROLLER_EXCEPTION") as error:
            run(StatefulController(), config=config)
        assert "RESOURCE_LIMIT_UNSUPPORTED" in error.value.receipt["detail"]["message"]


def test_nan_site_bound_is_rejected_before_controller_reset():
    class MustNotRun:
        def reset(self):
            raise AssertionError("invalid site reached controller")
    site = SiteConfig(p_ch_max=float("nan"))
    with pytest.raises(SafetyBlocked, match="INVALID_SITE_CONFIG"):
        simulate_checked(profile(), MustNotRun(), site,
                         SafetyLimits.from_site(SiteConfig()))
