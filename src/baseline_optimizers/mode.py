from __future__ import annotations

import numpy as np

from .common import OptimizerResult, evaluate_population
from .mo_utils import environmental_select


def run_mode(oracle, *, seed: int, pop_size: int = 40, differential_weight: float = 0.5, crossover_rate: float = 0.9) -> OptimizerResult:
    if pop_size < 4:
        raise ValueError('pop_size must be >= 4')
    if not (0.0 < differential_weight <= 2.0 and 0.0 <= crossover_rate <= 1.0):
        raise ValueError('invalid MODE hyperparameters')
    rng = np.random.default_rng(seed)
    x, f = evaluate_population(oracle, rng.random((pop_size, oracle.dim)), 'MODE')
    if len(x) < 4:
        raise RuntimeError('MODE needs at least four evaluated initial individuals')
    eval_index = len(x)
    while oracle.can_evaluate() and len(x) >= 4:
        trials = []
        n = len(x)
        for i in range(n):
            pool = np.delete(np.arange(n), i)
            r1, r2, r3 = rng.choice(pool, size=3, replace=False)
            mutant = np.clip(x[r1] + differential_weight * (x[r2] - x[r3]), 0.0, 1.0)
            jrand = int(rng.integers(0, oracle.dim))
            mask = rng.random(oracle.dim) < crossover_rate
            mask[jrand] = True
            trial = np.where(mask, mutant, x[i])
            trials.append(trial)
        tx, tf = evaluate_population(oracle, np.asarray(trials), 'MODE', eval_index)
        if len(tx) == 0:
            break
        eval_index += len(tx)
        x, f = environmental_select(np.vstack([x, tx]), np.vstack([f, tf]), min(pop_size, len(x) + len(tx)))
    return OptimizerResult('MODE', x, f, oracle.evaluations_used)
