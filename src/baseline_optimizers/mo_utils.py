from __future__ import annotations

import numpy as np


def dominates(a: np.ndarray, b: np.ndarray, eps: float = 0.0) -> bool:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return bool(np.all(a <= b + eps) and np.any(a < b - eps))


def nondominated_sort(f: np.ndarray) -> list[list[int]]:
    f = np.asarray(f, dtype=float)
    n = len(f)
    dominates_set = [[] for _ in range(n)]
    domination_count = np.zeros(n, dtype=int)
    first: list[int] = []
    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            if dominates(f[p], f[q]):
                dominates_set[p].append(q)
            elif dominates(f[q], f[p]):
                domination_count[p] += 1
        if domination_count[p] == 0:
            first.append(p)
    fronts: list[list[int]] = []
    current = first
    while current:
        fronts.append(current)
        nxt: list[int] = []
        for p in current:
            for q in dominates_set[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    nxt.append(q)
        current = nxt
    return fronts


def crowding_distance(f: np.ndarray, indices: list[int]) -> dict[int, float]:
    if not indices:
        return {}
    if len(indices) <= 2:
        return {i: float('inf') for i in indices}
    sub = np.asarray(f[indices], dtype=float)
    m = sub.shape[1]
    d = np.zeros(len(indices), dtype=float)
    for j in range(m):
        order = np.argsort(sub[:, j], kind='mergesort')
        d[order[0]] = np.inf
        d[order[-1]] = np.inf
        lo = sub[order[0], j]
        hi = sub[order[-1], j]
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            continue
        scale = hi - lo
        for k in range(1, len(order) - 1):
            if np.isinf(d[order[k]]):
                continue
            d[order[k]] += (sub[order[k + 1], j] - sub[order[k - 1], j]) / scale
    return {idx: float(d[pos]) for pos, idx in enumerate(indices)}


def rank_and_crowding(f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    f = np.asarray(f, dtype=float)
    rank = np.full(len(f), np.iinfo(np.int32).max, dtype=int)
    crowd = np.zeros(len(f), dtype=float)
    for r, front in enumerate(nondominated_sort(f)):
        for i in front:
            rank[i] = r
        cd = crowding_distance(f, front)
        for i, v in cd.items():
            crowd[i] = v
    return rank, crowd


def environmental_select(x: np.ndarray, f: np.ndarray, n_keep: int) -> tuple[np.ndarray, np.ndarray]:
    if n_keep <= 0:
        return np.empty((0, x.shape[1])), np.empty((0, f.shape[1]))
    keep: list[int] = []
    for front in nondominated_sort(f):
        if len(keep) + len(front) <= n_keep:
            keep.extend(front)
            continue
        cd = crowding_distance(f, front)
        need = n_keep - len(keep)
        chosen = sorted(front, key=lambda i: (-cd[i], i))[:need]
        keep.extend(chosen)
        break
    return np.asarray(x[keep], dtype=float), np.asarray(f[keep], dtype=float)


def nondominated_indices(f: np.ndarray) -> np.ndarray:
    fronts = nondominated_sort(f)
    return np.asarray(fronts[0] if fronts else [], dtype=int)
