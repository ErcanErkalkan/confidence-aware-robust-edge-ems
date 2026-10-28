"""Future metric tests explicitly preserve the historical metric implementation."""
import itertools

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.metrics_v2 import compute_metrics_v2, rainflow_cycles_detailed_v2, METRICS_VERSION
from crmt_edge_ems.safety import SafetyLimits, simulate_checked
from jer_microgrid.config import SiteConfig
from jer_microgrid.metrics import compute_metrics, rainflow_cycles_detailed


class FixedCommand:
    def reset(self):
        pass

    def step(self, *args):
        return 1.0, {"mode": "PS"}


def test_closed_cycle_bug_is_corrected_only_in_versioned_future_metrics():
    trajectory = np.asarray([0.2, 0.8, 0.2])
    old = sum(depth * weight for depth, weight, _, _ in rainflow_cycles_detailed(trajectory))
    new = sum(depth * weight for depth, weight, _, _ in rainflow_cycles_detailed_v2(trajectory))
    assert old == pytest.approx(0.3)
    assert new == pytest.approx(0.6)


def test_exhaustive_small_soc_paths_preserve_half_total_variation():
    # Exhaustive finite-state property check, including plateaus and nested
    # cycles; no optional property-testing dependency is required.
    for size in range(1, 7):
        for path in itertools.product((0.2, 0.5, 0.8), repeat=size):
            cycles = rainflow_cycles_detailed_v2(path)
            observed = sum(depth * weight for depth, weight, _, _ in cycles)
            expected = float(np.abs(np.diff(path)).sum()) / 2
            assert observed == pytest.approx(expected)
            assert all(depth > 0 and weight in {0.5, 1.0}
                       and high - low == pytest.approx(depth)
                       for depth, weight, low, high in cycles)


def simulation():
    site = SiteConfig()
    profile = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=1, freq="min", tz="UTC"),
        "base_kw": [0.0], "peak_flag": [0]})
    result = simulate_checked(profile, FixedCommand(), site, SafetyLimits.from_site(site))
    return result.series, site


def test_terminal_soc_interval_is_included_without_rewriting_legacy():
    series, site = simulation()
    old = compute_metrics(series, site)
    new = compute_metrics_v2(series, site)
    assert old["efcrf"] == old["lfp_cycle_loss_pct"] == 0
    assert new["efcrf"] == pytest.approx(
        abs(series["soc_next"].iloc[-1] - series["soc"].iloc[0]) / 2)
    assert new["lfp_cycle_loss_pct"] > 0
    assert new["metrics_version"] == METRICS_VERSION
    assert new["battery_lifetime_evidence"] == "MODEL_PROXY_NOT_PHYSICAL_LIFETIME"


def test_invalid_final_soc_is_not_clipped_or_dropped():
    series, site = simulation()
    series.loc[0, "soc_next"] = 1.1
    with pytest.raises(ContractError, match="declared bounds"):
        compute_metrics_v2(series, site)


def test_discontinuous_soc_is_rejected():
    series, site = simulation()
    second = series.copy()
    second["timestamp"] += pd.Timedelta(minutes=1)
    series = pd.concat([series, second], ignore_index=True)
    with pytest.raises(ContractError, match="discontinuous"):
        compute_metrics_v2(series, site)


@pytest.mark.parametrize("path", [[], [float("nan")], [float("inf")], ["0.5"]])
def test_rainflow_rejects_invalid_trajectory(path):
    with pytest.raises(ContractError):
        rainflow_cycles_detailed_v2(path)
