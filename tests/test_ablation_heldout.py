from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from crmt_edge_ems.parameter_space import PARAM_NAMES
from opencem_ablation_internal_test import load_ablation_selection


def test_ablation_selection_loader_rejects_hash_tampering(tmp_path):
    row = {"method": "NO_CVAR", "candidate_id": "c1"}
    row.update({p: 0.1 for p in PARAM_NAMES})
    selected = pd.DataFrame([row])
    selected_path = tmp_path / "selected_ablation_candidate.csv"
    selected.to_csv(selected_path, index=False, lineterminator="\n")
    digest = hashlib.sha256(selected_path.read_bytes()).hexdigest()
    lock = {
        "stage": "CRMT_ABLATION_VALIDATION_SELECTION_LOCK",
        "protocol_version": "opencem-confirmatory-prelock-v1",
        "ablation_id": "NO_CVAR",
        "seed": 1001,
        "data_context": {"manifest_sha256": "m"},
        "selected_ablation_candidate_sha256": digest,
    }
    (tmp_path / "ablation_selection_lock.json").write_text(
        json.dumps(lock), encoding="utf-8"
    )
    selected.loc[0, PARAM_NAMES[0]] = 0.2
    selected.to_csv(selected_path, index=False, lineterminator="\n")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        load_ablation_selection(
            tmp_path,
            ablation_id="NO_CVAR",
            seed=1001,
            expected_manifest_sha="m",
        )
