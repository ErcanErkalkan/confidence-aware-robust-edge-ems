from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


class EvaluationBudgetExceeded(RuntimeError):
    """Raised before an evaluation batch would exceed the frozen budget."""


@dataclass(frozen=True)
class EvaluationEvent:
    ordinal: int
    method_id: str
    candidate_id: str
    block_id: str
    unit: str = "controller_block_evaluation"


class EvaluationLedger:
    """Central accounting for fair optimizer comparisons.

    One budget unit is exactly one controller configuration evaluated on one
    predeclared data/scenario block. Candidate proposal generation, archive
    sorting, and bootstrap calculations do not consume this budget because they
    do not execute the EMS simulator.

    The ledger reserves a whole batch atomically before simulation begins. This
    prevents methods from receiving a partial extra generation when the common
    budget is nearly exhausted. Reserved evaluations remain charged if a
    simulator call later fails; this avoids giving unstable methods free retries.
    """

    UNIT = "controller_block_evaluation"

    def __init__(self, max_evaluations: int):
        max_evaluations = int(max_evaluations)
        if max_evaluations <= 0:
            raise ValueError("max_evaluations must be > 0")
        self.max_evaluations = max_evaluations
        self._events: list[EvaluationEvent] = []

    @property
    def used(self) -> int:
        return len(self._events)

    @property
    def remaining(self) -> int:
        return self.max_evaluations - self.used

    def can_reserve(self, n: int) -> bool:
        return 0 <= int(n) <= self.remaining

    def reserve(self, method_id: str, candidate_id: str, block_ids: Iterable[str]) -> tuple[EvaluationEvent, ...]:
        blocks = tuple(str(x) for x in block_ids)
        if not blocks:
            return ()
        if len(set(blocks)) != len(blocks):
            raise ValueError("block_ids within one reservation must be unique")
        if len(blocks) > self.remaining:
            raise EvaluationBudgetExceeded(
                f"Requested {len(blocks)} evaluations with only {self.remaining} remaining "
                f"(budget={self.max_evaluations}, used={self.used})"
            )
        start = self.used
        events = tuple(
            EvaluationEvent(start + i + 1, str(method_id), str(candidate_id), block_id)
            for i, block_id in enumerate(blocks)
        )
        self._events.extend(events)
        return events

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([e.__dict__ for e in self._events], columns=[
            "ordinal", "method_id", "candidate_id", "block_id", "unit"
        ])

    def assert_exact(self) -> None:
        if self.used != self.max_evaluations:
            raise AssertionError(f"Budget not exhausted exactly: used={self.used}, max={self.max_evaluations}")
