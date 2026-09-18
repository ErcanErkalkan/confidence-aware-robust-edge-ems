from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil

ALLOWED_CADENCE_MINUTES = (1, 2, 5, 10, 15, 30)
BASE_CADENCE_MINUTES = 1.0


@dataclass(frozen=True)
class TemporalMapping:
    cadence_minutes: float
    ts_hours: float
    r_max_kw_per_tick: float
    t_min_ticks: int
    cap_fix_hold_ticks: int
    prep_hold_ticks: int
    w_f_ticks: int
    horizon_k_ticks: int
    near_cap_window_ticks: int
    d_lim_kw_per_tick: float
    ema_beta: float
    ema_equivalent_span_ticks: float
    hold_decay_per_tick: float
    target_t_min_minutes: float
    achieved_t_min_minutes: float
    target_cap_fix_hold_minutes: float
    achieved_cap_fix_hold_minutes: float
    target_prep_hold_minutes: float
    achieved_prep_hold_minutes: float
    target_w_f_minutes: float
    achieved_w_f_minutes: float
    target_horizon_minutes: float
    achieved_horizon_minutes: float
    target_near_cap_window_minutes: float
    achieved_near_cap_window_minutes: float
    coarse_resolution_flags: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _ceil_ticks(duration_minutes: float, cadence_minutes: float, *, allow_zero: bool = False) -> int:
    if cadence_minutes <= 0:
        raise ValueError("cadence_minutes must be > 0")
    if duration_minutes < 0:
        raise ValueError("duration_minutes must be >= 0")
    if duration_minutes == 0 and allow_zero:
        return 0
    return max(1, int(ceil(duration_minutes / cadence_minutes)))


def derive_temporal_mapping(
    cadence_minutes: float,
    *,
    base_r_max_kw_per_tick: float = 20.0,
    base_t_min_ticks: int = 3,
    base_w_f_ticks: int = 5,
    base_w_ema_span_ticks: float = 7.0,
    base_horizon_k_ticks: int = 10,
    base_d_lim_kw_per_tick: float = 8.0,
    base_cap_fix_hold_ticks: int | None = None,
    base_prep_hold_extra_ticks: int = 2,
    base_near_cap_window_ticks: int = 3,
    base_hold_decay_per_tick: float = 0.60,
    enforce_allowed: bool = True,
) -> TemporalMapping:
    """Map the frozen 1-minute controller's temporal semantics to a new cadence.

    Durations are preserved in physical minutes and quantized upward to whole replay
    ticks. Rate-like per-tick limits are scaled by cadence. Exponential per-tick
    decay is mapped by equal physical-time decay. The FBRL EMA is mapped by equal
    exponential retention rather than by naively rounding its span.

    This function does not mutate the controller. It is a protocol/preflight mapper
    that must be integrated into real-data SiteConfig/controller construction before
    confirmatory replay when cadence != 1 minute.
    """
    c = float(cadence_minutes)
    if c <= 0:
        raise ValueError("cadence_minutes must be > 0")
    if enforce_allowed and c not in ALLOWED_CADENCE_MINUTES:
        raise ValueError(f"cadence_minutes must be one of {ALLOWED_CADENCE_MINUTES}")
    if base_w_ema_span_ticks <= 0:
        raise ValueError("base_w_ema_span_ticks must be > 0")
    if not (0.0 < base_hold_decay_per_tick <= 1.0):
        raise ValueError("base_hold_decay_per_tick must be in (0, 1]")

    ratio = c / BASE_CADENCE_MINUTES

    # Physical durations encoded by the frozen one-minute source.
    target_t_min = float(base_t_min_ticks) * BASE_CADENCE_MINUTES
    base_cap_ticks = max(1, int(base_t_min_ticks)) if base_cap_fix_hold_ticks is None else int(base_cap_fix_hold_ticks)
    target_cap = float(base_cap_ticks) * BASE_CADENCE_MINUTES
    target_prep = float(base_cap_ticks + int(base_prep_hold_extra_ticks)) * BASE_CADENCE_MINUTES
    target_wf = float(base_w_f_ticks) * BASE_CADENCE_MINUTES
    target_horizon = float(base_horizon_k_ticks) * BASE_CADENCE_MINUTES
    target_near = float(base_near_cap_window_ticks) * BASE_CADENCE_MINUTES

    t_min_ticks = _ceil_ticks(target_t_min, c, allow_zero=True)
    cap_ticks = _ceil_ticks(target_cap, c)
    prep_ticks = _ceil_ticks(target_prep, c)
    wf_ticks = _ceil_ticks(target_wf, c)
    horizon_ticks = _ceil_ticks(target_horizon, c)
    near_ticks = _ceil_ticks(target_near, c)

    # Frozen FBRL source: beta_1 = 2/(span+1), retention_1 = 1-beta_1.
    beta_1 = 2.0 / (float(base_w_ema_span_ticks) + 1.0)
    retention_1 = 1.0 - beta_1
    retention_c = retention_1 ** ratio
    beta_c = 1.0 - retention_c
    ema_span_equiv = (2.0 / beta_c) - 1.0

    # Frozen Proposed source decays prior command by hold_decay once per tick.
    hold_decay_c = float(base_hold_decay_per_tick) ** ratio

    flags: list[str] = []
    for name, target in (
        ("t_min", target_t_min),
        ("cap_fix_hold", target_cap),
        ("prep_hold", target_prep),
        ("w_f", target_wf),
        ("horizon", target_horizon),
        ("near_cap_window", target_near),
    ):
        if 0 < target < c:
            flags.append(name)

    return TemporalMapping(
        cadence_minutes=c,
        ts_hours=c / 60.0,
        r_max_kw_per_tick=float(base_r_max_kw_per_tick) * ratio,
        t_min_ticks=t_min_ticks,
        cap_fix_hold_ticks=cap_ticks,
        prep_hold_ticks=prep_ticks,
        w_f_ticks=wf_ticks,
        horizon_k_ticks=horizon_ticks,
        near_cap_window_ticks=near_ticks,
        d_lim_kw_per_tick=float(base_d_lim_kw_per_tick) * ratio,
        ema_beta=beta_c,
        ema_equivalent_span_ticks=ema_span_equiv,
        hold_decay_per_tick=hold_decay_c,
        target_t_min_minutes=target_t_min,
        achieved_t_min_minutes=t_min_ticks * c,
        target_cap_fix_hold_minutes=target_cap,
        achieved_cap_fix_hold_minutes=cap_ticks * c,
        target_prep_hold_minutes=target_prep,
        achieved_prep_hold_minutes=prep_ticks * c,
        target_w_f_minutes=target_wf,
        achieved_w_f_minutes=wf_ticks * c,
        target_horizon_minutes=target_horizon,
        achieved_horizon_minutes=horizon_ticks * c,
        target_near_cap_window_minutes=target_near,
        achieved_near_cap_window_minutes=near_ticks * c,
        coarse_resolution_flags=tuple(flags),
    )
