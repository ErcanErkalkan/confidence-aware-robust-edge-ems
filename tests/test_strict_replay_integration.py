"""Strict future replay tests use real EMS controllers and metric calculations."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.budget import EvaluationLedger
from crmt_edge_ems.contracts import ContractError, OBJECTIVES
from crmt_edge_ems.parameter_space import fixed_controller_parameters
from crmt_edge_ems.safety import SafetyBlocked, require_population
from crmt_edge_ems.strict_replay_v2 import StrictReplayBlock, StrictReplayEvaluator
from crmt_edge_ems.metrics_v2 import METRICS_VERSION
from jer_microgrid.config import SiteConfig


def profile(start="2026-01-01", n=4, base=5.0):
    return pd.DataFrame({
        "timestamp": pd.date_range(start, periods=n, freq="2min", tz="UTC"),
        "base_kw": [base] * n, "peak_flag": [0] * n})


def block(block_id="B01", start="2026-01-01", **kwargs):
    values = dict(
        block_id=block_id, profile=profile(start), source="SYNTHETIC_ENGINEERING_FIXTURE",
        split="DISCOVERY", site_id="fixture-site", cadence_minutes=2, expected_ticks=4,
        source_sha256="a" * 64,
        transformation_parameters={"operation": "constructed_test_fixture"},
        physical_unit_id="fixture-physical-unit", data_version="fixture-v1",
        exposure_record_id="fixture-exposure-log", historical_exposure="EXPOSED")
    values.update(kwargs)
    return StrictReplayBlock(**values)


def evaluator(**kwargs):
    return StrictReplayEvaluator(SiteConfig(ts_hours=2 / 60), **kwargs)


def test_default_site_cadence_mismatch_is_rejected_before_budget():
    ledger = EvaluationLedger(2)
    ev = StrictReplayEvaluator(SiteConfig(), ledger=ledger)
    with pytest.raises(ContractError, match="SiteConfig"):
        ev.evaluate(fixed_controller_parameters(), [block()], candidate_id="c1")
    assert ledger.used == 0 and not ev.receipts


def test_renamed_overlapping_support_is_rejected_before_budget():
    ledger = EvaluationLedger(2)
    ev = evaluator(ledger=ledger)
    with pytest.raises(ContractError, match="overlapping"):
        ev.evaluate(fixed_controller_parameters(ev.site),
                    [block(), block("renamed-copy")], candidate_id="c1")
    assert ledger.used == 0


def test_adjacent_nonoverlapping_support_and_distinct_units_are_valid():
    ev = evaluator(strict_metadata=True)
    adjacent = block("adjacent", start="2026-01-01 00:08:00")
    independent = block("other-device", physical_unit_id="other-physical-unit")
    assert len(ev.validate_blocks([block(), adjacent, independent])) == 3


@pytest.mark.parametrize("field,value", [
    ("source", "public_replay"), ("split", "unspecified"), ("site_id", None),
    ("physical_unit_id", None), ("source_sha256", None), ("source_sha256", "z" * 64),
    ("transformation_parameters", None), ("transformation_parameters", {"scale": np.nan}),
    ("data_version", None), ("exposure_record_id", None), ("historical_exposure", None),
    ("expected_ticks", None)])
def test_strong_provenance_is_required_before_budget(field, value):
    ledger = EvaluationLedger(1)
    ev = evaluator(ledger=ledger, strict_metadata=True)
    with pytest.raises(ContractError):
        ev.evaluate(fixed_controller_parameters(ev.site),
                    [block(**{field: value})], candidate_id="c1")
    assert ledger.used == 0 and not ev.receipts


def test_exposed_data_cannot_be_relabelled_as_independent_test():
    ev = evaluator(strict_metadata=True)
    with pytest.raises(ContractError, match="exposed"):
        ev.validate_blocks([block(split="EXTERNAL_TEST")])


def test_scientific_metadata_mode_cannot_disable_hang_containment():
    with pytest.raises(ContractError, match="process containment"):
        evaluator(strict_metadata=True, supervisor=None)


def test_all_profiles_and_candidate_parameters_preflight_before_reservation():
    ledger = EvaluationLedger(2)
    ev = evaluator(ledger=ledger)
    bad = profile("2026-01-02")
    bad.loc[1, "base_kw"] = np.inf
    with pytest.raises(ContractError):
        ev.evaluate(fixed_controller_parameters(ev.site),
                    [block(), block("B02", profile=bad)], candidate_id="c1")
    assert ledger.used == 0
    parameters = fixed_controller_parameters(ev.site)
    parameters["lookahead_gain"] = float("nan")
    with pytest.raises(ValueError, match="Infeasible"):
        ev.evaluate(parameters, [block()], candidate_id="c1")
    assert ledger.used == 0


def test_nan_site_limits_fail_before_any_reservation():
    ledger = EvaluationLedger(2)
    ev = evaluator(ledger=ledger)
    ev.site.r_max_kw_per_tick = np.nan
    with pytest.raises(SafetyBlocked, match="INVALID_SITE_CONFIG"):
        ev.evaluate(fixed_controller_parameters(), [block()], candidate_id="c1")
    assert ledger.used == 0


def test_real_supervised_ems_path_uses_future_metrics_and_receipts():
    ledger = EvaluationLedger(2)
    ev = evaluator(ledger=ledger, strict_metadata=True, seed=17,
                   execution_binding={"protocol_sha256": "b" * 64,
                                      "scope": "ENGINEERING_SMOKE_NOT_PROSPECTIVE"})
    result = ev.evaluate(fixed_controller_parameters(ev.site),
                         [block(), block("B02", start="2026-01-02")], candidate_id="c1")
    assert len(result) == ledger.used == 2
    assert np.isfinite(result[list(OBJECTIVES)].to_numpy()).all()
    assert set(result["metrics_version"]) == {METRICS_VERSION}
    assert [r["status"] for r in ev.receipts] == ["COMPLETED", "COMPLETED"]
    assert all(r["supervision"]["worker_terminated"] for r in ev.receipts)
    assert all(r["scientific_scope"] == "INPUT_CONTRACT_VERIFIED_NOT_AUTHORIZATION"
               for r in ev.receipts)
    assert all(len(r["output_sha256"]) == 64 for r in ev.receipts)
    assert np.isfinite(list(ev.aggregate(result).values())).all()


def test_failed_actual_simulator_event_remains_charged_and_later_event_never_runs():
    ledger = EvaluationLedger(2)
    ev = evaluator(ledger=ledger)
    unsafe = block(profile=profile(base=500))
    with pytest.raises(SafetyBlocked, match="GRID_LIMIT"):
        ev.evaluate(fixed_controller_parameters(ev.site),
                    [unsafe, block("B02", start="2026-01-02")], candidate_id="c1")
    assert ledger.used == 2
    assert [r["status"] for r in ev.receipts] == ["FAILED", "NOT_STARTED"]
    assert [r["simulator_started"] for r in ev.receipts] == [True, False]
    assert all(r["budget_charged"] for r in ev.receipts)
    failure = ev.receipts[0]["failure"]
    assert failure["result_policy"] == "INVALID_RUN_EXCLUDED_NO_PARTIAL_METRICS"
    assert failure["receipt"]["supervision"]["worker_terminated"]


def test_entire_real_candidate_population_can_be_rejected_without_partial_result():
    ev = evaluator()
    accepted = []
    for candidate in ("candidate-1", "candidate-2"):
        with pytest.raises(SafetyBlocked, match="GRID_LIMIT"):
            ev.evaluate(fixed_controller_parameters(ev.site),
                        [block(profile=profile(base=500))], candidate_id=candidate)
    with pytest.raises(SafetyBlocked, match="ALL_CANDIDATES_REJECTED"):
        require_population(accepted)
    assert all(r["status"] == "FAILED" for r in ev.receipts)


def test_engineering_compatibility_is_explicitly_labelled():
    ev = evaluator(supervisor=None)
    minimal = StrictReplayBlock("engineering", profile(), cadence_minutes=2)
    result = ev.evaluate(fixed_controller_parameters(ev.site), [minimal], candidate_id="fixture")
    assert len(result) == 1
    assert ev.receipts[0]["scientific_scope"] == "ENGINEERING_ONLY"


@pytest.mark.parametrize("zone,day,count", [
    ("UTC", "2026-01-01", 720),
    ("America/New_York", "2026-11-01", 750)])
def test_full_local_day_requires_exact_dst_aware_support(zone, day, count):
    start = pd.Timestamp(day, tz=zone)
    times = pd.date_range(start, start + pd.DateOffset(days=1),
                          freq="2min", inclusive="left").tz_convert("UTC")
    assert len(times) == count
    p = pd.DataFrame({"timestamp": times, "base_kw": 5.0, "peak_flag": 0})
    full = block(profile=p, expected_ticks=count,
                 transformation_parameters={"full_day": True, "timezone": zone})
    ev = evaluator(strict_metadata=True)
    assert len(ev.validate_blocks([full])[0].profile) == count
    shifted = p.copy()
    shifted["timestamp"] += pd.Timedelta(minutes=2)
    with pytest.raises(ContractError, match="exact local-day"):
        ev.validate_blocks([replace(full, profile=shifted)])
