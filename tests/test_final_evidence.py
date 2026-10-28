"""Evidence reports must retain byte provenance and refuse scientific promotion."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

import build_final_evidence as report


def passing_xml(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<testsuites tests="1"><testsuite tests="1"><testcase name="example"/></testsuite></testsuites>', encoding="utf-8")


def test_junit_nested_suites_counts_cases_once(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text('<testsuites><testsuite tests="2"><testcase name="ok"/><testcase name="bad"><failure>no</failure></testcase></testsuite></testsuites>')
    result = report.parse_junit(path)
    assert result["tests"] == 2
    assert result["failures"] == 1
    assert result["passed_count"] == 1
    assert result["passed"] is False


def test_source_hash_separates_eol_equivalence_from_content_drift(tmp_path, monkeypatch):
    data = b"one\ntwo\n"
    expected = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    (tmp_path / "active.py").write_bytes(data.replace(b"\n", b"\r\n"))
    def fake_git(root, *args):
        if args[0] == "rev-parse":
            return b"a" * 40 + b"\n"
        if args[0] == "ls-tree":
            return ("100644 blob " + expected + "\tactive.py\0").encode()
        return b""
    monkeypatch.setattr(report, "git", fake_git)
    result = report.source_integrity(tmp_path)
    assert result["passed"] is True
    assert result["records"][0]["verification_result"] == "NEWLINE_EQUIVALENT"
    (tmp_path / "active.py").write_bytes(b"changed\n")
    result = report.source_integrity(tmp_path)
    assert result["passed"] is False
    assert result["records"][0]["verification_result"] == "CONTENT_DIFFERENCE"


def test_reports_never_promote_producer_science_claims_and_manifest_rechecks(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "source_integrity", lambda root: {
        "git_commit": "a" * 40, "passed": True, "records": [], "errors": []})
    for relative in report.GROUPS.values():
        path = tmp_path / relative / "summary.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"scientific_validated": True, "status": "VERIFIED_COMPLETE",
                                    "actual_simulator_events": 16}), encoding="utf-8")
    junit = tmp_path / "reports/test_results/junit.xml"
    passing_xml(junit)
    out = tmp_path / "reports/final"
    result = report.build(tmp_path, out, junit)
    assert result["engineering_complete"] is True
    state = json.loads((out / "FINAL_STATUS.json").read_text(encoding="utf-8"))
    assert state["CALIBRATION_SCIENTIFICALLY_VALIDATED"] == "NO"
    assert state["R19_PROSPECTIVE_READY"] == "NO"
    assert state["INDEPENDENT_TEST_EXECUTED"] == "NO"
    assert state["PHYSICAL_SAFETY_VALIDATED"] == "NO"
    assert state["GITHUB_MAIN_SYNCED"] == state["GOOGLE_DRIVE_SYNCED"] == "NO"
    manifest = json.loads((out / "ARTIFACT_MANIFEST_SHA256.json").read_text(encoding="utf-8"))
    assert manifest["self_excluded"] == "ARTIFACT_MANIFEST_SHA256.json"
    assert all(row["artifact_id"] != "ARTIFACT_MANIFEST_SHA256.json" for row in manifest["artifacts"])
    for row in manifest["artifacts"]:
        assert report.file_sha(tmp_path / row["source_path"]) == row["sha256"]
    assert all((out / name).is_file() for name in report.REQUIRED)
    with (out / "R19_EFFECT_FEASIBILITY.csv").open(encoding="utf-8-sig") as stream:
        grid = list(csv.DictReader(stream))
    assert len(grid) == 256
    assert grid[199]["effect_geometrically_possible"] == "True"
    assert grid[200]["effect_geometrically_possible"] == "False"
    assert float(grid[255]["sharp_max_abs_delta_miss"]) == 0
    with (out / "A01_A32_FINAL_TRACKER.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == 32


def test_missing_junit_and_invalid_json_remain_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "source_integrity", lambda root: {
        "git_commit": None, "passed": False, "records": [], "errors": ["not a Git checkout"]})
    path = tmp_path / "reports/calibration_v2/invalid.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"coverage": NaN}')
    result = report.build(tmp_path, tmp_path / "reports/final", tmp_path / "missing.xml")
    assert result["engineering_complete"] is False
    state = json.loads((tmp_path / "reports/final/FINAL_STATUS.json").read_text(encoding="utf-8"))
    assert state["SOFTWARE_READY"] == "NO"
    assert state["engineering_input_errors"][0]["source_path"].endswith("invalid.json")


def test_output_cannot_escape_checkout(tmp_path):
    with pytest.raises(ValueError, match="within the checkout"):
        report.build(tmp_path, tmp_path.parent / "escaped", tmp_path / "missing.xml")


def test_junit_collection_error_without_testcases_is_not_lost(tmp_path):
    path = tmp_path / "collection.xml"
    path.write_text('<testsuites><testsuite tests="0" errors="1"><error>collection failed</error></testsuite></testsuites>')
    result = report.parse_junit(path)
    assert result["passed"] is False
    assert result["errors"] == 1
    assert "no testcase" in result["blocking_reason"]
