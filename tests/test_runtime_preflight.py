from __future__ import annotations

import pytest

import opencem_runtime_preflight as rp


def test_evenly_spaced_is_deterministic_and_includes_endpoints():
    keys = [f"d{i:02d}" for i in range(11)]
    a = rp._evenly_spaced(keys, 5)
    b = rp._evenly_spaced(keys, 5)
    assert a == b
    assert a[0] == "d00"
    assert a[-1] == "d10"
    assert len(a) == 5


def test_evenly_spaced_fails_closed_on_empty_or_nonpositive_request():
    with pytest.raises(ValueError):
        rp._evenly_spaced([], 5)
    with pytest.raises(ValueError):
        rp._evenly_spaced(["d0"], 0)
