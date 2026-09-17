from __future__ import annotations

import numpy as np

from .common import OptimizerResult, evaluate_population
from .mo_utils import environmental_select, rank_and_crowding


def _tournament(rng, rank, crowd) -> int:
    a, b = rng.integers(0, len(rank), size=2)
    if rank[a] < rank[b]: return int(a)
    if rank[b] < rank[a]: return int(b)
    if crowd[a] > crowd[b]: return int(a)
    if crowd[b] > crowd[a]: return int(b)
    return int(a if rng.random() < 0.5 else b)


def _sbx(rng, p1, p2, eta=15.0, prob=0.9):
    if rng.random() > prob:
        return p1.copy(), p2.copy()
    c1, c2 = p1.copy(), p2.copy()
    for j in range(len(p1)):
        if rng.random() > 0.5 or abs(p1[j] - p2[j]) < 1e-14:
            continue
        x1, x2 = sorted((p1[j], p2[j]))
        u = rng.random()
        beta = 1.0 + (2.0 * (x1 - 0.0) / (x2 - x1))
        alpha = 2.0 - beta ** (-(eta + 1.0))
        if u <= 1.0 / alpha:
            betaq = (u * alpha) ** (1.0 / (eta + 1.0))
        else:
            betaq = (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
        child1 = 0.5 * ((x1 + x2) - betaq * (x2 - x1))
        beta = 1.0 + (2.0 * (1.0 - x2) / (x2 - x1))
        alpha = 2.0 - beta ** (-(eta + 1.0))
        if u <= 1.0 / alpha:
            betaq = (u * alpha) ** (1.0 / (eta + 1.0))
        else:
            betaq = (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
        child2 = 0.5 * ((x1 + x2) + betaq * (x2 - x1))
        child1, child2 = np.clip([child1, child2], 0.0, 1.0)
        if rng.random() <= 0.5:
            c1[j], c2[j] = child2, child1
        else:
            c1[j], c2[j] = child1, child2
    return c1, c2


def _poly_mut(rng, x, eta=20.0, prob=None):
    y = x.copy()
    p = 1.0 / len(y) if prob is None else prob
    for j in range(len(y)):
        if rng.random() > p:
            continue
        u = rng.random()
        if u < 0.5:
            delta = (2*u + (1-2*u) * (1-y[j]) ** (eta+1)) ** (1/(eta+1)) - 1
        else:
            delta = 1 - (2*(1-u) + 2*(u-0.5) * y[j] ** (eta+1)) ** (1/(eta+1))
        y[j] = np.clip(y[j] + delta, 0.0, 1.0)
    return y


def run_nsga2(oracle, *, seed: int, pop_size: int = 40, crossover_prob: float = 0.9, eta_c: float = 15.0, eta_m: float = 20.0) -> OptimizerResult:
    if pop_size < 4:
        raise ValueError('pop_size must be >= 4')
    rng = np.random.default_rng(seed)
    x0 = rng.random((pop_size, oracle.dim))
    x, f = evaluate_population(oracle, x0, 'NSGAII')
    if len(x) == 0:
        raise RuntimeError('no budget for initial NSGA-II population')
    eval_index = len(x)
    while oracle.can_evaluate() and len(x) >= 2:
        rank, crowd = rank_and_crowding(f)
        children = []
        while len(children) < pop_size:
            p1 = x[_tournament(rng, rank, crowd)]
            p2 = x[_tournament(rng, rank, crowd)]
            c1, c2 = _sbx(rng, p1, p2, eta=eta_c, prob=crossover_prob)
            children.extend([_poly_mut(rng, c1, eta=eta_m), _poly_mut(rng, c2, eta=eta_m)])
        cx, cf = evaluate_population(oracle, np.asarray(children[:pop_size]), 'NSGAII', eval_index)
        if len(cx) == 0:
            break
        eval_index += len(cx)
        x, f = environmental_select(np.vstack([x, cx]), np.vstack([f, cf]), min(pop_size, len(x) + len(cx)))
    return OptimizerResult('NSGAII', x, f, oracle.evaluations_used)
