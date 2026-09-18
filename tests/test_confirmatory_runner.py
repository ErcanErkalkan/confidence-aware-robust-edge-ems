from __future__ import annotations

import numpy as np
import pandas as pd

from crmt_edge_ems.protocol import CRMT_HYPERPARAMETERS
from crmt_edge_ems.replay import ReplayBlock
from jer_microgrid.config import SiteConfig
import opencem_confirmatory_train as runner


def _profile(offset: float = 0.0) -> pd.DataFrame:
    ts = pd.date_range(
        "2026-01-01",
        periods=30,
        freq="2min",
        tz="UTC",
    )
    x = np.linspace(0, 2 * np.pi, len(ts))
    return pd.DataFrame(
        {
            "timestamp": ts,
            "base_kw": offset + np.sin(x),
            "peak_flag": np.zeros(len(ts), dtype=int),
        }
    )


def _blocks() -> list[ReplayBlock]:
    return [
        ReplayBlock(
            "b1", _profile(0.0), source="unit", split="train", site_id=1
        ),
        ReplayBlock(
            "b2", _profile(0.1), source="unit", split="train", site_id=2
        ),
        ReplayBlock(
            "b3", _profile(0.2), source="unit", split="train", site_id=1
        ),
        ReplayBlock(
            "b4", _profile(0.3), source="unit", split="train", site_id=2
        ),
    ]


def _test_sites():
    s1 = SiteConfig(soc_min=0.1, soc_max=1.0, soc_init=0.5)
    s2 = SiteConfig(soc_min=0.1, soc_max=1.0, soc_init=0.5)
    return {1: s1, 2: s2}


def test_small_baseline_runner_uses_exact_controller_block_budget(monkeypatch):
    monkeypatch.setattr(runner, "_sites", _test_sites)
    result, oracle, ledger = runner.run_baseline(
        "NSGAII",
        7,
        _blocks(),
        budget=16,
        hyperparameters={
            "pop_size": 4,
            "crossover_prob": 0.9,
            "eta_c": 15.0,
            "eta_m": 20.0,
        },
    )
    assert ledger.used == 16
    assert len(oracle.evaluation_records) == 4
    assert result.evaluations_used == 16


def test_small_crmt_runner_uses_exact_budget_and_both_sites(monkeypatch):
    monkeypatch.setattr(runner, "_sites", _test_sites)
    hp = dict(CRMT_HYPERPARAMETERS)
    hp.update(
        {
            "initial_blocks": 2,
            "allocation_batch": 1,
            "n_boot": 200,
        }
    )
    result, candidates, evaluator, ledger = runner.run_crmt(
        7,
        _blocks(),
        budget=8,
        candidate_pool_size=2,
        hyperparameters=hp,
    )
    assert ledger.used == 8
    assert result.budget_used == 8
    assert len(candidates) == 2
    assert all(
        len(df) == 4
        for df in result.candidate_metrics.values()
    )


def test_front_frame_contains_repaired_unit_and_physical_parameters(monkeypatch):
    monkeypatch.setattr(runner, "_sites", _test_sites)
    result, oracle, _ = runner.run_baseline(
        "SOBOL",
        5,
        _blocks(),
        budget=8,
        hyperparameters={"batch_size": 2},
    )
    front = runner._front_frame(
        "SOBOL",
        result,
        runner._risk().objectives,
    )
    assert not front.empty
    assert all(f"u{i}" in front.columns for i in range(9))
    assert set(runner.PARAM_NAMES).issubset(front.columns)
