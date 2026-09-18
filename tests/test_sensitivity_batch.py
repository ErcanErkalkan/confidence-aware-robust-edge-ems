from __future__ import annotations

from pathlib import Path

import pytest

from opencem_sensitivity_suite import _resolve_primary_internal_dir


def _make_internal(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "internal_test_run_summary.json").write_text(
        "{}", encoding="utf-8"
    )


def test_resolve_primary_internal_dir_direct_and_nested(tmp_path):
    direct = tmp_path / "internal_test_seed1001"
    _make_internal(direct)
    assert _resolve_primary_internal_dir(tmp_path, seed=1001) == direct

    nested_root = tmp_path / "nested"
    nested = nested_root / "artifact" / "outputs" / "internal_test_seed1002"
    _make_internal(nested)
    assert _resolve_primary_internal_dir(
        nested_root, seed=1002
    ) == nested


def test_resolve_primary_internal_dir_fails_closed_on_duplicates(tmp_path):
    _make_internal(tmp_path / "a" / "internal_test_seed1003")
    _make_internal(tmp_path / "b" / "internal_test_seed1003")
    with pytest.raises(RuntimeError, match="exactly one"):
        _resolve_primary_internal_dir(tmp_path, seed=1003)
