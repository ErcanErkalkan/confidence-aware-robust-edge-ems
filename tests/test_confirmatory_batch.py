from __future__ import annotations

import pytest

import opencem_confirmatory_batch as batch


def test_frozen_seed_range_accepts_contiguous_registry_slices():
    assert batch._seed_range(1001, 1001) == (1001,)
    assert batch._seed_range(1001, 1006) == tuple(range(1001, 1007))
    assert batch._seed_range(1025, 1030) == tuple(range(1025, 1031))


def test_frozen_seed_range_fails_closed_outside_registry():
    with pytest.raises(ValueError):
        batch._seed_range(1000, 1001)
    with pytest.raises(ValueError):
        batch._seed_range(1030, 1031)
    with pytest.raises(ValueError):
        batch._seed_range(1005, 1004)
