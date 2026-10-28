import json

import numpy as np
import pandas as pd
import pytest

from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.metric_replay_audit import verified_controller_profile, ReplayCheckpoints
from crmt_edge_ems.metrics_v2 import rainflow_cycles_detailed_v2
from crmt_edge_ems.contracts import strict_risk


def raw_frame():
    x = pd.DataFrame({"block_id": "opencem:inv1:2025-08-02",
                      "bin_utc": pd.date_range("2025-08-01T16:00:00Z", periods=720, freq="2min")})
    for kind, value in (("load", 1.0), ("pv", .25), ("base", .75)):
        x[kind + "_kw_raw"] = value
        x[kind + "_kw_frozen"] = value
    return x


def test_raw_to_controller_preserves_values_without_interpolation():
    x = raw_frame()
    profile, receipt = verified_controller_profile(x)
    assert len(profile) == 720
    np.testing.assert_array_equal(profile.base_kw, x.base_kw_raw)
    assert profile.peak_flag.eq(0).all()
    assert receipt["base_kw_max_abs_raw_frozen_kw"] == 0


@pytest.mark.parametrize("corruption", ["duplicate", "gap", "nonfinite", "schema", "partial", "mismatch", "naive", "identity"])
def test_raw_to_controller_negative_cases(corruption):
    x = raw_frame()
    if corruption == "duplicate":
        x.loc[1, "bin_utc"] = x.loc[0, "bin_utc"]
    elif corruption == "gap":
        x.loc[719, "bin_utc"] += pd.Timedelta(minutes=2)
    elif corruption == "nonfinite":
        x.loc[10, "base_kw_raw"] = np.nan
    elif corruption == "schema":
        x["unexpected"] = 0
    elif corruption == "partial":
        x = x.iloc[:-1]
    elif corruption == "mismatch":
        x.loc[0, "base_kw_raw"] += .01
    elif corruption == "naive":
        x["bin_utc"] = x.bin_utc.dt.tz_localize(None)
    elif corruption == "identity":
        x["base_kw_raw"] = x["base_kw_frozen"] = .5
    with pytest.raises(ContractError):
        verified_controller_profile(x)


def test_checkpoint_resume_and_tamper_detection(tmp_path):
    store = ReplayCheckpoints(tmp_path, {"input": "hash1", "source": "hash2"})
    store.write_batch("batch_0000", [{"candidate": "A", "value": 1}])
    assert ReplayCheckpoints(tmp_path, {"source": "hash2", "input": "hash1"}).read_batch("batch_0000")[0]["value"] == 1
    with pytest.raises(ContractError, match="binding"):
        ReplayCheckpoints(tmp_path, {"input": "changed"})
    (tmp_path / "batch_0000.json").write_text("[]")
    with pytest.raises(ContractError, match="altered"):
        store.read_batch("batch_0000")


def test_checkpoint_trajectory_artifact_is_bound(tmp_path):
    store = ReplayCheckpoints(tmp_path, {"source": "A"})
    trace = tmp_path / "trace.npz"
    trace.write_bytes(b"bound trajectory")
    store.write_batch("batch", [{"valid": True}], artifacts=[trace])
    trace.write_bytes(b"modified")
    with pytest.raises(ContractError, match="trajectory artifact"):
        store.read_batch("batch")


@pytest.mark.parametrize("path,expected", [([.2, .8], [(.6, .5)]),
                                         ([.2, .8, .2], [(.6, .5), (.6, .5)]),
                                         ([.2, .8, .5, .7, .2], [(.2, 1.0), (.6, .5), (.6, .5)])])
def test_reference_rainflow_cycle_multisets(path, expected):
    actual = sorted((round(d, 12), w) for d, w, _, _ in rainflow_cycles_detailed_v2(path))
    assert actual == sorted((round(d, 12), w) for d, w in expected)


def test_four_block_cvar_is_worst_block_not_claim_of_tail_precision():
    x = np.arange(16, dtype=float).reshape(4, 4)
    np.testing.assert_allclose(strict_risk(x), x.mean(axis=0) + .5 * x.max(axis=0))
