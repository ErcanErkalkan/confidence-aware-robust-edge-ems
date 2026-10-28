"""Actual EMS backend integration, failure and source-binding regressions."""
import io
import json

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.contracts import ContractError, OBJECTIVES, canonical, file_hash
from crmt_edge_ems.engineering_fixtures import make_engineering_plan
from crmt_edge_ems.execution_backend import EMSExecutionBackend, STAGES
from crmt_edge_ems.safety import SafetyBlocked


def fixture_plan(tmp_path, **kwargs):
    root = tmp_path / "fixture"
    return root, make_engineering_plan(root, ticks=4, candidates=2, **kwargs)


def test_actual_ems_all_stages_and_content_bound_resume(tmp_path, monkeypatch):
    root, plan = fixture_plan(tmp_path)
    out = tmp_path / "execution"
    backend = EMSExecutionBackend(plan, data_root=root, output=out)
    result = backend.run()
    assert result["scientific_confirmation"] is False
    assert result["independent_TEST_executed"] is False
    assert result["locked"] is False
    assert result["actual_simulator_events"] == 8
    assert result["energy_joules"] is None
    assert set(backend.store.state["stages"]) == set(STAGES)
    assert all(row["status"] == "COMPLETE" for row in backend.store.state["stages"].values())
    discovery = backend.store.load("discovery")
    audit = backend.store.load("audit")
    assert discovery["charged_events"] == audit["events"] == 4
    assert len(discovery["candidates"]) == 2
    for metrics in discovery["metrics"].values():
        assert len(metrics) == 2
        assert np.isfinite([[row[o] for o in OBJECTIVES] for row in metrics]).all()
    assert all(r["status"] == "COMPLETED" and r["supervision"]["worker_terminated"]
               for r in discovery["receipts"] + audit["receipts"])
    hashes = {path.name: file_hash(path) for path in out.glob("*.json")}
    resumed = EMSExecutionBackend(plan, data_root=root, output=out)
    def no_reexecution(*args):
        raise AssertionError("completed simulator stages must not execute on resume")
    monkeypatch.setattr(resumed, "_execute", no_reexecution)
    assert resumed.run() == result
    assert hashes == {path.name: file_hash(path) for path in out.glob("*.json")}


def test_changed_source_bytes_are_rejected_before_execution_directory(tmp_path):
    root, plan = fixture_plan(tmp_path)
    target = root / plan["blocks"][0]["profile_path"]
    target.write_bytes(target.read_bytes() + b"\n")
    out = tmp_path / "execution"
    with pytest.raises(ContractError, match="byte hash mismatch"):
        EMSExecutionBackend(plan, data_root=root, output=out)
    assert not out.exists()


def test_parser_consumes_the_exact_verified_byte_snapshot(tmp_path, monkeypatch):
    root, plan = fixture_plan(tmp_path)
    target = root / plan["blocks"][0]["profile_path"]
    original_parser = pd.read_csv
    mutated = False
    def changing_file_after_hash_verified(source, *args, **kwargs):
        nonlocal mutated
        assert isinstance(source, io.BytesIO)
        if not mutated:
            target.write_text("concurrent changed bytes", encoding="utf-8")
            mutated = True
        return original_parser(source, *args, **kwargs)
    monkeypatch.setattr(pd, "read_csv", changing_file_after_hash_verified)
    backend = EMSExecutionBackend(plan, data_root=root, output=tmp_path / "execution")
    assert backend.blocks[0].profile["base_kw"].iloc[0] == pytest.approx(15.0)
    assert target.read_text(encoding="utf-8") == "concurrent changed bytes"


def test_changed_configuration_cannot_resume_prior_outputs(tmp_path):
    root, plan = fixture_plan(tmp_path)
    out = tmp_path / "execution"
    backend = EMSExecutionBackend(plan, data_root=root, output=out)
    backend.run("prepare")
    old_hash = file_hash(out / "prepare.json")
    altered = json.loads(canonical(plan))
    altered["risk_weight"] = 0.25
    with pytest.raises(ContractError, match="resume source/config/environment"):
        EMSExecutionBackend(altered, data_root=root, output=out)
    assert file_hash(out / "prepare.json") == old_hash


