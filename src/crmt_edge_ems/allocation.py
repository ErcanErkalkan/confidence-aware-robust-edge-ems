from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .archive import CandidateRecord
from .dominance import pareto_dominates


@dataclass(frozen=True)
class AllocationScore:
    candidate_id: str
    score: float
    frontier_bonus: float
    uncertainty: float
    n_blocks: int


def _nondominated_ids(records: Mapping[str, CandidateRecord]) -> set[str]:
    ids = list(records)
    front: set[str] = set()
    for cid in ids:
        r = records[cid]
        if not any(
            other != cid and pareto_dominates(records[other].risk_vector, r.risk_vector)
            for other in ids
        ):
            front.add(cid)
    return front


def allocation_scores(records: Mapping[str, CandidateRecord]) -> list[AllocationScore]:
    if not records:
        return []
    front = _nondominated_ids(records)
    out: list[AllocationScore] = []
    for cid, record in records.items():
        x = np.asarray(record.samples, dtype=float)
        n = x.shape[0]
        if n <= 1:
            uncertainty = float("inf")
        else:
            sd = np.std(x, axis=0, ddof=1)
            se = sd / np.sqrt(n)
            scale = np.maximum(np.abs(np.mean(x, axis=0)), 1e-9)
            uncertainty = float(np.sum(np.minimum(se / scale, 10.0)))
        frontier_bonus = 2.0 if cid in front else 0.0
        score = frontier_bonus + uncertainty
        out.append(AllocationScore(cid, score, frontier_bonus, uncertainty, n))
    return sorted(out, key=lambda z: (-z.score, z.n_blocks, z.candidate_id))


def select_for_more_evaluation(records: Mapping[str, CandidateRecord], n_select: int) -> list[str]:
    if n_select <= 0:
        return []
    return [s.candidate_id for s in allocation_scores(records)[:n_select]]
