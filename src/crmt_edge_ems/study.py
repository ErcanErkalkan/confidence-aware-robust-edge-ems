from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from .allocation import select_for_more_evaluation
from .archive import CandidateRecord, ConfidenceArchive
from .evaluator import ScenarioBlock, SyntheticEvaluator
from .risk import RiskConfig, objective_matrix

@dataclass
class StudyResult:
    candidate_metrics: dict[str, pd.DataFrame]
    archive_ids: list[str]
    budget_used: int

class CRMTStudy:
    def __init__(self,evaluator:SyntheticEvaluator,*,risk:RiskConfig=RiskConfig(),initial_blocks:int=4,allocation_batch:int=2,alpha:float=0.05,n_boot:int=1000):
        self.evaluator=evaluator; self.risk=risk; self.initial_blocks=max(2,int(initial_blocks)); self.allocation_batch=max(1,int(allocation_batch)); self.alpha=alpha; self.n_boot=n_boot
    def run(self,candidates:Mapping[str,Mapping[str,float]],blocks:Iterable[ScenarioBlock],*,max_evaluations:int)->StudyResult:
        block_list=list(blocks)
        if len(block_list)<self.initial_blocks: raise ValueError("Not enough blocks for initial evaluation")
        if max_evaluations<len(candidates)*self.initial_blocks: raise ValueError("Budget is smaller than the required initial paired design")
        metrics={}; used_blocks={}; budget=0; initial=block_list[:self.initial_blocks]
        for cid,params in candidates.items():
            df=self.evaluator.evaluate(params,initial,candidate_id=cid); metrics[cid]=df; used_blocks[cid]=list(initial); budget+=len(initial)
        while budget < max_evaluations:
            records = self._records(candidates, metrics)
            available = {
                cid: record
                for cid, record in records.items()
                if len(set(metrics[cid]["block_id"].astype(str))) < len(block_list)
            }
            if not available:
                break
            selected = select_for_more_evaluation(
                available, min(self.allocation_batch, len(available))
            )
            progressed = False
            for cid in selected:
                if budget >= max_evaluations:
                    break
                evaluated_ids = set(metrics[cid]["block_id"].astype(str))
                next_block = next(
                    (b for b in block_list if b.block_id not in evaluated_ids),
                    None,
                )
                if next_block is None:
                    continue
                new = self.evaluator.evaluate(
                    candidates[cid], [next_block], candidate_id=cid
                )
                metrics[cid] = pd.concat([metrics[cid], new], ignore_index=True)
                used_blocks[cid].append(next_block)
                budget += 1
                progressed = True
            if not progressed:
                break
        records=self._records(candidates,metrics); archive=ConfidenceArchive(risk=self.risk,alpha=self.alpha,n_boot=self.n_boot)
        for record in records.values(): archive.add(record)
        return StudyResult(metrics,archive.confidently_nondominated_ids(),budget)
    def _records(self,candidates,metrics):
        out={}
        for cid,df in metrics.items():
            risk_dict=self.evaluator.aggregate(df,self.risk); samples=objective_matrix(df,self.risk.objectives); out[cid]=CandidateRecord(cid,dict(candidates[cid]),samples,np.asarray([risk_dict[k] for k in self.risk.objectives],dtype=float),tuple(df["block_id"].astype(str)))
        return out