def test_forged_execution_source_commit_is_rejected(tmp_path):
    root, plan = fixture_plan(tmp_path)
    plan["execution_context"]["git_commit"] = "0" * 40
    out = tmp_path / "execution"
    with pytest.raises(ContractError, match="actual execution checkout"):
        EMSExecutionBackend(plan, data_root=root, output=out)
    assert not out.exists()


def test_prospective_gate_runs_before_any_filesystem_input_access():
    class ForbiddenPath:
        def __fspath__(self):
            raise AssertionError("blocked prospective command accessed filesystem")
    with pytest.raises(ContractError, match="NO_GO"):
        EMSExecutionBackend({"scope": "PROSPECTIVE"},
                            data_root=ForbiddenPath(), output=ForbiddenPath())


def test_independent_test_gate_does_not_start_engineering_stages(tmp_path):
    root, plan = fixture_plan(tmp_path)
    backend = EMSExecutionBackend(plan, data_root=root, output=tmp_path / "execution")
    with pytest.raises(ContractError, match="NO_GO"):
        backend.run("independent-test")
    assert backend.store.state["stages"] == {}


def test_failed_real_discovery_preserves_event_charges_and_cannot_auto_retry(tmp_path):
    root, plan = fixture_plan(tmp_path)
    target = root / plan["blocks"][0]["profile_path"]
    bad = pd.read_csv(target)
    bad["base_kw"] = 500.0
    bad.to_csv(target, index=False)
    plan["blocks"][0]["source_sha256"] = file_hash(target)
    plan["blocks"][0]["profile_sha256"] = file_hash(target)
    out = tmp_path / "execution"
    backend = EMSExecutionBackend(plan, data_root=root, output=out)
    with pytest.raises(SafetyBlocked, match="GRID_LIMIT"):
        backend.run("discovery")
    failure = json.loads((out / "discovery_event_failure.json").read_text(encoding="utf-8"))
    assert failure["used"] == 2
    assert [r["status"] for r in failure["receipts"]] == ["FAILED", "NOT_STARTED"]
    assert all(r["budget_charged"] for r in failure["receipts"])
    assert backend.store.state["stages"]["discovery"]["status"] == "FAILED"
    resumed = EMSExecutionBackend(plan, data_root=root, output=out)
    with pytest.raises(ContractError, match="cannot be silently retried"):
        resumed.run("discovery")
    assert not (out / "discovery.json").exists()


def test_tampered_completed_checkpoint_output_cannot_resume(tmp_path):
    root, plan = fixture_plan(tmp_path)
    out = tmp_path / "execution"
    backend = EMSExecutionBackend(plan, data_root=root, output=out)
    backend.run("prepare")
    (out / "prepare.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ContractError, match="checkpoint artifact mismatch"):
        EMSExecutionBackend(plan, data_root=root, output=out).run("prepare")


@pytest.mark.parametrize("change,message", [
    ({"discovery_budget": 5}, "unique candidate/block"),
    ({"allocation_batch": 0}, "allocation_batch"),
    ({"allocation_mode": "unknown"}, "allocation mode")])
def test_infeasible_budget_or_allocation_fails_before_store(tmp_path, change, message):
    root, plan = fixture_plan(tmp_path)
    plan.update(change)
    out = tmp_path / "execution"
    with pytest.raises(ContractError, match=message):
        EMSExecutionBackend(plan, data_root=root, output=out)
    assert not out.exists()


def test_forged_day_metadata_cannot_bypass_temporal_embargo(tmp_path):
    root, plan = fixture_plan(tmp_path)
    plan["blocks"][0]["day_id"] = "1999-01-01"
    with pytest.raises(ContractError, match="observed local-day"):
        EMSExecutionBackend(plan, data_root=root, output=tmp_path / "execution")


def test_physical_unit_cannot_change_site_identity_between_splits(tmp_path):
    root, plan = fixture_plan(tmp_path)
    plan["blocks"][-1]["site_id"] = "FORGED-OTHER-SITE"
    with pytest.raises(ContractError, match="change site identity"):
        EMSExecutionBackend(plan, data_root=root, output=tmp_path / "execution")
