from __future__ import annotations

from pathlib import Path

import pytest

from opencem_validation_select import _resolve_train_run_dir


def _make_run(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "run_summary.json").write_text("{}", encoding="utf-8")
    (path / "optimizer_front.csv").write_text("candidate_id\n", encoding="utf-8")


def test_resolve_train_run_dir_accepts_direct_and_batch_layouts(tmp_path):
    direct = tmp_path / "SOBOL_seed1001"
    _make_run(direct)
    assert _resolve_train_run_dir(
        tmp_path, method="SOBOL", seed=1001
    ) == direct

    nested_root = tmp_path / "nested"
    nested = nested_root / "artifact" / "outputs" / "CRMT_seed1002"
    _make_run(nested)
    assert _resolve_train_run_dir(
        nested_root, method="CRMT", seed=1002
    ) == nested


def test_resolve_train_run_dir_fails_closed_on_duplicates(tmp_path):
    _make_run(tmp_path / "a" / "MODE_seed1003")
    _make_run(tmp_path / "b" / "MODE_seed1003")
    with pytest.raises(RuntimeError, match="exactly one"):
        _resolve_train_run_dir(tmp_path, method="MODE", seed=1003)
