"""Opt-in capacity accounting for new engineering runs; legacy/v2 stay frozen.

The default numerical tolerance matches SafetyLimits.veto (1e-12 kW).
Meter resolution is an uncertainty annotation, never permission to exceed a cap.
All caps here are declared scenario caps, not independently measured contracts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np

from .contracts import ContractError, digest, finite_array
from .metrics_v2 import compute_metrics_v2

METRICS_VERSION = "CRMT-METRICS-v3-RAINFLOW-TERMINAL-SOC-CAPACITY-TOLERANCE"
CAPACITY_POLICY_VERSION = "CRMT-CAPACITY-v1-NUMERICAL-TOLERANCE-RESOLUTION-SEPARATE"


@dataclass(frozen=True)
class CapacityPolicy:
    """Numerical allowance max(atol_kw, rtol * explicit physical scale).

    The benchmark default is absolute 1e-12 kW, rtol=0. A nonzero relative
    tolerance requires an explicit reference scale; it is not fitted to data.
    Measurement resolution, when independently known, marks near-boundary
    observations as unresolved, but does not change violation classification.
    """

    atol_kw: float = 1e-12
    rtol: float = 0.0
    reference_scale_kw: float = 1.0
    measurement_resolution_kw: float | None = None

    def __post_init__(self):
        values = (self.atol_kw, self.rtol, self.reference_scale_kw)
        if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, float, np.number))
               or not math.isfinite(x) for x in values):
            raise ContractError("capacity policy requires finite numeric tolerances")
        if min(self.atol_kw, self.rtol) < 0 or self.reference_scale_kw <= 0:
            raise ContractError("capacity policy tolerances must be nonnegative; scale positive")
        resolution = self.measurement_resolution_kw
        if resolution is not None and (
                isinstance(resolution, (bool, np.bool_))
                or not isinstance(resolution, (int, float, np.number))
                or not math.isfinite(resolution) or resolution <= 0):
            raise ContractError("measurement resolution must be positive when independently known")

    @property
    def tolerance_kw(self):
        return max(float(self.atol_kw), float(self.rtol * self.reference_scale_kw))

    @property
    def identity(self):
        return CAPACITY_POLICY_VERSION + ":" + digest(asdict(self))


def capacity_accounting(grid_kw, import_cap_kw, export_cap_kw, *, policy=CapacityPolicy()):
    """Compare a single aligned trajectory; reject missing/negative limits.

    Uses grid > cap + tolerance (and -grid > export cap + tolerance), exactly
    matching the safety comparator at the default policy. Equality is accepted.
    """
    if not isinstance(policy, CapacityPolicy):
        raise ContractError("CapacityPolicy required")
    grid = finite_array(grid_kw, "grid kW", ndim=1)
    imp = finite_array(import_cap_kw, "import cap kW", ndim=1)
    exp = finite_array(export_cap_kw, "export cap kW", ndim=1)
    if grid.shape != imp.shape or grid.shape != exp.shape:
        raise ContractError("capacity trajectories must have identical shape")
    if np.any(imp < 0) or np.any(exp < 0):
        raise ContractError("capacity limits must be nonnegative")
    tolerance = policy.tolerance_kw
    if not np.isfinite(imp + tolerance).all() or not np.isfinite(exp + tolerance).all():
        raise ContractError("capacity threshold overflow")
    legacy_imp = grid > imp
    legacy_exp = -grid > exp
    import_violation = grid > imp + tolerance
    export_violation = -grid > exp + tolerance
    excess = np.maximum(grid - imp, -grid - exp)
    near = np.zeros(len(grid), dtype=bool)
    if policy.measurement_resolution_kw is not None:
        near = np.abs(excess) <= policy.measurement_resolution_kw / 2
    return {
        "import_violation": import_violation,
        "export_violation": export_violation,
        "legacy_violation": legacy_imp | legacy_exp,
        "violation": import_violation | export_violation,
        "positive_excess_kw": np.maximum(excess, 0),
        "measurement_boundary_unresolved": near,
        "tolerance_kw": tolerance,
        "policy_id": policy.identity,
    }


def compute_metrics_v3(sim, site, *, policy=CapacityPolicy()):
    """v2 Rainflow/full terminal SOC plus explicit numerical capacity policy."""
    result = compute_metrics_v2(sim, site)
    flags = capacity_accounting(sim["grid_kw"].to_numpy(), sim["p_imp_cap"].to_numpy(),
                                sim["p_exp_cap"].to_numpy(), policy=policy)
    result["legacy_cap_violation_pct_total"] = result["cap_violation_pct_total"]
    for suffix, key in (("import", "import_violation"), ("export", "export_violation"),
                        ("total", "violation")):
        result["cap_violation_pct_" + suffix] = 100 * float(flags[key].mean())
    if "is_disconnected" in sim:
        offline = sim["is_disconnected"].to_numpy(dtype=bool)
        result["resilience_score"] = (100 * (1 - float(flags["violation"][offline].mean()))
                                      if offline.any() else 100.0)
    result.update({
        "metrics_version": METRICS_VERSION,
        "capacity_policy_id": flags["policy_id"],
        "capacity_policy": asdict(policy),
        "capacity_tolerance_kw": flags["tolerance_kw"],
        "capacity_numerical_only_ticks": int(np.sum(flags["legacy_violation"] & ~flags["violation"])),
        "capacity_violating_ticks": int(flags["violation"].sum()),
        "capacity_max_positive_excess_kw": float(flags["positive_excess_kw"].max()),
        "capacity_measurement_boundary_unresolved_ticks": int(flags["measurement_boundary_unresolved"].sum()),
        "measurement_resolution_known": policy.measurement_resolution_kw is not None,
        "capacity_evidence": "DECLARED_SCENARIO_CAPS_NOT_PHYSICAL_GRID_CERTIFICATION",
    })
    return result
