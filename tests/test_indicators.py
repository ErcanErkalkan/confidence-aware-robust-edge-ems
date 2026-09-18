from __future__ import annotations

import numpy as np
import pandas as pd

from crmt_edge_ems.indicators import (
    additive_epsilon,
    exact_hypervolume,
    igd_plus,
    nondominated_points,
    validation_optimizer_indicators,
)


def test_exact_hypervolume_known_2d_union():
    points = np.array([[0.2, 0.8], [0.8, 0.2]])
    hv = exact_hypervolume(points, [1.0, 1.0])
    assert np.isclose(hv, 0.28)


def test_igd_plus_and_epsilon_are_zero_for_exact_reference():
    front = np.array([[0.2, 0.8], [0.8, 0.2]])
    assert np.isclose(igd_plus(front, front), 0.0)
    assert np.isclose(additive_epsilon(front, front), 0.0)


def test_nondominated_points_removes_dominated_and_duplicates():
    x = np.array([[0.2, 0.2], [0.2, 0.2], [0.3, 0.3], [0.1, 0.5]])
    out = nondominated_points(x)
    assert len(out) == 2
    assert any(np.allclose(row, [0.2, 0.2]) for row in out)
    assert any(np.allclose(row, [0.1, 0.5]) for row in out)


def test_validation_indicators_use_common_reference_and_handle_degenerate_axis():
    df = pd.DataFrame({
        "method": ["A", "A", "B", "B"],
        "o1": [1.0, 2.0, 2.0, 3.0],
        "o2": [5.0, 5.0, 5.0, 5.0],
    })
    out, refs = validation_optimizer_indicators(
        df, objectives=("o1", "o2"), hv_reference_value=1.10
    )
    assert set(out["method"]) == {"A", "B"}
    assert refs["o2"]["degenerate"] is True
    assert np.isfinite(out[["hypervolume", "igd_plus", "additive_epsilon"]]).all().all()
