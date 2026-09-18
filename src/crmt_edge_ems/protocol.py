from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from jer_microgrid.config import SiteConfig

from .site_model import (
    PRIMARY_COMMAND_RAMP_KW_PER_MIN,
    PRIMARY_OPENCEM_CADENCE_MINUTES,
    build_opencem_subsystem_site,
    primary_opencem_assumptions,
)


PROTOCOL_VERSION = "opencem-confirmatory-prelock-v1"
TRAIN_BLOCK_COUNT = 210
VALIDATION_BLOCK_COUNT = 118
INTERNAL_TEST_BLOCK_COUNT = 78
OPTIMIZER_SEEDS = tuple(range(1001, 1031))

METHOD_IDS = ("SOBOL", "NSGAII", "MOPSO", "MODE", "CRMT")
CONFIRMATORY_CONTROLLER_BLOCK_BUDGET = 12_600  # per seed, per method
FULL_TRAIN_CANDIDATE_COST = TRAIN_BLOCK_COUNT
BASELINE_FULL_CANDIDATE_CAPACITY = (
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET // FULL_TRAIN_CANDIDATE_COST
)
CRMT_CANDIDATE_POOL_SIZE = 256

SELECTION_RULE_ID = "validation-equal-weight-chebyshev-v1"
SELECTION_PRIMARY_METRIC = "normalized_linf"
SELECTION_SECONDARY_METRIC = "normalized_l1"
SELECTION_FINAL_TIE_BREAK = "candidate_id_lexicographic"
SELECTION_RANGE_EPS = 1e-12
PER_METHOD_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET = (
    CONFIRMATORY_CONTROLLER_BLOCK_BUDGET * len(OPTIMIZER_SEEDS)
)
ALL_METHODS_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET = (
    PER_METHOD_ALL_SEEDS_CONTROLLER_BLOCK_BUDGET * len(METHOD_IDS)
)

# Hyperparameters and the numeric controller-block budget are frozen before
# confirmatory optimizer results are viewed. The budget was selected only after
# the real-data runtime preflight and is equal across all methods/seeds.
BASELINE_HYPERPARAMETERS: dict[str, dict[str, Any]] = {
    "SOBOL": {"batch_size": 20},
    "NSGAII": {"pop_size": 20, "crossover_prob": 0.90, "eta_c": 15.0, "eta_m": 20.0},
    "MOPSO": {
        "swarm_size": 20,
        "archive_size": 100,
        "inertia": 0.50,
        "c1": 1.50,
        "c2": 1.50,
        "velocity_clip": 0.20,
    },
    "MODE": {"pop_size": 20, "differential_weight": 0.50, "crossover_rate": 0.90},
}
CRMT_HYPERPARAMETERS: dict[str, Any] = {
    "candidate_pool_size": CRMT_CANDIDATE_POOL_SIZE,
    "initial_blocks": 4,
    "allocation_batch": 2,
    "alpha": 0.05,
    "n_boot": 2000,
    "risk_q": 0.90,
    "tail_weight": 0.50,
}


@dataclass(frozen=True)
class SiteSensitivityVariant:
    variant_id: str
    eta_ch: float | None = None
    eta_dis: float | None = None
    soc_min: float | None = None
    soc_max: float | None = None
    command_ramp_multiplier: float = 1.0
    duration_quantization: str = "ceil"
    rationale: str = ""


SITE_SENSITIVITY_VARIANTS: tuple[SiteSensitivityVariant, ...] = (
    SiteSensitivityVariant(
        "ETA_LOW_090",
        eta_ch=0.90,
        eta_dis=0.90,
        rationale="Lower symmetric model-efficiency sensitivity; not an upstream measured value.",
    ),
    SiteSensitivityVariant(
        "ETA_IDEAL_100",
        eta_ch=1.00,
        eta_dis=1.00,
        rationale="Ideal-loss upper bound for the model-efficiency assumption.",
    ),
    SiteSensitivityVariant(
        "SOC_CONSERVATIVE_15_95",
        soc_min=0.15,
        soc_max=0.95,
        rationale="More conservative hard SOC envelope with unchanged 0.50 initial SOC.",
    ),
    SiteSensitivityVariant(
        "RAMP_HALF",
        command_ramp_multiplier=0.50,
        rationale="Half of the primary non-binding command-ramp rate.",
    ),
    SiteSensitivityVariant(
        "RAMP_QUARTER",
        command_ramp_multiplier=0.25,
        rationale="Quarter of the primary non-binding command-ramp rate.",
    ),
    SiteSensitivityVariant(
        "TEMPORAL_FLOOR",
        duration_quantization="floor",
        rationale="Lower bracketing of non-representable 3- and 5-minute integer windows at 2-minute cadence.",
    ),
)

_VARIANTS = {v.variant_id: v for v in SITE_SENSITIVITY_VARIANTS}


def sensitivity_variant(variant_id: str) -> SiteSensitivityVariant:
    try:
        return _VARIANTS[str(variant_id)]
    except KeyError as exc:
        raise KeyError(f"Unknown site sensitivity variant: {variant_id}") from exc


def build_opencem_sensitivity_site(inverter_id: int, variant_id: str) -> SiteConfig:
    """Build one predeclared one-at-a-time site sensitivity.

    These variants are robustness/sensitivity analyses. They must not be selected
    using internal-test outcomes and must not be described as measured OpenCEM
    hardware settings.
    """
    variant = sensitivity_variant(variant_id)
    base = primary_opencem_assumptions(inverter_id)
    updated = replace(
        base,
        eta_ch=base.eta_ch if variant.eta_ch is None else float(variant.eta_ch),
        eta_dis=base.eta_dis if variant.eta_dis is None else float(variant.eta_dis),
        soc_min=base.soc_min if variant.soc_min is None else float(variant.soc_min),
        soc_max=base.soc_max if variant.soc_max is None else float(variant.soc_max),
        command_ramp_kw_per_min=float(PRIMARY_COMMAND_RAMP_KW_PER_MIN)
        * float(variant.command_ramp_multiplier),
    )
    updated.validate()
    return build_opencem_subsystem_site(
        updated,
        cadence_minutes=PRIMARY_OPENCEM_CADENCE_MINUTES,
        duration_quantization=variant.duration_quantization,
    )
