from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

from jer_microgrid.config import SiteConfig
from jer_microgrid.metrics import compute_metrics
from jer_microgrid.simulation import simulate_controller

from .budget import EvaluationLedger
from .parameter_space import build_tuned_controller
from .risk import RiskConfig, aggregate_objectives


_REQUIRED_PROFILE_COLUMNS = ("timestamp", "base_kw", "peak_flag")


@dataclass(frozen=True)
class ReplayBlock:
    block_id: str
    profile: pd.DataFrame
    source: str = "public_replay"
    split: str = "unspecified"
    site_id: str | int | None = None

    def validated_profile(self) -> pd.DataFrame:
        missing = [c for c in _REQUIRED_PROFILE_COLUMNS if c not in self.profile.columns]
        if missing:
            raise KeyError(f"Replay block {self.block_id!r} missing required columns: {missing}")
        p = self.profile.copy()
        if p.empty:
            raise ValueError(f"Replay block {self.block_id!r} is empty")
        if p["timestamp"].isna().any() or p["base_kw"].isna().any() or p["peak_flag"].isna().any():
            raise ValueError(f"Replay block {self.block_id!r} contains missing required values")
        if p["timestamp"].duplicated().any():
            raise ValueError(f"Replay block {self.block_id!r} has duplicate timestamps")
        if not p["timestamp"].is_monotonic_increasing:
            raise ValueError(f"Replay block {self.block_id!r} timestamps must be sorted")
        vals = set(pd.to_numeric(p["peak_flag"], errors="coerce").dropna().astype(int).unique())
        if not vals.issubset({0, 1}):
            raise ValueError(f"Replay block {self.block_id!r} peak_flag must be binary")
        return p


class ReplayEvaluator:
    """Evaluate tuned edge controllers on frozen real-data replay blocks.

    The evaluator never infers site hardware limits or operating windows from
    the dataset. Those belong to the locked experiment protocol and are passed
    explicitly via SiteConfig and the profile's peak_flag.
    """

    def __init__(self, site: SiteConfig, *, ledger: EvaluationLedger | None = None, method_id: str = "CRMT"):
        self.site = site
        self.ledger = ledger
        self.method_id = str(method_id)

    def evaluate_block(self, params: Mapping[str, float], block: ReplayBlock, *, candidate_id: str) -> dict[str, float | int | str]:
        profile = block.validated_profile()
        if self.ledger is not None:
            self.ledger.reserve(self.method_id, str(candidate_id), [block.block_id])
        controller = build_tuned_controller(self.site, params)
        sim = simulate_controller(profile, controller, self.site)
        metrics = compute_metrics(sim.series, self.site)
        return {
            "block_id": str(block.block_id),
            "source": str(block.source),
            "split": str(block.split),
            "n_ticks": int(len(profile)),
            **metrics,
        }

    def evaluate(self, params: Mapping[str, float], blocks: Iterable[ReplayBlock], *, candidate_id: str) -> pd.DataFrame:
        block_list = list(blocks)
        if self.ledger is not None:
            self.ledger.reserve(self.method_id, str(candidate_id), [b.block_id for b in block_list])
            ledger = self.ledger
            self.ledger = None
            try:
                rows = [self.evaluate_block(params, b, candidate_id=candidate_id) for b in block_list]
            finally:
                self.ledger = ledger
        else:
            rows = [self.evaluate_block(params, b, candidate_id=candidate_id) for b in block_list]
        return pd.DataFrame(rows)

    @staticmethod
    def aggregate(metrics: pd.DataFrame, risk: RiskConfig = RiskConfig()) -> dict[str, float]:
        return aggregate_objectives(metrics, risk)


class MultiSiteReplayEvaluator:
    """Replay evaluator for multiple independent physical/site domains.

    Each ReplayBlock must carry a site_id. The same normalized controller
    parameterization is decoded separately against that site's SiteConfig.
    """

    def __init__(
        self,
        sites: Mapping[str | int, SiteConfig],
        *,
        ledger: EvaluationLedger | None = None,
        method_id: str = "CRMT",
    ):
        if not sites:
            raise ValueError("at least one site is required")
        self.sites = {str(k): v for k, v in sites.items()}
        self.repair_site = next(iter(self.sites.values()))
        self.ledger = ledger
        self.method_id = str(method_id)

    def _site_for(self, block: ReplayBlock) -> SiteConfig:
        if block.site_id is None:
            raise ValueError(f"Replay block {block.block_id!r} is missing site_id")
        key = str(block.site_id)
        if key not in self.sites:
            raise KeyError(f"Unknown site_id {block.site_id!r} for block {block.block_id!r}")
        return self.sites[key]

    def evaluate_block(
        self,
        params: Mapping[str, float],
        block: ReplayBlock,
        *,
        candidate_id: str,
    ) -> dict[str, float | int | str]:
        profile = block.validated_profile()
        site = self._site_for(block)
        if self.ledger is not None:
            self.ledger.reserve(self.method_id, str(candidate_id), [block.block_id])
        controller = build_tuned_controller(site, params)
        sim = simulate_controller(profile, controller, site)
        metrics = compute_metrics(sim.series, site)
        return {
            "block_id": str(block.block_id),
            "site_id": str(block.site_id),
            "source": str(block.source),
            "split": str(block.split),
            "n_ticks": int(len(profile)),
            **metrics,
        }

    def evaluate(
        self,
        params: Mapping[str, float],
        blocks: Iterable[ReplayBlock],
        *,
        candidate_id: str,
    ) -> pd.DataFrame:
        block_list = list(blocks)
        if not block_list:
            return pd.DataFrame()
        # Structural/site routing errors are preflight failures and must be
        # detected before any expensive-evaluation budget is reserved.
        for block in block_list:
            self._site_for(block)
        if self.ledger is not None:
            self.ledger.reserve(
                self.method_id,
                str(candidate_id),
                [b.block_id for b in block_list],
            )
            ledger = self.ledger
            self.ledger = None
            try:
                rows = [
                    self.evaluate_block(params, b, candidate_id=candidate_id)
                    for b in block_list
                ]
            finally:
                self.ledger = ledger
        else:
            rows = [
                self.evaluate_block(params, b, candidate_id=candidate_id)
                for b in block_list
            ]
        return pd.DataFrame(rows)

    @staticmethod
    def aggregate(metrics: pd.DataFrame, risk: RiskConfig = RiskConfig()) -> dict[str, float]:
        return aggregate_objectives(metrics, risk)
