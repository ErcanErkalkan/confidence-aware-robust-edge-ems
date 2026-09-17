from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .mo_utils import nondominated_indices


@dataclass
class OptimizerResult:
    method_id: str
    positions: np.ndarray
    objectives: np.ndarray
    evaluations_used: int

    @property
    def nondominated_positions(self) -> np.ndarray:
        idx = nondominated_indices(self.objectives)
        return self.positions[idx]

    @property
    def nondominated_objectives(self) -> np.ndarray:
        idx = nondominated_indices(self.objectives)
        return self.objectives[idx]


def evaluate_population(oracle, x: np.ndarray, method_id: str, start_index: int = 0) -> tuple[np.ndarray, np.ndarray]:
    xs: list[np.ndarray] = []
    fs: list[np.ndarray] = []
    for i, row in enumerate(np.asarray(x, dtype=float)):
        if not oracle.can_evaluate():
            break
        cid = f'{method_id}-e{start_index + i + 1:06d}'
        f = oracle.evaluate(row, cid)
        xs.append(np.asarray(row, dtype=float))
        fs.append(np.asarray(f, dtype=float))
    if not xs:
        return np.empty((0, x.shape[1])), np.empty((0, oracle.n_obj))
    return np.asarray(xs), np.asarray(fs)
