from __future__ import annotations

import numpy as np
import pandas as pd

from crmt_edge_ems.protocol import METHOD_IDS, SITE_SENSITIVITY_VARIANTS
from crmt_edge_ems.risk import DEFAULT_OBJECTIVES
from opencem_sensitivity_report import sensitivity_contrast_table


def test_sensitivity_contrasts_are_paired_by_seed_and_holm_by_family():
    seeds = [1001, 1002, 1003]
    primary_rows = []
    sensitivity_rows = []
    variants = [v.variant_id for v in SITE_SENSITIVITY_VARIANTS]
    for method_i, method in enumerate(METHOD_IDS):
        for seed in seeds:
            base = {
                "seed": seed,
                "method": method,
            }
            for j, objective in enumerate(DEFAULT_OBJECTIVES):
                base[objective] = float(method_i + j + 0.01 * seed)
            primary_rows.append(base)
            for variant_i, variant in enumerate(variants):
                row = {
                    "seed": seed,
                    "variant_id": variant,
                    "method": method,
                }
                for j, objective in enumerate(DEFAULT_OBJECTIVES):
                    row[objective] = (
                        float(method_i + j + 0.01 * seed)
                        + 0.001 * variant_i
                    )
                sensitivity_rows.append(row)
    out = sensitivity_contrast_table(
        pd.DataFrame(primary_rows),
        pd.DataFrame(sensitivity_rows),
        n_boot=1000,
        bootstrap_seed=5,
        alpha=0.05,
    )
    expected = len(METHOD_IDS) * len(DEFAULT_OBJECTIVES) * len(variants)
    assert len(out) == expected
    assert set(out["n_seeds"]) == {3}
    assert np.all(
        out["p_value_holm_within_method_objective"]
        >= out["p_value_raw"]
    )
