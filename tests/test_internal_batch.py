from __future__ import annotations

from pathlib import Path

import pytest

from opencem_internal_test import _resolve_selection_dir


def _make_selection(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "selection_lock.json").write_text("{}", encoding="utf-8")
    (path / "selected_candidates.csv").write_text("method,candidate_id\n", encoding="utf-8")


def test_resolve_selection_dir_accepts_direct_and_batch_layouts(tmp_path):
    direct = tmp_path / "validation_selection_seed1001"
    _make_selection(direct)
    assert _resolve_selection_dir(tmp_path, seed=1001) == direct

    nested_root = tmp_path / "nested"
    nested = nested_root / "artifact" / "outputs" / "validation_selection_seed1002"
    _make_selection(nested)
    assert _resolve_selection_dir(nested_root, seed=1002) == nested


def test_resolve_selection_dir_fails_closed_on_duplicates(tmp_path):
    _make_selection(tmp_path / "a" / "validation_selection_seed1003")
    _make_selection(tmp_path / "b" / "validation_selection_seed1003")
    with pytest.raises(RuntimeError, match="exactly one"):
        _resolve_selection_dir(tmp_path, seed=1003)
