"""Fail-closed synthetic tests for R9 draft policy; no empirical or TEST data."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

FILE = Path(__file__).resolve().parents[1] / "tools" / "r9_equal_capacity_20261023" / "r9_capacity.py"
SPEC = importlib.util.spec_from_file_location("crmt_r9_capacity_draft", FILE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PolicyBlocked = MODULE.PolicyBlocked


def sample(n=24):
    scores = {f"c{i:02}": [float(i), float(i), float(i), float(i)] for i in range(n)}
    ledger = [{"candidate_id": f"c{i:02}", "block_id": "TRAIN-block-01"} for i in range(n)]
    return {
        "source_role": "TRAIN", "capacity": 20, "k": 20,
        "expected_evaluations": n,
        "train_scores": scores,
        "f0_archive": [f"c{i:02}" for i in range(15)],
        "f1_archive": [f"c{i:02}" for i in range(23)],
        "f0_evaluations": copy.deepcopy(ledger),
        "f1_evaluations": copy.deepcopy(ledger),
    }


def test_capacity_guarantee_backfill_transparent():
    x = MODULE.build_draft_pair(sample())
    assert x["f0"]["backfill_count"] == 5
    assert x["f1"]["backfill_count"] == 0
    assert x["f0"]["bounded_archive_ids"] == [f"c{i:02}" for i in range(20)]
    assert len(x["f1"]["selected_k_ids"]) == 20
    assert x["same_final_k_ids"] is True
    assert x["status"].endswith("NOT_INDEPENDENT_TEST")


def test_trace_order_is_irrelevant_and_deterministic():
    x = sample()
    x["f1_evaluations"].reverse()
    r1 = MODULE.build_draft_pair(x)
    r2 = MODULE.build_draft_pair(x)
    assert r1 == r2
    assert r1["f0_evaluations"] == r1["f1_evaluations"] == 24


def test_f_archive_membership_can_change_selection():
    x = sample()
    x["f0_archive"] = ["c23", "c22", "c21", "c20", "c19", "c18", "c17", "c16", "c15", "c14", "c13", "c12", "c11", "c10", "c09"]
    r = MODULE.build_draft_pair(x)
    assert r["same_final_k_ids"] is False
    assert len(r["f0"]["selected_k_ids"]) == 20


@pytest.mark.parametrize("change", [
    lambda x: x.update(source_role="VALIDATION"),
    lambda x: x.update(source_role="TEST"),
    lambda x: x.update(source_role="historical TRAIN"),
    lambda x: x.update(capacity=25),
    lambda x: x.update(k=21),
    lambda x: x.update(expected_evaluations=25),
    lambda x: x["f0_archive"].append("c00"),
    lambda x: x["f1_archive"].append("unknown"),
    lambda x: x["f0_evaluations"].append({"candidate_id": "c00", "block_id": "TRAIN-block-01"}),
    lambda x: x["f1_evaluations"][1].update(block_id="different-block"),
    lambda x: x["f0_evaluations"][1].update(candidate_id="c00"),
    lambda x: x["train_scores"]["c00"].__setitem__(0, float("nan")),
    lambda x: x["train_scores"]["c00"].append(5.0),
    lambda x: x.update(capacity=True),
    lambda x: x.update(independent_test_scores={"c00": [0, 0, 0, 0]}),
    lambda x: x.update(unexpected_metadata="unsafe"),
    lambda x: x.update(f0_archive=[]),
])
def test_fail_closed_on_invalid_input(change):
    x = sample()
    change(x)
    with pytest.raises(PolicyBlocked):
        MODULE.build_draft_pair(x)


def test_constant_objective_tie_break_is_lexical():
    x = sample()
    for key in x["train_scores"]:
        x["train_scores"][key] = [1, 1, 1, 1]
    x["f0_archive"] = list(reversed(x["f0_archive"]))
    r = MODULE.build_draft_pair(x)
    assert r["train_ranked_ids"] == sorted(x["train_scores"])


def test_no_test_metrics_schema():
    r = MODULE.build_draft_pair(sample())
    assert not any("test_scores" in key for key in r)
    assert len(r["input_sha256"]) == 64
