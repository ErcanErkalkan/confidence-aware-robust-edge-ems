from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd

from crmt_edge_ems.parameter_space import PARAM_NAMES
from crmt_edge_ems.protocol import (
    CRMT_HYPERPARAMETERS,
    METHOD_IDS,
    PROTOCOL_VERSION,
)
from crmt_edge_ems.replay import MultiSiteReplayEvaluator, ReplayBlock
from crmt_edge_ems.risk import RiskConfig, aggregate_objectives
from crmt_edge_ems.site_model import build_primary_opencem_site
from data_adapters.opsd_household import (
    OPSD_OOD_HOUSEHOLDS,
    native_net_profile,
    replay_profile_2min,
)
from opencem_internal_test import load_locked_selection
from opencem_sensitivity_suite import verify_primary_internal_test
from opsd_ood_acquire import verify_locked_identity
from opsd_ood_inventory import required_usecols
from opsd_ood_replay_inventory import (
    build_full_replay_inventory,
    full_regular_days,
)


TARGET_SITE_IDS = (1, 2)
EXPECTED_STRATA = len(OPSD_OOD_HOUSEHOLDS) * len(TARGET_SITE_IDS)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _risk() -> RiskConfig:
    return RiskConfig(
        q=float(CRMT_HYPERPARAMETERS["risk_q"]),
        tail_weight=float(CRMT_HYPERPARAMETERS["tail_weight"]),
    )


def _sites():
    return {
        1: build_primary_opencem_site(1),
        2: build_primary_opencem_site(2),
    }


def load_locked_opsd_frame(
    zip_path: Path,
    *,
    artifact_lock: dict,
) -> tuple[pd.DataFrame, dict]:
    observed = verify_locked_identity(zip_path, artifact_lock)
    member = observed["resolved_members"][
        "household_data_1min_singleindex.csv"
    ]
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(member) as fh:
            frame = pd.read_csv(
                fh,
                usecols=required_usecols(),
                low_memory=False,
            )
    return frame, observed


def build_locked_ood_blocks(
    frame: pd.DataFrame,
    *,
    base_inventory_lock: dict,
    full_replay_lock: dict,
) -> tuple[list[ReplayBlock], pd.DataFrame, dict]:
    """Regenerate the frozen full-day inventory and construct two-site OOD blocks."""
    manifest, inv_summary = build_full_replay_inventory(
        frame,
        base_inventory_lock=base_inventory_lock,
    )
    if int(len(manifest)) != int(full_replay_lock["manifest_rows"]):
        raise RuntimeError("OPSD full-regular inventory row-count mismatch")
    if inv_summary["manifest_sha256"] != str(
        full_replay_lock["manifest_sha256"]
    ):
        raise RuntimeError("OPSD full-regular inventory SHA-256 mismatch")
    if int(full_replay_lock["expected_bins_per_day"]) != 720:
        raise RuntimeError("unexpected OPSD full-day bin-count lock")

    memberships = {
        household: set(
            manifest.loc[
                manifest["household"] == household, "utc_date"
            ].astype(str)
        )
        for household in OPSD_OOD_HOUSEHOLDS
    }

    blocks: list[ReplayBlock] = []
    meta_rows = []
    for household in OPSD_OOD_HOUSEHOLDS:
        native = native_net_profile(frame, household)
        replay = replay_profile_2min(native)
        days = full_regular_days(replay, household=household)
        if set(days) != memberships[household]:
            raise RuntimeError(
                f"reconstructed OPSD membership drift for {household}"
            )

        for date in sorted(days):
            profile = days[date][
                [
                    "timestamp",
                    "load_kw",
                    "pv_kw",
                    "wind_kw",
                    "base_kw",
                    "peak_flag",
                ]
            ].copy()
            if len(profile) != 720:
                raise RuntimeError("OPSD OOD block is not a full 720-bin day")
            for site_id in TARGET_SITE_IDS:
                block_id = (
                    f"opsd:{household}:{date}:site{site_id}"
                )
                blocks.append(
                    ReplayBlock(
                        block_id=block_id,
                        profile=profile,
                        source="OPSD Household Data 2020-04-15",
                        split="external_ood",
                        site_id=site_id,
                    )
                )
                meta_rows.append(
                    {
                        "block_id": block_id,
                        "household": household,
                        "utc_date": date,
                        "target_site_id": int(site_id),
                    }
                )

    meta = pd.DataFrame(meta_rows)
    expected = int(full_replay_lock["manifest_rows"]) * len(
        TARGET_SITE_IDS
    )
    if len(blocks) != expected or len(meta) != expected:
        raise RuntimeError(
            f"OPSD OOD block count mismatch: {len(blocks)} != {expected}"
        )
    if meta.duplicated(["block_id"]).any():
        raise RuntimeError("duplicate OPSD OOD block IDs")

    context = {
        "package_sha256": str(full_replay_lock["package_sha256"]),
        "base_inventory_sha256": str(
            full_replay_lock["base_inventory_sha256"]
        ),
        "full_replay_manifest_sha256": str(
            full_replay_lock["manifest_sha256"]
        ),
        "full_replay_manifest_rows": int(
            full_replay_lock["manifest_rows"]
        ),
        "target_site_ids": list(TARGET_SITE_IDS),
        "ood_block_count": int(len(blocks)),
        "strata": [
            f"{h}|site{s}"
            for h in OPSD_OOD_HOUSEHOLDS
            for s in TARGET_SITE_IDS
        ],
    }
    return blocks, meta, context


