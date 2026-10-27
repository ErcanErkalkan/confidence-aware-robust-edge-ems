"""Opt-in fail-closed replay v2 for FUTURE experiments, not historical reruns.

The historical ReplayBlock/ReplayEvaluator/RiskConfig definitions remain unchanged.
This module does not grant preregistration or independent TEST authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd

from .contracts import ContractError, OBJECTIVES, finite_array, integer, strict_risk
from .replay import ReplayBlock, ReplayEvaluator
from .risk import RiskConfig


@dataclass(frozen=True)
class StrictReplayBlock(ReplayBlock):
    """Use only with predeclared cadence and scientific partition metadata."""

    cadence_minutes: int = 2
    expected_ticks: int | None = None

    def validated_profile(self) -> pd.DataFrame:
        if not isinstance(self.block_id, str) or not self.block_id.strip():
            raise ContractError('strict replay requires a nonempty block ID')
        integer(self.cadence_minutes, 'cadence_minutes', 1)
        if self.expected_ticks is not None:
            integer(self.expected_ticks, 'expected_ticks', 2)
        if not isinstance(self.profile, pd.DataFrame):
            raise ContractError('profile must be a pandas DataFrame')
        required = {'timestamp', 'base_kw', 'peak_flag'}
        if not required.issubset(self.profile.columns):
            raise ContractError('profile missing required columns')
        p = self.profile.copy()
        if len(p) < 2 or (self.expected_ticks is not None and len(p) != self.expected_ticks):
            raise ContractError('replay block length/declared support mismatch')
        if any(not pd.api.types.is_numeric_dtype(p[c]) for c in ('base_kw', 'peak_flag')):
            raise ContractError('base_kw/peak_flag must have numeric dtype, not strings')
        if pd.api.types.is_bool_dtype(p['peak_flag']):
            raise ContractError('peak_flag must be explicit 0/1 numbers')
        base = finite_array(p['base_kw'].to_numpy(), 'base_kw', ndim=1)
        peak = finite_array(p['peak_flag'].to_numpy(), 'peak_flag', ndim=1)
        if not np.isin(peak, [0, 1]).all():
            raise ContractError('peak_flag must contain exact 0 or 1, without coercion')
        try:
            timestamps = pd.DatetimeIndex(pd.to_datetime(p['timestamp'], errors='raise'))
        except (ValueError, TypeError, OverflowError) as exc:
            raise ContractError('invalid replay timestamps') from exc
        if timestamps.tz is None or timestamps.hasnans or timestamps.has_duplicates or not timestamps.is_monotonic_increasing:
            raise ContractError('timestamps must be timezone-aware, complete, unique and ordered')
        ns = timestamps.as_unit('ns').asi8
        expected_step_ns = self.cadence_minutes * 60 * 1_000_000_000
        if not np.all(np.diff(ns) == expected_step_ns):
            raise ContractError('replay cadence mismatch or missing time window')
        p['timestamp'] = timestamps
        p['base_kw'] = base
        p['peak_flag'] = peak.astype(np.int64)
        return p


class StrictReplayEvaluator(ReplayEvaluator):
    """Explicit opt-in; cannot silently use weaker legacy replay validation."""

    def evaluate_block(self, params, block, *, candidate_id):
        if not isinstance(block, StrictReplayBlock):
            raise ContractError('future replay requires StrictReplayBlock')
        block.validated_profile()  # Must preflight before ledger reservation.
        return super().evaluate_block(params, block, candidate_id=candidate_id)

    def evaluate(self, params, blocks, *, candidate_id):
        blocks = list(blocks)
        if not blocks or any(not isinstance(b, StrictReplayBlock) for b in blocks):
            raise ContractError('nonempty sequence of StrictReplayBlock required')
        ids = [b.block_id for b in blocks]
        if len(ids) != len(set(ids)):
            raise ContractError('duplicate replay block ID')
        for block in blocks:
            block.validated_profile()  # Reject bad later blocks before budget reservation.
        return super().evaluate(params, blocks, candidate_id=candidate_id)

    @staticmethod
    def aggregate(metrics: pd.DataFrame, risk: RiskConfig = RiskConfig()) -> dict[str, float]:
        if not isinstance(metrics, pd.DataFrame) or tuple(risk.objectives) != OBJECTIVES:
            raise ContractError('strict aggregation requires four canonical objectives')
        if any(c not in metrics.columns for c in OBJECTIVES):
            raise ContractError('missing objective columns')
        matrix = finite_array(metrics[list(OBJECTIVES)].to_numpy(), 'strict replay objective matrix', ndim=2)
        score = strict_risk(matrix, q=risk.q, tail_weight=risk.tail_weight)
        return dict(zip(OBJECTIVES, map(float, score), strict=True))