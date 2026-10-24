"""Integrity assertions for the *derived R18 receipt*, not source-byte re-auditing.

The CSV's 8 remote-only pairs do NOT become locally SHA-verified by this test.
For original source-byte checks use the separately archived R18 Drive package.
"""
from pathlib import Path
import csv

RECEIPT = (Path(__file__).resolve().parents[1] /
           "reproducibility/r18_archive_membership_20261024/R18_MEMBERSHIP_20.csv")


def _rows():
    with RECEIPT.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_r18_pair_completeness():
    rows = _rows()
    assert len(rows) == 20
    assert {(int(r["seed"]), int(r["C"]), int(r["A"])) for r in rows} == {
        (s, c, a) for s in range(1001, 1006) for c in (0, 1) for a in (0, 1)
    }


def test_r18_archive_intersection_math_and_scope():
    rows = _rows()
    exceptions = []
    locally_checked = 0
    for row in rows:
        f0 = int(row["F0_archive_size"])
        f1 = int(row["F1_archive_size"])
        intersection = int(row["intersection"])
        only0 = int(row["F0_only_count"])
        only1 = int(row["F1_only_count"])
        assert f0 - intersection == only0
        assert f1 - intersection == only1
        assert 0 <= intersection <= min(f0, f1)
        if only0:
            exceptions.append((int(row["seed"]), int(row["C"]), int(row["A"]),
                               row["F0_only_candidate"]))
        if row["source_evidence_scope"] == "LOCALLY_PACKED_SHA_CHECKED_ORIGINAL_FRONT":
            locally_checked += 1
        else:
            assert row["source_evidence_scope"] == "DRIVE_CONNECTOR_MEMBERSHIP_ONLY_NOT_LOCALLY_PACKED"
    assert locally_checked == 12
    assert len(rows) - locally_checked == 8
    assert exceptions == [(1001, 0, 0, "CRMT-c0089"), (1001, 1, 0, "CRMT-c0089")]


def test_r18_natural_archives_not_equal_capacity():
    rows = _rows()
    assert sum(int(r["F0_archive_size"]) for r in rows) / 20 == 83.60
    assert sum(int(r["F1_archive_size"]) for r in rows) / 20 == 226.95
