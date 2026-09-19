from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from .protocol import (
    SELECTION_FINAL_TIE_BREAK,
    SELECTION_PRIMARY_METRIC,
    SELECTION_RANGE_EPS,
    SELECTION_RULE_ID,
    SELECTION_SECONDARY_METRIC,
)


def score_validation_candidates(
    candidate_scores: pd.DataFrame,
    *,
    objectives: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """Normalize minimization objectives over the common validation candidate pool.

    The common reference set is the union of all method-front candidates for one
    optimizer seed. Each objective is scaled to [0,1] using the observed
    validation minimum and maximum. Degenerate objectives contribute zero.
    """
    required = {"method", "candidate_id", *objectives}
    missing = sorted(required - set(candidate_scores.columns))
    if missing:
        raise KeyError(f"validation candidate scores missing columns: {missing}")
    if candidate_scores.empty:
        raise ValueError("validation candidate score table is empty")
    if candidate_scores[["method", "candidate_id"]].duplicated().any():
        raise ValueError("duplicate (method, candidate_id) rows in validation scores")

    out = candidate_scores.copy()
    refs: dict[str, dict[str, float]] = {}
    normalized_cols: list[str] = []
    for objective in objectives:
        x = pd.to_numeric(out[objective], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(x).all():
            raise ValueError(f"non-finite validation objective: {objective}")
        ideal = float(np.min(x))
        worst = float(np.max(x))
        span = worst - ideal
        col = f"norm__{objective}"
        if span <= SELECTION_RANGE_EPS:
            out[col] = 0.0
            degenerate = True
        else:
            out[col] = (x - ideal) / span
            degenerate = False
        normalized_cols.append(col)
        refs[objective] = {
            "ideal": ideal,
            "observed_worst": worst,
            "span": float(span),
            "degenerate": bool(degenerate),
        }

    norm = out[normalized_cols].to_numpy(dtype=float)
    out[SELECTION_PRIMARY_METRIC] = np.max(norm, axis=1)
    out[SELECTION_SECONDARY_METRIC] = np.sum(norm, axis=1)
    out["selection_rule_id"] = SELECTION_RULE_ID
    return out, refs


def select_one_per_method(
    scored: pd.DataFrame,
) -> pd.DataFrame:
    """Select one candidate per method with deterministic prelocked tie-breaks."""
    required = {
        "method",
        "candidate_id",
        SELECTION_PRIMARY_METRIC,
        SELECTION_SECONDARY_METRIC,
    }
    missing = sorted(required - set(scored.columns))
    if missing:
        raise KeyError(f"scored validation table missing columns: {missing}")
    if scored.empty:
        raise ValueError("scored validation table is empty")

    selected = []
    for method, group in scored.groupby("method", sort=True):
        g = group.sort_values(
            [SELECTION_PRIMARY_METRIC, SELECTION_SECONDARY_METRIC, "candidate_id"],
            kind="mergesort",
        )
        selected.append(g.iloc[0].copy())
    out = pd.DataFrame(selected).reset_index(drop=True)
    out["selection_tie_break"] = (
        f"{SELECTION_PRIMARY_METRIC} -> {SELECTION_SECONDARY_METRIC} -> "
        f"{SELECTION_FINAL_TIE_BREAK}"
    )
    return out


def score_validation_candidates_with_reference(
    candidate_scores: pd.DataFrame,
    *,
    objectives: Sequence[str],
    references: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """Score candidates using an already frozen validation normalization reference.

    Values are intentionally not clipped to [0, 1]. A later candidate may lie
    outside the primary observed range; preserving that information avoids
    silently changing the selection geometry.
    """
    required = {"method", "candidate_id", *objectives}
    missing = sorted(required - set(candidate_scores.columns))
    if missing:
        raise KeyError(f"validation candidate scores missing columns: {missing}")
    if candidate_scores.empty:
        raise ValueError("validation candidate score table is empty")
    if candidate_scores[["method", "candidate_id"]].duplicated().any():
        raise ValueError("duplicate (method, candidate_id) rows in validation scores")

    out = candidate_scores.copy()
    normalized_cols: list[str] = []
    for objective in objectives:
        if objective not in references:
            raise KeyError(f"normalization reference missing objective: {objective}")
        ref = references[objective]
        x = pd.to_numeric(out[objective], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(x).all():
            raise ValueError(f"non-finite validation objective: {objective}")
        ideal = float(ref["ideal"])
        span = float(ref["span"])
        degenerate = bool(ref.get("degenerate", span <= SELECTION_RANGE_EPS))
        col = f"norm__{objective}"
        if degenerate or span <= SELECTION_RANGE_EPS:
            out[col] = 0.0
        else:
            out[col] = (x - ideal) / span
        normalized_cols.append(col)

    norm = out[normalized_cols].to_numpy(dtype=float)
    out[SELECTION_PRIMARY_METRIC] = np.max(norm, axis=1)
    out[SELECTION_SECONDARY_METRIC] = np.sum(norm, axis=1)
    out["selection_rule_id"] = SELECTION_RULE_ID
    out["normalization_reference_source"] = "primary_validation_lock"
    return out
