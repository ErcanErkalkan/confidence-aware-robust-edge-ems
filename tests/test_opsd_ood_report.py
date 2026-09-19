from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from crmt_edge_ems.protocol import METHOD_IDS
from crmt_edge_ems.risk import DEFAULT_OBJECTIVES
from opsd_ood_report import _resolve_ood_seed_dir, build_opsd_ood_report


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_seed(root: Path, seed: int, offset: float = 0.0) -> None:
    d = root / f"opsd_ood_seed{seed}"
    d.mkdir(parents=True)
    rows = []
    for i, method in enumerate(METHOD_IDS):
        row = {
            "method": method,
            "candidate_id": f"{method}-{seed}",
            "n_strata": 6,
            "macro_weighting": "equal_household_x_target_site",
        }
        for j, metric in enumerate(DEFAULT_OBJECTIVES):
            row[metric] = float(offset + i + 0.1 * j)
        rows.append(row)
    macro = pd.DataFrame(rows)
    strata = pd.DataFrame(
        {"method": [METHOD_IDS[0]], "candidate_id": ["x"], "household": ["h"],
         "target_site_id": [1], "n_blocks": [1]}
    )
    pooled = macro[["method", "candidate_id", *DEFAULT_OBJECTIVES]].copy()
    paths = {}
    for name, frame in {
        "ood_macro_risk_summary.csv": macro,
        "ood_stratum_risk_summary.csv": strata,
        "ood_pooled_risk_summary.csv": pooled,
    }.items():
        p = d / name
        frame.to_csv(p, index=False, lineterminator="\n")
        paths[name] = _sha(p)
    summary = {
        "stage": "EXTERNAL_OOD_OPSD_FROZEN_SELECTION",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "seed": seed,
        "selection_lock_sha256": "sel",
        "selected_candidates_sha256": "cand",
        "primary_internal_test_summary_sha256": "internal",
        "source_context": {
            "package_sha256": "pkg",
            "full_replay_manifest_sha256": "replay",
        },
        "files_sha256": paths,
    }
    (d / "ood_run_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )


def test_ood_seed_resolver_accepts_nested_batch_layout(tmp_path):
    nested = tmp_path / "artifact" / "outputs" / "opsd_ood_seed1001"
    _make_seed(tmp_path / "artifact" / "outputs", 1001)
    assert _resolve_ood_seed_dir(tmp_path, seed=1001) == nested


def test_ood_seed_resolver_fails_closed_on_duplicate_evidence(tmp_path):
    _make_seed(tmp_path / "a", 1001)
    _make_seed(tmp_path / "b", 1001)
    with pytest.raises(RuntimeError, match="exactly one"):
        _resolve_ood_seed_dir(tmp_path, seed=1001)


def test_ood_report_uses_seed_as_paired_replication_unit(tmp_path):
    root = tmp_path / "ood"
    for seed in (1001, 1002, 1003):
        _make_seed(root, seed, offset=0.01 * seed)
    out = tmp_path / "out"
    summary = build_opsd_ood_report(
        ood_root=root,
        output_dir=out,
        seeds=(1001, 1002, 1003),
    )
    assert summary["statistical_protocol"]["inferential_unit"] == "optimizer_seed"
    df = pd.read_csv(out / "ood_macro_seed_metrics.csv")
    assert len(df) == 3 * len(METHOD_IDS)
    assert set(df["seed"]) == {1001, 1002, 1003}
