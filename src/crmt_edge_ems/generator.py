from __future__ import annotations

import numpy as np
from scipy.stats import qmc

from .parameter_space import decode_unit_vector, validate_physical


def sobol_candidates(n: int, *, seed: int = 0, max_draw_multiplier: int = 16) -> list[dict[str, float]]:
    """Generate deterministic feasible candidate configurations.

    This is a search baseline / initialization mechanism, not the proposed
    optimization novelty.
    """
    if n <= 0:
        return []
    d = 9
    engine = qmc.Sobol(d=d, scramble=True, seed=seed)
    accepted: list[dict[str, float]] = []
    draws = 0
    max_draws = max(n * max_draw_multiplier, n)
    while len(accepted) < n and draws < max_draws:
        u = engine.random(1)[0]
        draws += 1
        p = decode_unit_vector(u)
        ok, _ = validate_physical(p)
        if ok:
            accepted.append(p)
    if len(accepted) < n:
        raise RuntimeError(f"Could only generate {len(accepted)} feasible candidates out of requested {n}")
    return accepted