def stratified_risk_summaries(
    metrics: pd.DataFrame,
    *,
    risk: RiskConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return stratum, equal-stratum macro, and pooled risk summaries."""
    risk = risk or _risk()
    required = {
        "method",
        "candidate_id",
        "household",
        "target_site_id",
        *risk.objectives,
    }
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise KeyError(f"OOD metrics missing columns: {missing}")

    stratum_rows = []
    for (method, cid, household, site_id), g in metrics.groupby(
        ["method", "candidate_id", "household", "target_site_id"],
        sort=True,
    ):
        agg = aggregate_objectives(g, risk)
        stratum_rows.append(
            {
                "method": str(method),
                "candidate_id": str(cid),
                "household": str(household),
                "target_site_id": int(site_id),
                "n_blocks": int(len(g)),
                **{k: float(v) for k, v in agg.items()},
            }
        )
    strata = pd.DataFrame(stratum_rows)

    macro_rows = []
    pooled_rows = []
    for (method, cid), g in metrics.groupby(
        ["method", "candidate_id"], sort=True
    ):
        s = strata[
            (strata["method"] == method)
            & (strata["candidate_id"] == cid)
        ]
        if len(s) != EXPECTED_STRATA:
            raise RuntimeError(
                f"{method}/{cid} has {len(s)} OOD strata; "
                f"expected {EXPECTED_STRATA}"
            )
        macro_rows.append(
            {
                "method": str(method),
                "candidate_id": str(cid),
                "n_strata": EXPECTED_STRATA,
                "macro_weighting": "equal_household_x_target_site",
                **{
                    objective: float(s[objective].mean())
                    for objective in risk.objectives
                },
            }
        )
        pooled = aggregate_objectives(g, risk)
        pooled_rows.append(
            {
                "method": str(method),
                "candidate_id": str(cid),
                "n_blocks": int(len(g)),
                **{k: float(v) for k, v in pooled.items()},
            }
        )

    macro = pd.DataFrame(macro_rows)
    pooled = pd.DataFrame(pooled_rows)
    return strata, macro, pooled


def execute_ood_on_blocks(
    blocks: list[ReplayBlock],
    block_meta: pd.DataFrame,
    *,
    context: dict,
    selection_dir: Path,
    primary_internal_dir: Path,
    expected_opencem_manifest_sha: str,
    output_dir: Path,
) -> dict:
    selected, selection_lock = load_locked_selection(
        selection_dir,
        expected_manifest_sha256=expected_opencem_manifest_sha,
    )
    primary_internal = verify_primary_internal_test(
        primary_internal_dir,
        selection_dir=selection_dir,
        expected_manifest_sha256=expected_opencem_manifest_sha,
    )
    if int(primary_internal["seed"]) != int(selection_lock["seed"]):
        raise RuntimeError("primary internal-test and selection seed mismatch")
    if set(selected["method"]) != set(METHOD_IDS):
        raise RuntimeError("OOD selection method registry mismatch")

    evaluator = MultiSiteReplayEvaluator(
        _sites(), method_id="EXTERNAL_OOD_OPSD"
    )
    parts = []
    for row in selected.itertuples(index=False):
        params = {
            name: float(getattr(row, name))
            for name in PARAM_NAMES
        }
        result = evaluator.evaluate(
            params,
            blocks,
            candidate_id=f"{row.method}:{row.candidate_id}",
        )
        result.insert(0, "candidate_id", str(row.candidate_id))
        result.insert(0, "method", str(row.method))
        result = result.merge(
            block_meta,
            on="block_id",
            how="left",
            validate="one_to_one",
        )
        if result[
            ["household", "utc_date", "target_site_id"]
        ].isna().any().any():
            raise RuntimeError("OOD block metadata merge is incomplete")
        parts.append(result)

    metrics = pd.concat(parts, ignore_index=True)
    strata, macro, pooled = stratified_risk_summaries(
        metrics, risk=_risk()
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    frames = {
        "ood_block_metrics.csv": metrics,
        "ood_stratum_risk_summary.csv": strata,
        "ood_macro_risk_summary.csv": macro,
        "ood_pooled_risk_summary.csv": pooled,
    }
    for name, frame in frames.items():
        path = output_dir / name
        frame.to_csv(path, index=False, lineterminator="\n")
        files[name] = _sha256(path)

    summary = {
        "stage": "EXTERNAL_OOD_OPSD_FROZEN_SELECTION",
        "claim_boundary": (
            "External profile/domain-transfer evaluation of validation-frozen "
            "candidates under the two frozen OpenCEM site models. No retuning "
            "or hardware-equivalence claim."
        ),
        "protocol_version": PROTOCOL_VERSION,
        "seed": int(selection_lock["seed"]),
        "selection_lock_sha256": _sha256(
            selection_dir / "selection_lock.json"
        ),
        "selected_candidates_sha256": selection_lock[
            "selected_candidates_sha256"
        ],
        "primary_internal_test_summary_sha256": _sha256(
            primary_internal_dir / "internal_test_run_summary.json"
        ),
        "source_context": dict(context),
        "risk": {
            "q": float(_risk().q),
            "tail_weight": float(_risk().tail_weight),
            "objectives": list(_risk().objectives),
        },
        "primary_ood_summary": (
            "ood_macro_risk_summary.csv; six household×target-site "
            "strata receive equal weight"
        ),
        "secondary_ood_summary": "ood_pooled_risk_summary.csv",
        "files_sha256": files,
    }
    path = output_dir / "ood_run_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    p = argparse.ArgumentParser(
        description="Run locked-selection OPSD external OOD evaluation"
    )
    p.add_argument("--zip", dest="zip_path", type=Path, required=True)
    p.add_argument("--artifact-lock-json", type=Path, required=True)
    p.add_argument("--base-inventory-lock-json", type=Path, required=True)
    p.add_argument("--full-replay-lock-json", type=Path, required=True)
    p.add_argument("--opencem-block-lock-json", type=Path, required=True)
    p.add_argument("--selection-dir", type=Path, required=True)
    p.add_argument("--primary-internal-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()

    artifact_lock = json.loads(
        args.artifact_lock_json.read_text(encoding="utf-8")
    )
    base_lock = json.loads(
        args.base_inventory_lock_json.read_text(encoding="utf-8")
    )
    full_lock = json.loads(
        args.full_replay_lock_json.read_text(encoding="utf-8")
    )
    opencem_lock = json.loads(
        args.opencem_block_lock_json.read_text(encoding="utf-8")
    )

    frame, observed = load_locked_opsd_frame(
        args.zip_path,
        artifact_lock=artifact_lock,
    )
    if observed["sha256"] != str(full_lock["package_sha256"]):
        raise RuntimeError("OPSD artifact differs from full-replay lock")
    blocks, meta, context = build_locked_ood_blocks(
        frame,
        base_inventory_lock=base_lock,
        full_replay_lock=full_lock,
    )
    summary = execute_ood_on_blocks(
        blocks,
        meta,
        context=context,
        selection_dir=args.selection_dir,
        primary_internal_dir=args.primary_internal_dir,
        expected_opencem_manifest_sha=str(
            opencem_lock["canonical_csv_sha256"]
        ),
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
