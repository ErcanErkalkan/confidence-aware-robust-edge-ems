"""Future-only strict replay with checked EMS simulation and versioned metrics.

Legacy ReplayBlock/ReplayEvaluator/RiskConfig and historical results are intact.
Metadata validation is an input contract, never independent experiment approval.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import math

import numpy as np
import pandas as pd

from .contracts import (ContractError, OBJECTIVES, canonical, digest, finite_array,
                        identifiers, integer, strict_risk)
from .metrics_v2 import METRICS_VERSION, compute_metrics_v2
from .parameter_space import build_tuned_controller
from .replay import ReplayBlock, ReplayEvaluator
from .risk import RiskConfig
from .safety import (SafetyLimits, simulate_checked, validate_simulation_inputs,
                     validate_site)
from .safety.process_supervisor import ProcessSupervisorConfig

_SPLITS = {"TRAIN", "DISCOVERY", "AUDIT", "VALIDATION", "INTERNAL_TEST", "EXTERNAL_TEST"}
_DEFAULT_SUPERVISOR = ProcessSupervisorConfig()


@dataclass(frozen=True)
class StrictReplayBlock(ReplayBlock):
    cadence_minutes: int = 2
    expected_ticks: int | None = None
    source_sha256: str | None = None
    transformation_parameters: dict | None = None
    physical_unit_id: str | None = None
    data_version: str | None = None
    exposure_record_id: str | None = None
    historical_exposure: str | None = None

    def validated_profile(self) -> pd.DataFrame:
        if not isinstance(self.block_id, str) or not self.block_id.strip():
            raise ContractError("strict replay requires a nonempty block ID")
        integer(self.cadence_minutes, "cadence_minutes", 1)
        if self.expected_ticks is not None:
            integer(self.expected_ticks, "expected_ticks", 2)
        if not isinstance(self.profile, pd.DataFrame):
            raise ContractError("profile must be a pandas DataFrame")
        required = {"timestamp", "base_kw", "peak_flag"}
        if not required.issubset(self.profile.columns):
            raise ContractError("profile missing required columns")
        p = self.profile.copy()
        if len(p) < 2 or (self.expected_ticks is not None and len(p) != self.expected_ticks):
            raise ContractError("replay block length/declared support mismatch")
        if any(not pd.api.types.is_numeric_dtype(p[c]) for c in ("base_kw", "peak_flag")):
            raise ContractError("base_kw/peak_flag must have numeric dtype, not strings")
        if pd.api.types.is_bool_dtype(p["peak_flag"]):
            raise ContractError("peak_flag must be explicit 0/1 numbers")
        base = finite_array(p["base_kw"].to_numpy(), "base_kw", ndim=1)
        peak = finite_array(p["peak_flag"].to_numpy(), "peak_flag", ndim=1)
        if not np.isin(peak, [0, 1]).all():
            raise ContractError("peak_flag must contain exact 0 or 1, without coercion")
        try:
            timestamps = pd.DatetimeIndex(pd.to_datetime(p["timestamp"], errors="raise"))
        except (ValueError, TypeError, OverflowError) as exc:
            raise ContractError("invalid replay timestamps") from exc
        if (timestamps.tz is None or timestamps.hasnans or timestamps.has_duplicates
                or not timestamps.is_monotonic_increasing):
            raise ContractError("timestamps must be timezone-aware, complete, unique and ordered")
        expected_step_ns = self.cadence_minutes * 60 * 1_000_000_000
        if not np.all(np.diff(timestamps.as_unit("ns").asi8) == expected_step_ns):
            raise ContractError("replay cadence mismatch or missing time window")
        p["timestamp"] = timestamps
        p["base_kw"] = base
        p["peak_flag"] = peak.astype(np.int64)
        return p

    def validate_metadata(self):
        identifiers([self.source], "source")
        if self.source == "public_replay":
            raise ContractError("strict scientific metadata requires an identified source")
        if self.split not in _SPLITS:
            raise ContractError("strict scientific metadata requires an explicit split")
        if (isinstance(self.site_id, (bool, np.bool_))
                or not isinstance(self.site_id, (str, int, np.integer))
                or not str(self.site_id).strip()):
            raise ContractError("strict scientific metadata requires site_id")
        identifiers([str(self.site_id)], "site_id")
        for name in ("physical_unit_id", "data_version", "exposure_record_id"):
            identifiers([getattr(self, name)], name)
        h = self.source_sha256
        if (not isinstance(h, str) or len(h) != 64
                or any(c not in "0123456789abcdef" for c in h)):
            raise ContractError("strict scientific metadata requires raw source SHA-256")
        if not isinstance(self.transformation_parameters, dict):
            raise ContractError("strict scientific metadata requires transformation parameters")
        try:
            canonical(self.transformation_parameters)
        except (ValueError, TypeError) as exc:
            raise ContractError("transformation parameters must be finite JSON") from exc
        if self.historical_exposure not in {"UNEXPOSED", "EXPOSED"}:
            raise ContractError("strict scientific metadata requires explicit exposure history")
        if self.split == "EXTERNAL_TEST" and self.historical_exposure != "UNEXPOSED":
            raise ContractError("exposed data cannot be independent TEST")
        if self.expected_ticks is None:
            raise ContractError("strict scientific metadata requires declared expected_ticks")
        full_day = self.transformation_parameters.get("full_day", False)
        if not isinstance(full_day, bool):
            raise ContractError("full_day declaration must be boolean")
        if full_day:
            zone = self.transformation_parameters.get("timezone")
            if not isinstance(zone, str) or not zone.strip():
                raise ContractError("full-day support requires declared local timezone")
            try:
                actual = pd.DatetimeIndex(self.validated_profile()["timestamp"])
                local = actual.tz_convert(zone)
                start = local[0].normalize()
                expected = pd.date_range(
                    start, start + pd.DateOffset(days=1),
                    freq=f"{self.cadence_minutes}min", inclusive="left").tz_convert(actual.tz)
            except (ValueError, TypeError, KeyError) as exc:
                raise ContractError("invalid full-day timezone declaration") from exc
            if (len(actual) != len(expected) or not np.array_equal(
                    actual.as_unit("ns").asi8, expected.as_unit("ns").asi8)):
                raise ContractError("full-day declaration requires exact local-day support")


class StrictReplayEvaluator(ReplayEvaluator):
    """Real EMS simulator path; gate authorization remains the caller's duty.

    strict_metadata=False is engineering-only compatibility. Enabling strict
    metadata checks provenance declarations but does not attest their truth.
    Prospective orchestration must independently enforce G0--G4.
    """

    def __init__(self, site, *, ledger=None, method_id="CRMT", limits=None,
                 strict_metadata=False, supervisor=_DEFAULT_SUPERVISOR, seed=0,
                 execution_binding=None):
        super().__init__(site, ledger=ledger, method_id=method_id)
        validate_site(site)
        integer(seed, "seed")
        identifiers([method_id], "method_id")
        if not isinstance(strict_metadata, bool):
            raise ContractError("strict_metadata must be boolean")
        if supervisor is not None and not isinstance(supervisor, ProcessSupervisorConfig):
            raise ContractError("supervisor must be ProcessSupervisorConfig or None")
        if strict_metadata and supervisor is None:
            raise ContractError("strict scientific replay requires process containment")
        self.limits = SafetyLimits.from_site(site) if limits is None else limits
        self.strict_metadata = strict_metadata
        self.supervisor = supervisor
        self.seed = int(seed)
        self.execution_binding = dict(execution_binding or {})
        try:
            canonical(self.execution_binding)
        except (TypeError, ValueError) as exc:
            raise ContractError("execution_binding must be finite JSON") from exc
        self.receipts = []

    def validate_blocks(self, blocks):
        """Pure whole-batch preflight before generation, budget reservation or EMS calls."""
        blocks = list(blocks)
        if not blocks or any(not isinstance(b, StrictReplayBlock) for b in blocks):
            raise ContractError("nonempty sequence of StrictReplayBlock required")
        identifiers([b.block_id for b in blocks], "replay block IDs")
        validated = []
        support = {}
        for block in blocks:
            profile = block.validated_profile()
            if not math.isclose(
                    block.cadence_minutes / 60, self.site.ts_hours,
                    abs_tol=1e-12, rel_tol=0):
                raise ContractError("block cadence differs from SiteConfig sampling interval")
            snapshot = replace(block, profile=profile)
            if self.strict_metadata:
                snapshot.validate_metadata()
            validate_simulation_inputs(profile, self.site, self.limits)
            # The evaluator has one configured site. Unspecified engineering
            # blocks consequently belong to that same site, not independent domains.
            physical = (block.physical_unit_id if block.physical_unit_id is not None
                        else str(block.site_id) if block.site_id is not None
                        else "__ENGINEERING_SINGLE_SITE__")
            times = pd.DatetimeIndex(profile["timestamp"]).as_unit("ns").asi8
            interval = (int(times[0]), int(times[-1]) + block.cadence_minutes * 60 * 1_000_000_000)
            for start, stop in support.setdefault(physical, []):
                if interval[0] < stop and start < interval[1]:
                    raise ContractError("overlapping replay support for the same physical unit")
            support[physical].append(interval)
            validated.append(snapshot)
        return validated

    def _evaluate_batch(self, params, blocks, *, candidate_id):
        identifiers([candidate_id], "candidate_id")
        blocks = self.validate_blocks(blocks)
        # Parameter feasibility is a preflight failure and cannot consume budget.
        controller = build_tuned_controller(self.site, params)
        reservations = (self.ledger.reserve(
            self.method_id, candidate_id, [b.block_id for b in blocks])
            if self.ledger is not None else [None] * len(blocks))
        batch = []
        for block, reservation in zip(blocks, reservations, strict=True):
            receipt = {
                "method_id": self.method_id, "candidate_id": candidate_id,
                "block_id": block.block_id, "status": "RESERVED",
                "budget_charged": self.ledger is not None,
                "reservation_ordinal": None if reservation is None else reservation.ordinal,
                "source_sha256": block.source_sha256, "data_version": block.data_version,
                "metrics_version": METRICS_VERSION,
                "scientific_scope": ("INPUT_CONTRACT_VERIFIED_NOT_AUTHORIZATION"
                                     if self.strict_metadata else "ENGINEERING_ONLY"),
                "execution_binding": self.execution_binding,
                "simulator_started": False, "failure": None}
            self.receipts.append(receipt)
            batch.append(receipt)
        rows = []
        for i, (block, receipt) in enumerate(zip(blocks, batch, strict=True)):
            receipt["status"] = "STARTED"
            receipt["simulator_started"] = True
            receipt["started_at_utc"] = datetime.now(timezone.utc).isoformat()
            event_seed = int(digest({
                "base_seed": self.seed, "candidate_id": candidate_id,
                "block_id": block.block_id})[:8], 16)
            receipt["simulation_seed"] = event_seed
            binding = {**self.execution_binding, "method_id": self.method_id,
                       "candidate_id": candidate_id, "block_id": block.block_id,
                       "source_sha256": block.source_sha256, "data_version": block.data_version}
            try:
                sim = simulate_checked(
                    block.profile, controller, self.site, self.limits,
                    supervisor=self.supervisor, seed=event_seed, event_binding=binding)
                metrics = compute_metrics_v2(sim.series, self.site)
                finite_array([metrics[k] for k in OBJECTIVES], "objective metrics", ndim=1)
                row = {
                    "block_id": block.block_id, "source": block.source,
                    "split": block.split,
                    "site_id": None if block.site_id is None else str(block.site_id),
                    "n_ticks": len(block.profile), **metrics}
                receipt["status"] = "COMPLETED"
                receipt["output_sha256"] = digest(row)
                receipt["supervision"] = sim.meta["supervision"]
                rows.append(row)
            except Exception as exc:
                receipt["status"] = "FAILED"
                receipt["failure"] = {
                    "type": type(exc).__name__, "message": str(exc)[:512],
                    "receipt": getattr(exc, "receipt", None),
                    "result_policy": "INVALID_RUN_EXCLUDED_NO_PARTIAL_METRICS"}
                for later in batch[i + 1:]:
                    later["status"] = "NOT_STARTED"
                    later["reason"] = "PRIOR_EVENT_FAILED_RESERVATION_REMAINS_CHARGED"
                raise
            finally:
                receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        return rows

    def evaluate_block(self, params, block, *, candidate_id):
        return self._evaluate_batch(params, [block], candidate_id=candidate_id)[0]

    def evaluate(self, params, blocks, *, candidate_id):
        return pd.DataFrame(self._evaluate_batch(params, blocks, candidate_id=candidate_id))

    @staticmethod
    def aggregate(metrics: pd.DataFrame, risk: RiskConfig = RiskConfig()) -> dict[str, float]:
        if not isinstance(metrics, pd.DataFrame) or tuple(risk.objectives) != OBJECTIVES:
            raise ContractError("strict aggregation requires four canonical objectives")
        if any(c not in metrics.columns for c in OBJECTIVES):
            raise ContractError("missing objective columns")
        matrix = finite_array(metrics[list(OBJECTIVES)].to_numpy(),
                              "strict replay objective matrix", ndim=2)
        score = strict_risk(matrix, q=risk.q, tail_weight=risk.tail_weight)
        return dict(zip(OBJECTIVES, map(float, score), strict=True))
