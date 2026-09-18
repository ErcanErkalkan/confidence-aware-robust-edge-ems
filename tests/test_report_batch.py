from __future__ import annotations

from pathlib import Path

import pytest

from opencem_confirmatory_report import _resolve_seed_dir


REQ = ("a.json", "b.csv")


def _make(path: Path) -> None:
    path.mkdir(parents=True)
    for name in REQ:
        (path / name).write_text("x", encoding="utf-8")


def test_report_resolver_accepts_direct_and_nested_batch_layouts(tmp_path):
    direct = tmp_path / "validation_selection_seed1001"
    _make(direct)
    assert _resolve_seed_dir(
        tmp_path,
        name="validation_selection_seed1001",
        required_files=REQ,
    ) == direct

    nested_root = tmp_path / "nested"
    nested = nested_root / "artifact" / "outputs" / "internal_test_seed1002"
    _make(nested)
    assert _resolve_seed_dir(
        nested_root,
        name="internal_test_seed1002",
        required_files=REQ,
    ) == nested


def test_report_resolver_fails_closed_on_duplicate_evidence(tmp_path):
    _make(tmp_path / "a" / "validation_selection_seed1003")
    _make(tmp_path / "b" / "validation_selection_seed1003")
    with pytest.raises(RuntimeError, match="exactly one"):
        _resolve_seed_dir(
            tmp_path,
            name="validation_selection_seed1003",
            required_files=REQ,
        )
