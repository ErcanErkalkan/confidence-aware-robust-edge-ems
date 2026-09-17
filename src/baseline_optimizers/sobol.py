from __future__ import annotations

import math
import warnings
import numpy as np
from scipy.stats import qmc

from .common import OptimizerResult, evaluate_population
from .mo_utils import nondominated_indices


def _proposal_pool(engine: qmc.Sobol, n: int) -> np.ndarray:
    """Return at least ``n`` deterministic scrambled Sobol proposals.

    When the oracle exposes its remaining complete-candidate capacity, the
    sequence is generated once from the smallest power-of-two Sobol net that
    covers that capacity, then deterministically truncated. This avoids
    repeated non-balanced draws and SciPy warnings while retaining exact EMS
    evaluation-budget accounting.
    """
    n = int(n)
    if n <= 0:
        return np.empty((0, engine.d), dtype=float)
    m = int(math.ceil(math.log2(n))) if n > 1 else 0
    return engine.random_base2(m=m)[:n]


def run_sobol(oracle, *, seed: int, batch_size: int = 32) -> OptimizerResult:
    if batch_size <= 0:
        raise ValueError('batch_size must be > 0')
    engine = qmc.Sobol(d=oracle.dim, scramble=True, seed=seed)

    remaining = getattr(oracle, 'candidate_evaluations_remaining', None)
    if remaining is not None:
        try:
            n_target = int(remaining)
        except (TypeError, RuntimeError):
            n_target = 0
        if n_target > 0:
            proposals = _proposal_pool(engine, n_target)
            x, f = evaluate_population(oracle, proposals, 'SOBOL', 0)
            if len(x) == 0:
                raise RuntimeError('no budget for Sobol baseline')
            nd = nondominated_indices(f)
            return OptimizerResult('SOBOL', x[nd], f[nd], oracle.evaluations_used)

    # Generic fallback for third-party oracles that do not expose capacity.
    # Arbitrary stopping budgets cannot preserve a complete 2^m net, so we
    # suppress only SciPy's known balance warning and still charge solely the
    # actual objective evaluations.
    xs = []
    fs = []
    idx = 0
    while oracle.can_evaluate():
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message="The balance properties of Sobol.*", category=UserWarning)
            cand = engine.random(batch_size)
        x, f = evaluate_population(oracle, cand, 'SOBOL', idx)
        if len(x) == 0:
            break
        xs.append(x)
        fs.append(f)
        idx += len(x)
    if not xs:
        raise RuntimeError('no budget for Sobol baseline')
    x = np.vstack(xs)
    f = np.vstack(fs)
    nd = nondominated_indices(f)
    return OptimizerResult('SOBOL', x[nd], f[nd], oracle.evaluations_used)
