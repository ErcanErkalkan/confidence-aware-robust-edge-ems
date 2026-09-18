from __future__ import annotations

import unittest

import numpy as np

from jer_microgrid.config import CONTROLLERS_MAIN, SiteConfig, SyntheticConfig
from jer_microgrid.controllers import build_controller, compute_hard_bounds
from jer_microgrid.metrics import compute_metrics
from jer_microgrid.simulation import simulate_controller, soc_update
from jer_microgrid.synth import generate_profile


class CoreBehaviorTests(unittest.TestCase):
    def test_synthetic_profile_is_deterministic(self) -> None:
        site = SiteConfig()
        synth = SyntheticConfig(hours=2, scenario_names=["mixed"])
        first = generate_profile(7, "mixed", site, synth)
        second = generate_profile(7, "mixed", site, synth)
        np.testing.assert_allclose(first["base_kw"].to_numpy(), second["base_kw"].to_numpy())
        self.assertEqual(first["scenario_seed"].iloc[0], "mixed_seed7")

    def test_soc_update_direction_and_bounds(self) -> None:
        site = SiteConfig()
        self.assertLess(soc_update(0.5, 10.0, site), 0.5)
        self.assertGreater(soc_update(0.5, -10.0, site), 0.5)
        self.assertGreaterEqual(soc_update(0.0, 1000.0, site), 0.0)
        self.assertLessEqual(soc_update(1.0, -1000.0, site), 1.0)

    def test_proposed_command_respects_hard_bounds(self) -> None:
        site = SiteConfig()
        synth = SyntheticConfig(hours=2, scenario_names=["load_step"])
        profile = generate_profile(3, "load_step", site, synth)
        result = simulate_controller(profile, build_controller("Proposed", site), site)
        for _, row in result.series.iterrows():
            pmin, pmax = compute_hard_bounds(float(row["soc"]), site)
            self.assertGreaterEqual(float(row["cmd_kw"]), pmin - 1e-9)
            self.assertLessEqual(float(row["cmd_kw"]), pmax + 1e-9)

    def test_metric_payload_contains_expected_fields(self) -> None:
        site = SiteConfig()
        synth = SyntheticConfig(hours=1, scenario_names=["mixed"])
        profile = generate_profile(0, "mixed", site, synth)
        result = simulate_controller(profile, build_controller("GR", site), site)
        metrics = compute_metrics(result.series, site)
        for key in [
            "ramp95_kw_per_min",
            "cap_violation_pct_total",
            "throughput_kwh",
            "lfp_cycle_loss_pct",
            "mean_cpu_ms",
        ]:
            self.assertIn(key, metrics)
            self.assertTrue(np.isfinite(metrics[key]))

    def test_controller_registry_has_no_removed_reference(self) -> None:
        self.assertNotIn("MPC_ref", CONTROLLERS_MAIN)
        for name in ["Proposed", "NC", "GR", "RS", "FBRL"]:
            self.assertEqual(build_controller(name, SiteConfig()).name, name)


if __name__ == "__main__":
    unittest.main()
