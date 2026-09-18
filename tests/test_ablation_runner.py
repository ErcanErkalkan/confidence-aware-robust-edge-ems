from __future__ import annotations

import numpy as np
import pandas as pd

from crmt_edge_ems.protocol import CRMT_HYPERPARAMETERS
from crmt_edge_ems.replay import ReplayBlock
from jer_microgrid.config import SiteConfig
import opencem_crmt_ablation_train as ablation
import opencem_confirmatory_train as train


def _profile(offset=0.0):
    ts = pd.date_range("2026-01-01", periods=24, freq="2min", tz="UTC")
    return pd.DataFrame({
        "timestamp": ts,
        "base_kw": offset + np.sin(np.linspace(0, 2*np.pi, len(ts))),
        "peak_flag": 0,
    })


def _blocks():
    return [
        ReplayBlock("b1", _profile(0.0), split="train", site_id=1),
        ReplayBlock("b2", _profile(0.1), split="train", site_id=2),
        ReplayBlock("b3", _profile(0.2), split="train", site_id=1),
        ReplayBlock("b4", _profile(0.3), split="train", site_id=2),
    ]


def _sites():
    return {1: SiteConfig(), 2: SiteConfig()}


def test_each_ablation_runs_same_small_exact_budget(monkeypatch):
    monkeypatch.setattr(train, "_sites", _sites)
    hp = dict(CRMT_HYPERPARAMETERS)
    hp.update({"initial_blocks": 2, "allocation_batch": 1, "n_boot": 200})
    settings = {
        "NO_CVAR": (0.0, "confidence", "adaptive"),
        "NO_CONFIDENCE": (0.5, "risk_pareto", "adaptive"),
        "NO_ADAPTIVE": (0.5, "confidence", "round_robin"),
    }
    for _, (tail, archive, allocation) in settings.items():
        from crmt_edge_ems.risk import RiskConfig
        result, candidates, evaluator, ledger = train.run_crmt(
            9,
            _blocks(),
            budget=8,
            candidate_pool_size=2,
            hyperparameters=hp,
            allocation_mode=allocation,
            archive_mode=archive,
            risk_override=RiskConfig(q=0.9, tail_weight=tail),
        )
        assert ledger.used == 8
        assert result.budget_used == 8
        assert len(candidates) == 2
