from __future__ import annotations

from crmt_edge_ems.protocol import ABLATION_IDS
from opencem_confirmatory_batch import _seed_range


def test_ablation_internal_batch_registry_and_shards_are_frozen():
    assert ABLATION_IDS == ("NO_CVAR", "NO_CONFIDENCE", "NO_ADAPTIVE")
    assert _seed_range(1001, 1006) == tuple(range(1001, 1007))
    assert _seed_range(1025, 1030) == tuple(range(1025, 1031))
