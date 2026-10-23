"""Check the declared CRMT historical TRAIN audit receipts for internal consistency.

This test checks immutable evidence INDEXES/receipts, not raw CSV re-downloads,
not a new R9 experiment, and never reads any independent TEST dataset.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "reproducibility" / "r9_historical_train_sources_20261023"

def _json(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))

def _key(row):
    return f"seed{int(row['seed'])}/C{int(row['C'])}_A{int(row['A'])}"

def test_40_conditions_20_pairs_with_honest_provenance():
    gate = _json("GLOBAL_SOURCE_PROVENANCE_GATE_20261023.json")
    assert gate["conditions"] == 40
    assert gate["conditions_with_declared_expected_source_commit"] == 39
    assert len(gate["pairs"]) == 20
    assert len(gate["conditions_with_missing_or_nonmatching_source_commit"]) == 1
    bad = gate["conditions_with_missing_or_nonmatching_source_commit"][0]
    assert bad["seed"] == 1001 and bad["condition"] == "C1_F1_A1"
    assert bad["found"] == "UNRECORDED_LOCAL_SHA"
    assert gate["raw_byte_pairs_verified_count"] + gate["raw_byte_pairs_unverified_count"] == 20
    assert gate["claimed_controller_block_evaluations"] == 504000

def test_csv_global_index_and_aggregate_receipt_agree():
    gate = _json("GLOBAL_SOURCE_PROVENANCE_GATE_20261023.json")
    summary = _json("R9_EIGHT_PAIR_BYTE_AUDIT_RECEIPT.json")
    with (BASE / "R9_TRAIN_PAIR_SUMMARY_20.csv").open(newline="", encoding="utf-8-sig") as handle:
        records = list(csv.DictReader(handle))
    assert len(records) == len({_key(x) for x in records}) == 20
    true_keys = {_key(x) for x in records if x["raw_bytes_verified"] == "TRUE" and x["science_fields_equal_raw"] == "TRUE"}
    for row in records:
        assert (row["raw_bytes_verified"],row["science_fields_equal_raw"]) in {("TRUE","TRUE"),("NOT_YET","NOT_YET")}
        assert row["F0_F1_ledger_SHA256_equal_per_run_summary"] == "TRUE"
        assert row["F0_F1_candidate_metrics_SHA256_equal_per_run_summary"] == "FALSE"
    assert true_keys == set(gate["raw_bytes_science_fields_verified_pilot_pairs"])
    assert true_keys == {x["pair"] for x in summary["verified_pairs"]}
    assert summary["actual_byte_verified_pairs"] == len(true_keys) == gate["raw_byte_pairs_verified_count"]
    assert summary["actual_byte_unverified_pairs"] == 20-len(true_keys)
    assert summary["R9_independent_TEST_performed"] is False
    assert summary["prospective_decision"] == "NO_GO"
    assert "seed1001/C1_A1" not in true_keys

def test_every_new_verification_receipt_has_source_hashes_and_budget():
    summary = _json("R9_EIGHT_PAIR_BYTE_AUDIT_RECEIPT.json")
    for item in summary["verified_pairs"]:
        if item["seed"] == 1001:
            prior = _json("verified_seed1001_C0_A0.json")
            assert prior["science_and_non_timing_metrics_equal"] is True
            assert prior["budget_per_condition"] == 12600
            continue
        receipt_name = f"seed{item['seed']}_C{item['C']}_A{item['A']}_repo_preflight.json"
        receipt = _json(receipt_name)
        assert receipt["status"] == "HISTORICAL_TRAIN_PAIRED_PREFLIGHT_ONLY_NOT_NEW_TEST"
        assert receipt["science_and_non_timing_metrics_equal"] is True
        assert receipt["identical_candidate_block_evaluation_pairs"] is True
        assert receipt["budget_per_condition"] == 12600
        assert receipt["archive_size_F0"] == item["archive_f0"]
        assert receipt["archive_size_F1"] == item["archive_f1"]
        for key in ("F0", "F1"):
            for fname in ("candidate_metrics.csv","ledger.csv","optimizer_front.csv"):
                value = receipt["input_sha256"][key][fname]
                assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)
