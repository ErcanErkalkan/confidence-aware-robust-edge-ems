import numpy as np

from baseline_optimizers import BlockRiskOracle, run_mode, run_mopso, run_nsga2, run_sobol
from crmt_edge_ems.budget import EvaluationLedger
from crmt_edge_ems.evaluator import LedgeredSyntheticEvaluator, ScenarioBlock
from jer_microgrid.config import SyntheticConfig


BLOCKS = (
    ScenarioBlock('mixed', 101),
    ScenarioBlock('cloud_edge', 102),
)
BLOCK_BUDGET = 12  # 6 complete candidates x 2 declared blocks


def _run_microgrid(method: str, seed: int = 17):
    ledger = EvaluationLedger(BLOCK_BUDGET)
    evaluator = LedgeredSyntheticEvaluator(
        synth=SyntheticConfig(hours=2),
        ledger=ledger,
        method_id=method.upper(),
    )
    oracle = BlockRiskOracle(evaluator, BLOCKS)
    if method == 'sobol':
        result = run_sobol(oracle, seed=seed, batch_size=4)
    elif method == 'nsga2':
        result = run_nsga2(oracle, seed=seed, pop_size=4)
    elif method == 'mopso':
        result = run_mopso(oracle, seed=seed, swarm_size=4, archive_size=8)
    elif method == 'mode':
        result = run_mode(oracle, seed=seed, pop_size=4)
    else:
        raise ValueError(method)
    return result, ledger


def test_all_baselines_share_exact_controller_block_budget_on_microgrid():
    for method in ['sobol', 'nsga2', 'mopso', 'mode']:
        result, ledger = _run_microgrid(method)
        ledger.assert_exact()
        assert result.evaluations_used == BLOCK_BUDGET
        assert len(result.objectives) > 0
        assert result.objectives.shape[1] == 4
        assert np.isfinite(result.objectives).all()
        assert np.all((result.positions >= 0.0) & (result.positions <= 1.0))
        events = ledger.to_frame()
        assert len(events) == BLOCK_BUDGET
        assert events['method_id'].nunique() == 1
        assert events['method_id'].iloc[0] == method.upper()
        # Every accepted candidate must have a complete, identical block set.
        per_candidate = events.groupby('candidate_id')['block_id'].agg(tuple)
        assert len(per_candidate) == BLOCK_BUDGET // len(BLOCKS)
        assert all(set(v) == {b.block_id for b in BLOCKS} for v in per_candidate)


def test_microgrid_baseline_reproducibility_under_same_seed():
    for method in ['sobol', 'nsga2', 'mopso', 'mode']:
        a, la = _run_microgrid(method, seed=29)
        b, lb = _run_microgrid(method, seed=29)
        assert np.allclose(a.positions, b.positions)
        assert np.allclose(a.objectives, b.objectives)
        assert la.to_frame().equals(lb.to_frame())
