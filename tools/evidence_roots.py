from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ABLATION_IDS = ("NO_CVAR", "NO_CONFIDENCE", "NO_ADAPTIVE")
SEEDS = tuple(range(1001, 1031))
ABLATION_CONTROLLER_BLOCK_BUDGET = 12600
ABLATION_TRAIN_MANIFEST_SHA256 = "3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1"
ABLATION_TRAIN_BLOCK_COUNT = 210
ABLATION_TRAIN_GIT_SHA = "128c6d3be06d9efd7921f903065bc727ac1d7440"
ABLATION_REQUIRED_HASHED_FILES = ("candidate_metrics.csv", "optimizer_front.csv", "ledger.csv")
SENSITIVITY_VARIANT_IDS = (
    "ETA_LOW_090",
    "ETA_IDEAL_100",
    "SOC_CONSERVATIVE_15_95",
    "RAMP_HALF",
    "RAMP_QUARTER",
    "TEMPORAL_FLOOR",
)
SENSITIVITY_INTERNAL_BLOCK_COUNT = 78
SENSITIVITY_METHOD_COUNT = 5
SENSITIVITY_EXPECTED_BLOCK_ROWS = len(SENSITIVITY_VARIANT_IDS) * SENSITIVITY_METHOD_COUNT * SENSITIVITY_INTERNAL_BLOCK_COUNT
SENSITIVITY_EXPECTED_RISK_ROWS = len(SENSITIVITY_VARIANT_IDS) * SENSITIVITY_METHOD_COUNT
SENSITIVITY_MANIFEST_SHA256 = ABLATION_TRAIN_MANIFEST_SHA256
SENSITIVITY_REQUIRED_HASHED_FILES = ("sensitivity_block_metrics.csv", "sensitivity_risk_summary.csv")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_lines(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_unique_dir(root: Path, name: str, required: tuple[str, ...]) -> Path:
    direct = root / name
    if direct.is_dir() and all((direct / item).is_file() for item in required):
        return direct
    matches = sorted(
        p
        for p in root.rglob(name)
        if p.is_dir() and all((p / item).is_file() for item in required)
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one evidence directory {name!r}, found {len(matches)}"
        )
    return matches[0]


def _verify_files_sha256(directory: Path, mapping: dict) -> list[tuple[str, str]]:
    if not isinstance(mapping, dict) or not mapping:
        raise RuntimeError(f"missing files_sha256 in {directory}")
    verified: list[tuple[str, str]] = []
    for name, expected in sorted(mapping.items()):
        path = directory / str(name)
        if not path.is_file():
            raise FileNotFoundError(f"missing evidence file: {path}")
        observed = _sha256(path)
        if observed != str(expected):
            raise RuntimeError(
                f"hash mismatch for {path}: observed={observed} expected={expected}"
            )
        verified.append((str(name), observed))
    return verified


def validation_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for seed in SEEDS:
        directory = _resolve_unique_dir(
            root,
            f"validation_selection_seed{seed}",
            ("selection_lock.json", "selected_candidates.csv"),
        )
        lock_path = directory / "selection_lock.json"
        selected_path = directory / "selected_candidates.csv"
        lock = _load_json(lock_path)
        if lock.get("stage") != "VALIDATION_SELECTION_LOCK":
            raise RuntimeError(f"validation stage mismatch for seed {seed}")
        if int(lock.get("seed")) != seed:
            raise RuntimeError(f"validation seed mismatch for seed {seed}")
        lock_sha = _sha256(lock_path)
        selected_sha = _sha256(selected_path)
        if lock.get("selected_candidates_sha256") != selected_sha:
            raise RuntimeError(f"selected-candidate hash mismatch for seed {seed}")
        files = lock.get("files_sha256")
        if isinstance(files, dict) and files:
            _verify_files_sha256(directory, files)
        lines.append(f"{seed}|{lock_sha}|{selected_sha}")
    return _hash_lines(lines), len(lines)


def internal_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for seed in SEEDS:
        directory = _resolve_unique_dir(
            root,
            f"internal_test_seed{seed}",
            (
                "internal_test_run_summary.json",
                "internal_test_risk_summary.csv",
                "internal_test_block_metrics.csv",
            ),
        )
        summary_path = directory / "internal_test_run_summary.json"
        risk_path = directory / "internal_test_risk_summary.csv"
        block_path = directory / "internal_test_block_metrics.csv"
        summary = _load_json(summary_path)
        if summary.get("stage") != "ONE_SHOT_INTERNAL_TEST":
            raise RuntimeError(f"internal-test stage mismatch for seed {seed}")
        if int(summary.get("seed")) != seed:
            raise RuntimeError(f"internal-test seed mismatch for seed {seed}")
        summary_sha = _sha256(summary_path)
        risk_sha = _sha256(risk_path)
        block_sha = _sha256(block_path)
        files = summary.get("files_sha256", {})
        if files.get("internal_test_risk_summary.csv") != risk_sha:
            raise RuntimeError(f"internal risk-summary hash mismatch for seed {seed}")
        if files.get("internal_test_block_metrics.csv") != block_sha:
            raise RuntimeError(f"internal block-metrics hash mismatch for seed {seed}")
        lines.append(
            "|".join(
                [
                    str(seed),
                    str(summary.get("selection_lock_sha256")),
                    str(summary.get("selected_candidates_sha256")),
                    summary_sha,
                    risk_sha,
                    block_sha,
                ]
            )
        )
    return _hash_lines(lines), len(lines)


def ablation_train_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for ablation in ABLATION_IDS:
        for seed in SEEDS:
            directory = _resolve_unique_dir(
                root,
                f"{ablation}_seed{seed}",
                ("run_summary.json", "optimizer_front.csv"),
            )
            summary_path = directory / "run_summary.json"
            summary = _load_json(summary_path)
            if summary.get("stage") != "CRMT_ABLATION_TRAIN_ONLY":
                raise RuntimeError(f"ablation TRAIN stage mismatch for {ablation}/{seed}")
            if str(summary.get("ablation_id")) != ablation:
                raise RuntimeError(f"ablation TRAIN ID mismatch for {ablation}/{seed}")
            if int(summary.get("seed")) != seed:
                raise RuntimeError(f"ablation TRAIN seed mismatch for {ablation}/{seed}")
            if int(summary.get("controller_block_budget")) != ABLATION_CONTROLLER_BLOCK_BUDGET:
                raise RuntimeError(f"ablation TRAIN budget mismatch for {ablation}/{seed}")
            if int(summary.get("ledger_used")) != ABLATION_CONTROLLER_BLOCK_BUDGET:
                raise RuntimeError(f"ablation TRAIN ledger mismatch for {ablation}/{seed}")
            if str(summary.get("git_sha")) != ABLATION_TRAIN_GIT_SHA:
                raise RuntimeError(f"ablation TRAIN git SHA mismatch for {ablation}/{seed}")
            data_context = summary.get("data_context", {})
            if data_context.get("manifest_sha256") != ABLATION_TRAIN_MANIFEST_SHA256:
                raise RuntimeError(f"ablation TRAIN manifest mismatch for {ablation}/{seed}")
            if data_context.get("split") != "train":
                raise RuntimeError(f"ablation TRAIN split mismatch for {ablation}/{seed}")
            if int(data_context.get("split_block_count")) != ABLATION_TRAIN_BLOCK_COUNT:
                raise RuntimeError(f"ablation TRAIN block-count mismatch for {ablation}/{seed}")
            files_sha256 = summary.get("files_sha256", {})
            missing_hashes = [name for name in ABLATION_REQUIRED_HASHED_FILES if name not in files_sha256]
            if missing_hashes:
                raise RuntimeError(
                    f"ablation TRAIN missing required file hashes for {ablation}/{seed}: {missing_hashes}"
                )
            verified = _verify_files_sha256(directory, files_sha256)
            line = [ablation, str(seed), _sha256(summary_path)]
            line.extend(f"{name}:{sha}" for name, sha in verified)
            lines.append("|".join(line))
    return _hash_lines(lines), len(lines)


def ablation_validation_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for ablation in ABLATION_IDS:
        for seed in SEEDS:
            directory = _resolve_unique_dir(
                root,
                f"{ablation}_validation_seed{seed}",
                ("ablation_selection_lock.json", "selected_ablation_candidate.csv"),
            )
            lock_path = directory / "ablation_selection_lock.json"
            selected_path = directory / "selected_ablation_candidate.csv"
            lock = _load_json(lock_path)
            if lock.get("stage") != "CRMT_ABLATION_VALIDATION_SELECTION_LOCK":
                raise RuntimeError(f"ablation validation stage mismatch for {ablation}/{seed}")
            if str(lock.get("ablation_id")) != ablation:
                raise RuntimeError(f"ablation validation ID mismatch for {ablation}/{seed}")
            if int(lock.get("seed")) != seed:
                raise RuntimeError(f"ablation validation seed mismatch for {ablation}/{seed}")
            selected_sha = _sha256(selected_path)
            if lock.get("selected_ablation_candidate_sha256") != selected_sha:
                raise RuntimeError(f"ablation selected-candidate hash mismatch for {ablation}/{seed}")
            files = lock.get("files_sha256")
            if isinstance(files, dict) and files:
                _verify_files_sha256(directory, files)
            lines.append(f"{ablation}|{seed}|{_sha256(lock_path)}|{selected_sha}")
    return _hash_lines(lines), len(lines)


def ablation_internal_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for ablation in ABLATION_IDS:
        for seed in SEEDS:
            directory = _resolve_unique_dir(
                root,
                f"{ablation}_internal_seed{seed}",
                (
                    "ablation_internal_run_summary.json",
                    "ablation_internal_block_metrics.csv",
                    "ablation_internal_risk_summary.csv",
                ),
            )
            summary_path = directory / "ablation_internal_run_summary.json"
            summary = _load_json(summary_path)
            if summary.get("stage") != "CRMT_ABLATION_ONE_SHOT_INTERNAL_TEST":
                raise RuntimeError(f"ablation internal stage mismatch for {ablation}/{seed}")
            if str(summary.get("ablation_id")) != ablation:
                raise RuntimeError(f"ablation internal ID mismatch for {ablation}/{seed}")
            if int(summary.get("seed")) != seed:
                raise RuntimeError(f"ablation internal seed mismatch for {ablation}/{seed}")
            verified = _verify_files_sha256(directory, summary.get("files_sha256", {}))
            line = [
                ablation,
                str(seed),
                str(summary.get("ablation_selection_lock_sha256")),
                str(summary.get("selected_ablation_candidate_sha256")),
                _sha256(summary_path),
            ]
            line.extend(f"{name}:{sha}" for name, sha in verified)
            lines.append("|".join(line))
    return _hash_lines(lines), len(lines)


def sensitivity_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for seed in SEEDS:
        directory = _resolve_unique_dir(
            root,
            f"sensitivity_seed{seed}",
            (
                "sensitivity_run_summary.json",
                "sensitivity_block_metrics.csv",
                "sensitivity_risk_summary.csv",
            ),
        )
        summary_path = directory / "sensitivity_run_summary.json"
        summary = _load_json(summary_path)
        if summary.get("stage") != "PREDECLARED_SITE_TEMPORAL_SENSITIVITY":
            raise RuntimeError(f"sensitivity stage mismatch for seed {seed}")
        if int(summary.get("seed")) != seed:
            raise RuntimeError(f"sensitivity seed mismatch for seed {seed}")
        if tuple(summary.get("variant_ids", ())) != SENSITIVITY_VARIANT_IDS:
            raise RuntimeError(f"sensitivity variant set/order mismatch for seed {seed}")
        data_context = summary.get("data_context", {})
        if data_context.get("manifest_sha256") != SENSITIVITY_MANIFEST_SHA256:
            raise RuntimeError(f"sensitivity manifest mismatch for seed {seed}")
        if data_context.get("split") != "internal_test":
            raise RuntimeError(f"sensitivity split mismatch for seed {seed}")
        if int(data_context.get("split_block_count")) != SENSITIVITY_INTERNAL_BLOCK_COUNT:
            raise RuntimeError(f"sensitivity block-count mismatch for seed {seed}")
        if summary.get("primary_internal_test_stage") != "ONE_SHOT_INTERNAL_TEST":
            raise RuntimeError(f"sensitivity primary-internal stage mismatch for seed {seed}")
        if not summary.get("selection_lock_sha256"):
            raise RuntimeError(f"sensitivity selection-lock hash missing for seed {seed}")
        if not summary.get("selected_candidates_sha256"):
            raise RuntimeError(f"sensitivity selected-candidates hash missing for seed {seed}")
        if not summary.get("primary_internal_test_summary_sha256"):
            raise RuntimeError(f"sensitivity primary-internal summary hash missing for seed {seed}")
        files_sha256 = summary.get("files_sha256", {})
        missing_hashes = [
            name for name in SENSITIVITY_REQUIRED_HASHED_FILES
            if name not in files_sha256
        ]
        if missing_hashes:
            raise RuntimeError(
                f"sensitivity missing required file hashes for seed {seed}: {missing_hashes}"
            )
        verified = _verify_files_sha256(directory, files_sha256)
        for name, expected_rows in (
            ("sensitivity_block_metrics.csv", SENSITIVITY_EXPECTED_BLOCK_ROWS),
            ("sensitivity_risk_summary.csv", SENSITIVITY_EXPECTED_RISK_ROWS),
        ):
            with (directory / name).open(newline="", encoding="utf-8") as handle:
                observed_rows = sum(1 for _ in csv.reader(handle)) - 1
            if observed_rows != expected_rows:
                raise RuntimeError(
                    f"sensitivity row-count mismatch for seed {seed}/{name}: "
                    f"{observed_rows} != {expected_rows}"
                )
        line = [
            str(seed),
            str(summary.get("selection_lock_sha256")),
            str(summary.get("selected_candidates_sha256")),
            str(summary.get("primary_internal_test_summary_sha256")),
            _sha256(summary_path),
        ]
        line.extend(f"{name}:{sha}" for name, sha in verified)
        lines.append("|".join(line))
    return _hash_lines(lines), len(lines)


def ood_root(root: Path) -> tuple[str, int]:
    lines: list[str] = []
    for seed in SEEDS:
        directory = _resolve_unique_dir(
            root,
            f"opsd_ood_seed{seed}",
            ("ood_run_summary.json",),
        )
        summary_path = directory / "ood_run_summary.json"
        summary = _load_json(summary_path)
        if summary.get("stage") != "EXTERNAL_OOD_OPSD_FROZEN_SELECTION":
            raise RuntimeError(f"OOD stage mismatch for seed {seed}")
        if int(summary.get("seed")) != seed:
            raise RuntimeError(f"OOD seed mismatch for seed {seed}")
        verified = _verify_files_sha256(directory, summary.get("files_sha256", {}))
        line = [
            str(seed),
            str(summary.get("selection_lock_sha256")),
            str(summary.get("selected_candidates_sha256")),
            str(summary.get("primary_internal_test_summary_sha256")),
            _sha256(summary_path),
        ]
        line.extend(f"{name}:{sha}" for name, sha in verified)
        lines.append("|".join(line))
    return _hash_lines(lines), len(lines)


ROOT_BUILDERS = {
    "validation": validation_root,
    "internal": internal_root,
    "ablation_train": ablation_train_root,
    "ablation_validation": ablation_validation_root,
    "ablation_internal": ablation_internal_root,
    "sensitivity": sensitivity_root,
    "ood": ood_root,
}


def compute_evidence_root(stage: str, root: Path) -> dict:
    try:
        builder = ROOT_BUILDERS[stage]
    except KeyError as exc:
        raise ValueError(f"unsupported evidence-root stage: {stage}") from exc
    digest, records = builder(Path(root))
    return {
        "stage": stage,
        "root_sha256": digest,
        "records": int(records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute and optionally verify deterministic evidence roots"
    )
    parser.add_argument("--stage", required=True, choices=sorted(ROOT_BUILDERS))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--expected-root")
    args = parser.parse_args()

    result = compute_evidence_root(args.stage, args.root)
    if args.expected_root and result["root_sha256"] != args.expected_root:
        raise RuntimeError(
            f"{args.stage} evidence-root mismatch: "
            f"observed={result['root_sha256']} expected={args.expected_root}"
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
