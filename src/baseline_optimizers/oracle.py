from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

import numpy as np

from crmt_edge_ems.parameter_space import decode_unit_vector, repair_unit_vector
from crmt_edge_ems.risk import RiskConfig


class VectorOracle(Protocol):
    dim: int
    n_obj: int

    @property
    def evaluations_used(self) -> int: ...
    @property
    def candidate_evaluations_remaining(self) -> int: ...
    def can_evaluate(self) -> bool: ...
    def evaluate(self, unit: np.ndarray, candidate_id: str) -> np.ndarray: ...


@dataclass
class FunctionOracle:
    func: Callable[[np.ndarray], np.ndarray]
    dim: int
    n_obj: int
    max_evaluations: int
    repair: Callable[[np.ndarray], np.ndarray] | None = None

    def __post_init__(self):
        self._used = 0
        if self.max_evaluations <= 0:
            raise ValueError('max_evaluations must be > 0')

    @property
    def evaluations_used(self) -> int:
        return self._used

    @property
    def candidate_evaluations_remaining(self) -> int:
        return self.max_evaluations - self._used

    def can_evaluate(self) -> bool:
        return self._used < self.max_evaluations

    def evaluate(self, unit: np.ndarray, candidate_id: str) -> np.ndarray:
        if not self.can_evaluate():
            raise RuntimeError('candidate-evaluation budget exhausted')
        x = np.asarray(unit, dtype=float)
        x = self.repair(x) if self.repair is not None else np.clip(x, 0.0, 1.0)
        y = np.asarray(self.func(x), dtype=float)
        if y.shape != (self.n_obj,) or not np.isfinite(y).all():
            raise ValueError(f'oracle returned invalid objective vector shape/value: {y}')
        self._used += 1
        return y


class BlockRiskOracle:
    """Adapter from unit-cube candidates to the common CRMT block evaluator.

    Fairness accounting is delegated to the evaluator's EvaluationLedger. One
    candidate call costs exactly len(blocks) controller-block evaluations.
    """

    def __init__(self, evaluator, blocks: Iterable, *, risk: RiskConfig = RiskConfig()):
        self.evaluator = evaluator
        self.blocks = tuple(blocks)
        if not self.blocks:
            raise ValueError('at least one block is required')
        self.risk = risk
        self.dim = 9
        self.n_obj = len(risk.objectives)
        self._candidate_calls = 0

    @property
    def evaluations_used(self) -> int:
        ledger = getattr(self.evaluator, 'ledger', None)
        if ledger is not None:
            return int(ledger.used)
        return self._candidate_calls * len(self.blocks)

    @property
    def candidate_evaluations_remaining(self) -> int:
        ledger = getattr(self.evaluator, 'ledger', None)
        if ledger is None:
            raise RuntimeError('candidate capacity is undefined without an EvaluationLedger')
        return int(ledger.remaining // len(self.blocks))

    def can_evaluate(self) -> bool:
        ledger = getattr(self.evaluator, 'ledger', None)
        return True if ledger is None else ledger.remaining >= len(self.blocks)

    def evaluate(self, unit: np.ndarray, candidate_id: str) -> np.ndarray:
        if not self.can_evaluate():
            raise RuntimeError('insufficient controller-block budget for a complete candidate evaluation')
        site = getattr(self.evaluator, 'site', None)
        repaired = repair_unit_vector(unit, site=site)
        params = decode_unit_vector(repaired)
        df = self.evaluator.evaluate(params, self.blocks, candidate_id=str(candidate_id))
        agg = self.evaluator.aggregate(df, self.risk)
        objective = np.asarray([agg[k] for k in self.risk.objectives], dtype=float)
        if objective.shape != (self.n_obj,) or not np.isfinite(objective).all():
            raise ValueError(f'evaluator returned invalid objective vector shape/value: {objective}')
        self._candidate_calls += 1
        return objective
