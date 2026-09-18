from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from .allocation import select_for_more_evaluation
from .archive import CandidateRecord, ConfidenceArchive
from .dominance import pareto_dominates
from .risk import RiskConfig, objective_matrix


@dataclass
class StudyResult:
    candidate_metrics: dict[str, pd.DataFrame]
    archive_ids: list[str]
    budget_used: int


def _risk_pareto_archive_ids(
    records: Mapping[str, CandidateRecord],
) -> list[str]:
    """Return ordinary nondominated IDs using aggregated risk vectors only."""
    ids = list(records)
    keep: list[str] = []
    for cid in ids:
        if not any(
            other != cid
            and pareto_dominates(
                records[other].risk_vector,
                records[cid].risk_vector,
            )
            for other in ids
        ):
            keep.append(cid)
    return keep


class CRMTStudy:
    def __init__(
        self,
        evaluator,
        *,
        risk: RiskConfig = RiskConfig(),
        initial_blocks: int = 4,
        allocation_batch: int = 2,
        alpha: float = 0.05,
        n_boot: int = 1000,
        allocation_mode: str = "adaptive",
        archive_mode: str = "confidence",
    ):
        self.evaluator = evaluator
        self.risk = risk
        self.initial_blocks = max(2, int(initial_blocks))
        self.allocation_batch = max(1, int(allocation_batch))
        self.alpha = float(alpha)
        self.n_boot = int(n_boot)
        if allocation_mode not in {"adaptive", "round_robin"}:
            raise ValueError("allocation_mode must be 'adaptive' or 'round_robin'")
        if archive_mode not in {"confidence", "risk_pareto"}:
            raise ValueError("archive_mode must be 'confidence' or 'risk_pareto'")
        self.allocation_mode = allocation_mode
        self.archive_mode = archive_mode

    def run(
        self,
        candidates: Mapping[str, Mapping[str, float]],
        blocks: Iterable,
        *,
        max_evaluations: int,
    ) -> StudyResult:
        block_list = list(blocks)
        if len(block_list) < self.initial_blocks:
            raise ValueError("Not enough blocks for initial evaluation")
        if max_evaluations < len(candidates) * self.initial_blocks:
            raise ValueError(
                "Budget is smaller than the required initial paired design"
            )

        metrics: dict[str, pd.DataFrame] = {}
        budget = 0
        initial = block_list[: self.initial_blocks]
        for cid, params in candidates.items():
            df = self.evaluator.evaluate(
                params, initial, candidate_id=cid
            )
            metrics[cid] = df
            budget += len(initial)

        if self.allocation_mode == "adaptive":
            budget = self._run_adaptive(
                candidates, block_list, metrics, budget, max_evaluations
            )
        else:
            budget = self._run_round_robin(
                candidates, block_list, metrics, budget, max_evaluations
            )

        records = self._records(candidates, metrics)
        if self.archive_mode == "confidence":
            archive = ConfidenceArchive(
                risk=self.risk,
                alpha=self.alpha,
                n_boot=self.n_boot,
            )
            for record in records.values():
                archive.add(record)
            archive_ids = archive.confidently_nondominated_ids()
        else:
            archive_ids = _risk_pareto_archive_ids(records)

        return StudyResult(metrics, archive_ids, budget)

    def _run_adaptive(
        self,
        candidates,
        block_list,
        metrics,
        budget: int,
        max_evaluations: int,
    ) -> int:
        while budget < max_evaluations:
            records = self._records(candidates, metrics)
            available = {
                cid: record
                for cid, record in records.items()
                if len(set(metrics[cid]["block_id"].astype(str)))
                < len(block_list)
            }
            if not available:
                break
            selected = select_for_more_evaluation(
                available,
                min(self.allocation_batch, len(available)),
            )
            progressed = False
            for cid in selected:
                if budget >= max_evaluations:
                    break
                next_block = self._next_block(metrics[cid], block_list)
                if next_block is None:
                    continue
                new = self.evaluator.evaluate(
                    candidates[cid],
                    [next_block],
                    candidate_id=cid,
                )
                metrics[cid] = pd.concat(
                    [metrics[cid], new],
                    ignore_index=True,
                )
                budget += 1
                progressed = True
            if not progressed:
                break
        return budget

    def _run_round_robin(
        self,
        candidates,
        block_list,
        metrics,
        budget: int,
        max_evaluations: int,
    ) -> int:
        ids = list(candidates)
        while budget < max_evaluations:
            progressed = False
            for cid in ids:
                if budget >= max_evaluations:
                    break
                next_block = self._next_block(metrics[cid], block_list)
                if next_block is None:
                    continue
                new = self.evaluator.evaluate(
                    candidates[cid],
                    [next_block],
                    candidate_id=cid,
                )
                metrics[cid] = pd.concat(
                    [metrics[cid], new],
                    ignore_index=True,
                )
                budget += 1
                progressed = True
            if not progressed:
                break
        return budget

    @staticmethod
    def _next_block(metrics: pd.DataFrame, block_list):
        evaluated_ids = set(metrics["block_id"].astype(str))
        return next(
            (b for b in block_list if b.block_id not in evaluated_ids),
            None,
        )

    def _records(self, candidates, metrics):
        out = {}
        for cid, df in metrics.items():
            risk_dict = self.evaluator.aggregate(df, self.risk)
            samples = objective_matrix(df, self.risk.objectives)
            out[cid] = CandidateRecord(
                cid,
                dict(candidates[cid]),
                samples,
                np.asarray(
                    [risk_dict[k] for k in self.risk.objectives],
                    dtype=float,
                ),
                tuple(df["block_id"].astype(str)),
            )
        return out
