from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

from .dominance import confidence_risk_dominance
from .risk import RiskConfig


@dataclass
class CandidateRecord:
    candidate_id: str
    params: Mapping[str, float]
    samples: np.ndarray  # [blocks, objectives], aligned by block_ids for pairwise comparison
    risk_vector: np.ndarray
    block_ids: tuple[str, ...]


@dataclass
class ConfidenceArchive:
    risk: RiskConfig = field(default_factory=RiskConfig)
    alpha: float = 0.05
    n_boot: int = 2000
    epsilon: float = 0.0
    records: dict[str, CandidateRecord] = field(default_factory=dict)

    def add(self, record: CandidateRecord) -> None:
        if record.samples.ndim != 2 or record.samples.shape[1] != len(self.risk.objectives):
            raise ValueError("Candidate sample width must match archive RiskConfig objectives")
        self.records[record.candidate_id] = record

    def confidently_nondominated_ids(self) -> list[str]:
        ids = list(self.records)
        keep: list[str] = []
        for cid in ids:
            dominated = False
            for other_id in ids:
                if cid == other_id:
                    continue
                a, b = self._align(self.records[other_id], self.records[cid])
                if a.shape[0] < 2:
                    continue
                decision = confidence_risk_dominance(
                    a,
                    b,
                    risk=self.risk,
                    alpha=self.alpha,
                    n_boot=self.n_boot,
                    epsilon=self.epsilon,
                    seed=self._pair_seed(other_id, cid),
                )
                if decision.relation == -1:
                    dominated = True
                    break
            if not dominated:
                keep.append(cid)
        return keep

    @staticmethod
    def _pair_seed(a: str, b: str) -> int:
        text = f"{a}|{b}".encode("utf-8")
        x = 2166136261
        for byte in text:
            x ^= byte
            x = (x * 16777619) & 0xFFFFFFFF
        return int(x)

    @staticmethod
    def _align(a: CandidateRecord, b: CandidateRecord) -> tuple[np.ndarray, np.ndarray]:
        apos = {bid: i for i, bid in enumerate(a.block_ids)}
        bpos = {bid: i for i, bid in enumerate(b.block_ids)}
        common = [bid for bid in a.block_ids if bid in bpos]
        if not common:
            m = a.samples.shape[1]
            return np.empty((0, m)), np.empty((0, m))
        return (
            np.asarray([a.samples[apos[bid]] for bid in common], dtype=float),
            np.asarray([b.samples[bpos[bid]] for bid in common], dtype=float),
        )
