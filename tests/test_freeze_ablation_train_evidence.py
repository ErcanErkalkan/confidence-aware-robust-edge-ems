import hashlib
import json
from pathlib import Path

from tools.freeze_ablation_train_evidence import (
    INDEX_NAME,
    LOCK_NAME,
    SHA_NAME,
    freeze_ablation_train,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_evidence(root: Path) -> None:
    for ablation in ("NO_CVAR", "NO_CONFIDENCE", "NO_ADAPTIVE"):
        for seed in range(1001, 1031):
            directory = root / f"{ablation}_seed{seed}"
            directory.mkdir(parents=True)
            payloads = {
                "candidate_metrics.csv": "candidate_id,value\nc1,1\n",
                "optimizer_front.csv": "candidate_id,obj\nc1,1\n",
                "ledger.csv": "candidate_id,block_id\nc1,b1\n",
            }
            for name, payload in payloads.items():
                (directory / name).write_text(payload, encoding="utf-8")
            summary = {
                "stage": "CRMT_ABLATION_TRAIN_ONLY",
                "ablation_id": ablation,
                "seed": seed,
                "controller_block_budget": 12600,
                "ledger_used": 12600,
                "archive_size": 1,
                "git_sha": "128c6d3be06d9efd7921f903065bc727ac1d7440",
                "data_context": {
                    "manifest_sha256": "3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1",
                    "split": "train",
                    "split_block_count": 210,
                },
                "files_sha256": {
                    name: _sha(directory / name)
                    for name in payloads
                },
            }
            (directory / "run_summary.json").write_text(
                json.dumps(summary),
                encoding="utf-8",
            )


def test_freeze_ablation_train_is_complete_and_deterministic(tmp_path):
    evidence = tmp_path / "evidence"
    _build_evidence(evidence)

    out1 = tmp_path / "freeze1"
    out2 = tmp_path / "freeze2"
    first = freeze_ablation_train(evidence, out1, 35439908126)
    second = freeze_ablation_train(evidence, out2, 35439908126)

    assert first["records"] == 90
    assert first["ablation_train_root_sha256"] == second["ablation_train_root_sha256"]
    assert first["master_lock_sha256"] == second["master_lock_sha256"]
    assert (out1 / INDEX_NAME).read_bytes() == (out2 / INDEX_NAME).read_bytes()
    assert (out1 / LOCK_NAME).read_bytes() == (out2 / LOCK_NAME).read_bytes()
    assert (out1 / SHA_NAME).read_bytes() == (out2 / SHA_NAME).read_bytes()
