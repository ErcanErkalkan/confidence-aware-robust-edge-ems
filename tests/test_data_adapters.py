import numpy as np
import pandas as pd
import pytest

from data_adapters.opencem import (
    DEFAULT_CONFIRMATORY_SPLIT,
    assign_confirmatory_split,
    audit_raw_measurements,
    daily_blocks,
    reconstruct_counterfactual_profile,
    refuse_unsafe_grid_as_uncontrolled_base,
)
from data_adapters.ausgrid import customer_profile


def test_opencem_schema_audit_and_safety_guard():
    df = pd.DataFrame({
        'read_ts':[1], 'inverter':[1], 'battvolt':[51.2], 'battcurr':[0.0], 'battsoc':[50],
        'pv1power':[100], 'outw_a':[200], 'gridpowerw_a':[100]
    })
    a = audit_raw_measurements(df)
    assert a.minimum_schema_ok and a.inverter_ids == (1,)
    with pytest.raises(RuntimeError):
        refuse_unsafe_grid_as_uncontrolled_base()


def test_opencem_two_inverter_counterfactual_uses_load_minus_pv_not_grid():
    t0 = pd.Timestamp('2026-01-01T00:00:00Z').timestamp()
    df = pd.DataFrame({
        'read_ts': [t0, t0 + 10, t0, t0 + 10],
        'inverter': [1, 1, 2, 2],
        'outsumw': [2000, 2200, 1000, 1200],
        'pv1power': [500, 700, 200, 400],
        'gridpowerw_a': [9999, 9999, 9999, 9999],
    })
    p = reconstruct_counterfactual_profile(df, expected_inverters=(1, 2), frequency='1min')
    assert len(p) == 1
    # Per-inverter means: load=(2.1+1.1)=3.2 kW; PV=(0.6+0.3)=0.9 kW.
    assert np.isclose(p.loc[0, 'load_kw'], 3.2)
    assert np.isclose(p.loc[0, 'pv_kw'], 0.9)
    assert np.isclose(p.loc[0, 'base_kw'], 2.3)
    assert not np.isclose(p.loc[0, 'base_kw'], 9.999)


def test_opencem_requires_all_expected_inverters_per_bin():
    t0 = pd.Timestamp('2026-01-01T00:00:00Z').timestamp()
    df = pd.DataFrame({
        'read_ts': [t0, t0 + 60, t0],
        'inverter': [1, 1, 2],
        'outsumw': [1000, 1000, 1000],
        'pv1power': [100, 100, 100],
    })
    p = reconstruct_counterfactual_profile(df, expected_inverters=(1, 2), frequency='1min')
    # 00:00 has both inverters; 00:01 only inverter 1, so it must be dropped.
    assert len(p) == 1


def test_frozen_chronological_split_excludes_boundary_partial_days():
    # Minimal one-row frames are sufficient because this test targets split assignment,
    # not the separate daily completeness gate.
    dates = [
        '2025-07-13', '2025-07-14', '2025-12-31',
        '2026-01-01', '2026-02-28', '2026-03-01',
        '2026-04-11', '2026-04-12'
    ]
    blocks = {d: pd.DataFrame({'local_date':[d]}) for d in dates}
    s = assign_confirmatory_split(blocks, split=DEFAULT_CONFIRMATORY_SPLIT)
    assert set(s['train']) == {'2025-07-14', '2025-12-31'}
    assert set(s['validation']) == {'2026-01-01', '2026-02-28'}
    assert set(s['internal_test']) == {'2026-03-01', '2026-04-11'}
    assert '2025-07-13' not in set().union(*[set(v) for v in s.values()])
    assert '2026-04-12' not in set().union(*[set(v) for v in s.values()])


def test_daily_blocks_applies_coverage_gate():
    # One complete minute-level UTC day mapped to a single local_date label.
    ts = pd.date_range('2026-01-01', periods=1440, freq='1min', tz='UTC')
    profile = pd.DataFrame({'timestamp':ts, 'local_date':['2026-01-01']*1440})
    blocks = daily_blocks(profile, expected_frequency_minutes=1, min_coverage=0.95)
    assert '2026-01-01' in blocks
    partial = profile.iloc[:1000].copy()
    assert not daily_blocks(partial, expected_frequency_minutes=1, min_coverage=0.95)


def test_ausgrid_halfhour_energy_to_kw_and_net_load():
    cols=[]
    for k in range(1,49):
        mins=30*k
        hh=(mins//60)%24; mm=mins%60
        cols.append(f'{hh}:{mm:02d}')
    rows=[]
    for cat,val in [('GC',1.0),('GG',0.25),('CL',0.5)]:
        row={'Customer':1,'Consumption Category':cat,'Date':'01Jul2010'}
        row.update({c:val for c in cols}); rows.append(row)
    p=customer_profile(pd.DataFrame(rows),1)
    assert len(p)==48
    # (1.0+0.5-0.25) kWh / 0.5 h = 2.5 kW net load.
    assert np.allclose(p['base_kw'],2.5)


def test_opencem_reconstruction_does_not_infer_peak_window():
    from data_adapters.opencem import apply_peak_window
    t0 = pd.Timestamp('2026-01-01T09:00:00Z').timestamp()  # 17:00 Asia/Shanghai
    df = pd.DataFrame({
        'read_ts': [t0, t0], 'inverter': [1, 2],
        'outsumw': [1000, 1000], 'pv1power': [100, 100],
    })
    p = reconstruct_counterfactual_profile(df, expected_inverters=(1, 2), frequency='1min')
    assert int(p['peak_flag'].sum()) == 0
    q = apply_peak_window(p, local_timezone='Asia/Shanghai', start_hour=17, end_hour=22)
    assert int(q.loc[0, 'peak_flag']) == 1


def test_opencem_primary_per_inverter_replay_preserves_independent_subsystems():
    from data_adapters.opencem import reconstruct_per_inverter_profiles
    t0 = pd.Timestamp('2026-01-01T00:00:00Z').timestamp()
    df = pd.DataFrame({
        'read_ts': [t0, t0 + 10, t0, t0 + 10],
        'inverter': [1, 1, 2, 2],
        'outsumw': [2000, 2200, 1000, 1200],
        'pv1power': [500, 700, 200, 400],
    })
    profiles = reconstruct_per_inverter_profiles(df, expected_inverters=(1, 2), frequency='1min')
    assert set(profiles) == {1, 2}
    assert np.isclose(profiles[1].loc[0, 'base_kw'], 1.5)  # 2.1 - 0.6
    assert np.isclose(profiles[2].loc[0, 'base_kw'], 0.8)  # 1.1 - 0.3
    assert int(profiles[1].loc[0, 'source_inverter']) == 1
    assert int(profiles[2].loc[0, 'source_inverter']) == 2
    assert profiles[1]['peak_flag'].sum() == 0
    assert profiles[2]['peak_flag'].sum() == 0
