from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

from jer_microgrid.config import SiteConfig, SyntheticConfig
from jer_microgrid.metrics import compute_metrics
from jer_microgrid.simulation import simulate_controller
from jer_microgrid.synth import generate_profile

from .budget import EvaluationLedger
from .parameter_space import build_tuned_controller
from .risk import RiskConfig, aggregate_objectives


@dataclass(frozen=True, order=True)
class ScenarioBlock:
    scenario: str
    seed: int

    @property
    def block_id(self) -> str:
        return f"{self.scenario}:seed{self.seed}"


class SyntheticEvaluator:
    """Deterministic block evaluator used for method development and stress tests.

    Public-data replay is intentionally a separate provider so synthetic and
    external-data evidence cannot be silently mixed.
    """

    def __init__(self, site: SiteConfig | None = None, synth: SyntheticConfig | None = None):
        self.site = site or SiteConfig()
        self.synth = synth or SyntheticConfig()

    def evaluate_block(self, params: Mapping[str, float], block: ScenarioBlock) -> dict[str, float | int | str]:
        profile = generate_profile(block.seed, block.scenario, self.site, self.synth)
        controller = build_tuned_controller(self.site, params)
        sim = simulate_controller(profile, controller, self.site)
        metrics = compute_metrics(sim.series, self.site)
        return {
            "block_id": block.block_id,
            "scenario": block.scenario,
            "seed": int(block.seed),
            **metrics,
        }

    def evaluate(
        self,
        params: Mapping[str, float],
        blocks: Iterable[ScenarioBlock],
        *,
        candidate_id: str | None = None,
    ) -> pd.DataFrame:
        rows = [self.evaluate_block(params, block) for block in blocks]
        return pd.DataFrame(rows)

    def aggregate(self, metrics: pd.DataFrame, risk: RiskConfig = RiskConfig()) -> dict[str, float]:
        return aggregate_objectives(metrics, risk)


class LedgeredSyntheticEvaluator(SyntheticEvaluator):
    """Synthetic evaluator with atomic controller-block budget accounting."""

    def __init__(
        self,
        site: SiteConfig | None = None,
        synth: SyntheticConfig | None = None,
        *,
        ledger: EvaluationLedger,
        method_id: str = "CRMT",
    ):
        super().__init__(site=site, synth=synth)
        self.ledger = ledger
        self.method_id = str(method_id)

    def evaluate(
        self,
        params: Mapping[str, float],
        blocks: Iterable[ScenarioBlock],
        *,
        candidate_id: str | None = None,
    ) -> pd.DataFrame:
        block_list = list(blocks)
        if not block_list:
            return pd.DataFrame()
        if candidate_id is None:
            raise ValueError("candidate_id is required for ledgered evaluation")
        self.ledger.reserve(self.method_id, str(candidate_id), [block.block_id for block in block_list])
        rows = [self.evaluate_block(params, block) for block in block_list]
        return pd.DataFrame(rows)
