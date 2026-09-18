from __future__ import annotations

import numpy as np
import pandas as pd

from crmt_edge_ems.statistics import (
    descriptive_table,
    friedman_table,
    holm_adjust,
    paired_bootstrap_median_difference,
    paired_rank_biserial,
    pairwise_paired_table,
)


def test_holm_adjust_is_monotone_in_sorted_p_order():
    raw = np.array([0.03, 0.001, 0.02, 0.8])
    adj = holm_adjust(raw)
    assert np.all((adj >= raw) & (adj <= 1.0))
    order = np.argsort(raw)
    assert np.all(np.diff(adj[order]) >= -1e-15)


def test_paired_rank_biserial_direction_and_zero_case():
    assert paired_rank_biserial([1, 1, 1], [1, 1, 1]) == 0.0
    assert paired_rank_biserial([3, 4, 5], [1, 2, 3]) > 0
    assert paired_rank_biserial([1, 2, 3], [3, 4, 5]) < 0


def test_bootstrap_median_difference_is_deterministic():
    a = np.arange(30, dtype=float)
    b = a + 2.0
    x = paired_bootstrap_median_difference(
        a, b, n_boot=1000, seed=9
    )
    y = paired_bootstrap_median_difference(
        a, b, n_boot=1000, seed=9
    )
    assert x == y
    assert x[0] == -2.0


def test_paired_tables_require_complete_seed_design():
    rows = []
    for seed in range(5):
        for method, offset in [("A", 0.0), ("B", 1.0), ("C", 2.0)]:
            rows.append({"seed": seed, "method": method, "m": seed + offset})
    df = pd.DataFrame(rows)
    f = friedman_table(df, metrics=["m"], methods=["A", "B", "C"])
    p = pairwise_paired_table(
        df,
        metrics=["m"],
        methods=["A", "B", "C"],
        n_boot=1000,
        bootstrap_seed=11,
        alpha=0.05,
        direction={"m": "minimize"},
    )
    d = descriptive_table(df, metrics=["m"])
    assert len(f) == 1
    assert len(p) == 3
    assert len(d) == 3
    assert np.isfinite(p["p_value_holm"]).all()
