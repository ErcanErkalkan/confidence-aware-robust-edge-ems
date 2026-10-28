"""Comparator invariants that matter for dependent day-vector calibration."""
import numpy as np
import pytest

from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.calibration.comparative_v3 import (
    day_bootstrap, diagnostics, filter_day_bootstrap, risk_day_panel,
)
from experiments.calibration.run_comparative_v3 import (
    METHODS, read_scenario_checkpoint, write_csv,
)


def test_day_resampling_preserves_candidate_pair_and_inverter_dependence():
    rng = np.random.default_rng(884)
    day = rng.random((16, 1, 1, 4))
    panel = np.broadcast_to(day, (16, 3, 2, 4)).copy()
    panel[:, 1] += .2
    panel[:, 2] += .4
    boot = day_bootstrap(panel, seed=39)
    # Each paired replicate must preserve the location shift exactly, despite
    # arbitrary within-day dependence. Separate candidate draws would fail.
    np.testing.assert_allclose(boot.replicates[:, 1]-boot.replicates[:, 0], .3)
    np.testing.assert_allclose(boot.replicates[:, 2]-boot.replicates[:, 0], .6)
    assert boot.support_days == 16


def test_decimal_ceil_tail_is_not_binary_roundoff_ceil():
    x = np.broadcast_to(np.arange(10)[:, None, None, None]/10, (10, 2, 1, 4))
    np.testing.assert_allclose(risk_day_panel(x, q=.7), .45+.5*.8)


@pytest.mark.parametrize("chronology", [None, np.r_[np.arange(7), np.arange(8, 17)]])
def test_block_bootstrap_never_bridges_missing_day(chronology):
    with pytest.raises(ContractError, match="chronolog"):
        day_bootstrap(np.zeros((16, 2, 1, 4)), block_length=8, chronology=chronology)


def test_bootstrap_comparison_reports_unresolved_bonferroni_tail():
    boot = day_bootstrap(np.random.default_rng(17).random((12, 4, 2, 4)), seed=15)
    bonf = filter_day_bootstrap(boot, method="bonferroni")
    assert bonf["bootstrap_tail_resolution_sufficient"] is False
    assert filter_day_bootstrap(boot, method="maxT")["bootstrap_tail_resolution_sufficient"] is True
    with pytest.raises(ContractError):
        filter_day_bootstrap(boot, method="invented")


def test_capacity_abstention_keeps_front_and_never_implies_k_selection():
    t = np.linspace(0, 1, 12)
    truth = np.stack((t, 1-t, t, 1-t), axis=1)
    answer = diagnostics(np.ones(12, bool), np.zeros((12, 12), bool),
                         np.full((12, 12, 4), np.inf), capacity=10,
                         truth=truth, abstain_on_overflow=True)
    assert answer["archive_overflow"] and answer["abstention"]
    assert answer["retained_pareto_count"] == 12
    assert answer["false_elimination"] is False
    assert answer["family_coverage"] is True
    assert answer["selection_executed"] is False
    assert answer["shortlist_size"] is None


def test_finite_historical_reference_is_not_treated_as_known_truth_by_default():
    answer = diagnostics(np.ones(3, bool), np.zeros((3, 3), bool),
                         np.full((3, 3, 4), np.inf))
    assert answer["family_coverage"] is None
    assert answer["false_elimination"] is None
    assert answer["true_pareto_size"] is None


def test_scenario_checkpoint_resume_requires_complete_unique_method_grid(tmp_path):
    scenario = "IID_CLEAR_KNOWN_SPECIFIC_SUPPORT"
    rows = [{"scenario": scenario, "repetition": repetition, "method": method}
            for repetition in range(2) for method in METHODS]
    path = tmp_path / "CHECKPOINT_00.csv"
    write_csv(path, rows)

    restored = read_scenario_checkpoint(path, scenario=scenario, repetitions=2)
    assert len(restored) == 2 * len(METHODS)
    assert {row["method"] for row in restored} == set(METHODS)
    assert {row["repetition"] for row in restored} == {0, 1}

    incomplete = tmp_path / "CHECKPOINT_01.csv"
    write_csv(incomplete, rows[:-1])
    with pytest.raises(ContractError, match="incomplete"):
        read_scenario_checkpoint(incomplete, scenario=scenario, repetitions=2)

    duplicate = tmp_path / "CHECKPOINT_02.csv"
    write_csv(duplicate, rows + [rows[0]])
    with pytest.raises(ContractError, match="incomplete"):
        read_scenario_checkpoint(duplicate, scenario=scenario, repetitions=2)


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_bad_panel_is_rejected_instead_of_silently_filtered(bad):
    panel = np.zeros((16, 2, 1, 4))
    panel[3, 1, 0, 0] = bad
    with pytest.raises(ContractError):
        day_bootstrap(panel)
