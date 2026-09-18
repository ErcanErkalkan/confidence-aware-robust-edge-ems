from __future__ import annotations

from crmt_edge_ems import CRMTStudy, RiskConfig, ScenarioBlock, SyntheticEvaluator, sobol_candidates
from jer_microgrid.config import SyntheticConfig


def test_budgeted_study_smoke():
    evaluator = SyntheticEvaluator(synth=SyntheticConfig(hours=0.5, scenario_names=["mixed", "load_step"]))
    candidates = {f"c{i}": p for i, p in enumerate(sobol_candidates(3, seed=21))}
    blocks = [
        ScenarioBlock("mixed", 0),
        ScenarioBlock("load_step", 0),
        ScenarioBlock("mixed", 1),
        ScenarioBlock("load_step", 1),
        ScenarioBlock("mixed", 2),
        ScenarioBlock("load_step", 2),
    ]
    study = CRMTStudy(evaluator, risk=RiskConfig(q=0.8, tail_weight=0.5), initial_blocks=2, allocation_batch=2, n_boot=300)
    result = study.run(candidates, blocks, max_evaluations=10)
    assert result.budget_used == 10
    assert result.archive_ids
    assert set(result.candidate_metrics) == set(candidates)
