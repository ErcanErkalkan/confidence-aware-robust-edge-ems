from __future__ import annotations

import math
import pytest

from temporal_mapping_prelock import derive_temporal_mapping


def test_one_minute_mapping_is_identity_for_frozen_temporal_defaults():
    m = derive_temporal_mapping(1)
    assert math.isclose(m.ts_hours, 1 / 60)
    assert math.isclose(m.r_max_kw_per_tick, 20.0)
    assert m.t_min_ticks == 3
    assert m.cap_fix_hold_ticks == 3
    assert m.prep_hold_ticks == 5
    assert m.w_f_ticks == 5
    assert m.horizon_k_ticks == 10
    assert m.near_cap_window_ticks == 3
    assert math.isclose(m.d_lim_kw_per_tick, 8.0)
    assert math.isclose(m.ema_beta, 0.25)
    assert math.isclose(m.ema_equivalent_span_ticks, 7.0)
    assert math.isclose(m.hold_decay_per_tick, 0.60)
    assert m.coarse_resolution_flags == ()


def test_two_minute_mapping_preserves_physical_targets_with_upward_quantization():
    m = derive_temporal_mapping(2)
    assert math.isclose(m.ts_hours, 2 / 60)
    assert math.isclose(m.r_max_kw_per_tick, 40.0)
    assert m.t_min_ticks == 2       # 3 min target -> 4 min achieved
    assert m.cap_fix_hold_ticks == 2
    assert m.prep_hold_ticks == 3   # 5 min target -> 6 min achieved
    assert m.w_f_ticks == 3         # 5 min target -> 6 min achieved
    assert m.horizon_k_ticks == 5   # 10 min target exact
    assert m.near_cap_window_ticks == 2
    assert math.isclose(m.d_lim_kw_per_tick, 16.0)
    assert math.isclose(m.ema_beta, 1 - 0.75**2)
    assert math.isclose(m.hold_decay_per_tick, 0.60**2)


def test_five_minute_mapping_reports_unresolvable_shorter_windows():
    m = derive_temporal_mapping(5)
    assert m.t_min_ticks == 1
    assert m.cap_fix_hold_ticks == 1
    assert m.prep_hold_ticks == 1
    assert m.w_f_ticks == 1
    assert m.horizon_k_ticks == 2
    assert m.near_cap_window_ticks == 1
    assert set(m.coarse_resolution_flags) == {"t_min", "cap_fix_hold", "near_cap_window"}
    assert math.isclose(m.hold_decay_per_tick, 0.60**5)


def test_rate_like_limits_scale_with_cadence():
    for c in (1, 2, 5, 10, 15, 30):
        m = derive_temporal_mapping(c)
        assert math.isclose(m.r_max_kw_per_tick / c, 20.0)
        assert math.isclose(m.d_lim_kw_per_tick / c, 8.0)


def test_ema_retention_preserves_same_physical_decay():
    beta1 = derive_temporal_mapping(1).ema_beta
    retention1 = 1 - beta1
    for c in (2, 5, 10, 15, 30):
        m = derive_temporal_mapping(c)
        assert math.isclose(1 - m.ema_beta, retention1**c, rel_tol=1e-12, abs_tol=1e-12)


def test_invalid_cadence_fails_closed():
    with pytest.raises(ValueError):
        derive_temporal_mapping(0)
    with pytest.raises(ValueError):
        derive_temporal_mapping(3)
