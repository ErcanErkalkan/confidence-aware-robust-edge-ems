from __future__ import annotations

import numpy as np

from .common import OptimizerResult, evaluate_population
from .mo_utils import crowding_distance, dominates, environmental_select, nondominated_indices


def _archive(x, f, max_size):
    idx = nondominated_indices(f)
    ax, af = x[idx], f[idx]
    if len(ax) <= max_size:
        return ax, af
    local = list(range(len(ax)))
    cd = crowding_distance(af, local)
    keep = sorted(local, key=lambda i: (-cd[i], i))[:max_size]
    return ax[keep], af[keep]


def _leader_index(rng, af):
    if len(af) == 1:
        return 0
    cd = crowding_distance(af, list(range(len(af))))
    vals = np.asarray([cd[i] for i in range(len(af))], dtype=float)
    finite = np.isfinite(vals)
    if np.any(~finite):
        vals[~finite] = (np.max(vals[finite]) if np.any(finite) else 1.0) + 1.0
    vals = np.maximum(vals, 1e-12)
    probs = vals / vals.sum()
    return int(rng.choice(len(af), p=probs))


def run_mopso(oracle, *, seed: int, swarm_size: int = 40, archive_size: int = 100, inertia: float = 0.5, c1: float = 1.5, c2: float = 1.5, velocity_clip: float = 0.2) -> OptimizerResult:
    if swarm_size < 2 or archive_size < 2:
        raise ValueError('swarm_size and archive_size must be >= 2')
    rng = np.random.default_rng(seed)
    x0 = rng.random((swarm_size, oracle.dim))
    x, f = evaluate_population(oracle, x0, 'MOPSO')
    if len(x) == 0:
        raise RuntimeError('no budget for initial MOPSO swarm')
    v = rng.uniform(-0.05, 0.05, size=x.shape)
    pbest_x = x.copy(); pbest_f = f.copy()
    ax, af = _archive(x.copy(), f.copy(), archive_size)
    eval_index = len(x)
    while oracle.can_evaluate() and len(x) > 0:
        proposals = []
        for i in range(len(x)):
            leader = ax[_leader_index(rng, af)]
            r1 = rng.random(oracle.dim); r2 = rng.random(oracle.dim)
            v[i] = inertia*v[i] + c1*r1*(pbest_x[i]-x[i]) + c2*r2*(leader-x[i])
            v[i] = np.clip(v[i], -velocity_clip, velocity_clip)
            proposals.append(np.clip(x[i] + v[i], 0.0, 1.0))
        nx, nf = evaluate_population(oracle, np.asarray(proposals), 'MOPSO', eval_index)
        if len(nx) == 0:
            break
        k = len(nx); eval_index += k
        for i in range(k):
            if dominates(nf[i], pbest_f[i]):
                pbest_x[i], pbest_f[i] = nx[i].copy(), nf[i].copy()
            elif not dominates(pbest_f[i], nf[i]) and rng.random() < 0.5:
                pbest_x[i], pbest_f[i] = nx[i].copy(), nf[i].copy()
        x[:k], f[:k] = nx, nf
        ax, af = _archive(np.vstack([ax, nx]), np.vstack([af, nf]), archive_size)
    return OptimizerResult('MOPSO', ax, af, oracle.evaluations_used)
