from __future__ import annotations

from opencem_ablation_report import ABLATION_COMPARISON_METHODS


def test_ablation_report_method_registry_is_prelocked():
    assert ABLATION_COMPARISON_METHODS == (
        "CRMT", "NO_CVAR", "NO_CONFIDENCE", "NO_ADAPTIVE"
    )
