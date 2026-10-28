"""Fail-closed helpers for exposed TRAIN/VALIDATION engineering replay."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .contracts import ContractError, canonical, digest, file_hash, finite_array

RAW_COLUMNS = {"block_id", "bin_utc", "load_kw_frozen", "load_kw_raw", "pv_kw_frozen",
               "pv_kw_raw", "base_kw_frozen", "base_kw_raw"}


def verified_controller_profile(frame, *, expected_ticks=720, parity_atol_kw=1e-10):
    """Use existing raw reconstruction; never reaggregate or fill missing bins.

    A full day has exactly 720 unique, ordered, timezone-aware 2-minute bins.
    Values must be finite and agree with frozen load/PV/base, including the
    load-minus-PV identity. The returned neutral peak flags match the adapter.
    """
    if not isinstance(frame, pd.DataFrame) or set(frame) != RAW_COLUMNS:
        raise ContractError("unexpected raw-to-controller schema")
    if (isinstance(expected_ticks, bool) or not isinstance(expected_ticks, int)
            or expected_ticks < 1 or len(frame) != expected_ticks):
        raise ContractError("incorrect full-day tick count")
    if frame.block_id.isna().any() or frame.block_id.nunique() != 1:
        raise ContractError("one nonmissing block identity required")
    if (not isinstance(parity_atol_kw, (int, float)) or isinstance(parity_atol_kw, bool)
            or not math.isfinite(parity_atol_kw) or parity_atol_kw < 0):
        raise ContractError("finite nonnegative parity tolerance required")
    try:
        times = pd.DatetimeIndex(pd.to_datetime(frame.bin_utc, errors="raise"))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractError("invalid replay timestamps") from exc
    if (times.tz is None or times.hasnans or times.has_duplicates
            or not times.is_monotonic_increasing):
        raise ContractError("aware unique ordered replay timestamps required")
    times = times.tz_convert("UTC")
    if len(times) > 1 and not np.all(np.diff(times.as_unit("ns").asi8) == 120_000_000_000):
        raise ContractError("missing or irregular two-minute measurement")
    for name in RAW_COLUMNS - {"block_id", "bin_utc"}:
        finite_array(frame[name].to_numpy(), name, ndim=1)
    deltas = {}
    for name in ("load_kw", "pv_kw", "base_kw"):
        raw, frozen = frame[name + "_raw"].to_numpy(), frame[name + "_frozen"].to_numpy()
        delta = float(np.abs(raw - frozen).max())
        if delta > parity_atol_kw:
            raise ContractError("raw/frozen value mismatch: " + name)
        deltas[name + "_max_abs_raw_frozen_kw"] = delta
    if not np.allclose(frame.load_kw_raw - frame.pv_kw_raw, frame.base_kw_raw,
                       atol=parity_atol_kw, rtol=0):
        raise ContractError("raw load-minus-PV identity mismatch")
    profile = pd.DataFrame({"timestamp": times, "base_kw": frame.base_kw_raw.to_numpy(dtype=float),
                            "peak_flag": np.zeros(len(frame), dtype=np.int64)})
    deltas.update({"n_ticks": len(profile), "peak_flag_policy": "NEUTRAL_ZERO_AS_HISTORICAL_ADAPTER",
                   "input_tensor_parity": "RAW_TO_FROZEN_BASE_VERIFIED_ORIGINAL_CONTROLLER_TENSOR_UNAVAILABLE",
                   "profile_sha256": trajectory_hash(profile, ("timestamp", "base_kw", "peak_flag"))})
    return profile, deltas


def trajectory_hash(frame, columns=("timestamp", "base_kw", "cmd_kw", "grid_kw", "soc", "soc_next",
                                     "p_imp_cap", "p_exp_cap", "mode")):
    """Deterministic trajectory identity excluding nondeterministic CPU timing."""
    h = hashlib.sha256()
    for name in columns:
        h.update(name.encode() + b"\0")
        if name == "timestamp":
            h.update(pd.DatetimeIndex(frame[name]).as_unit("ns").asi8.astype("<i8").tobytes())
        elif name == "mode":
            h.update(canonical(frame[name].astype(str).tolist()))
        else:
            h.update(frame[name].to_numpy(dtype="<f8").tobytes())
    return h.hexdigest()


class ReplayCheckpoints:
    """Atomic, hash-bound, fixed-size batches; no silent changed-input resume."""

    def __init__(self, root, binding):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity = digest(binding)
        self.path = self.root / "CHECKPOINT_STATE.json"
        self.state = {"schema_version": 1, "binding_sha256": self.identity,
                      "binding": binding, "completed_batches": {}}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if self.state.get("binding_sha256") != self.identity:
                raise ContractError("checkpoint source/input/config binding changed")

    def read_batch(self, name):
        receipt = self.state["completed_batches"].get(name)
        if receipt is None:
            return None
        path = self.root / receipt["file"]
        if not path.is_file() or file_hash(path) != receipt["sha256"]:
            raise ContractError("checkpoint batch missing or altered")
        for item in receipt.get("artifacts", []):
            artifact = self.root / item["file"]
            if not artifact.is_file() or file_hash(artifact) != item["sha256"]:
                raise ContractError("checkpoint trajectory artifact missing or altered")
        rows = json.loads(path.read_text(encoding="utf-8"))
        if len(rows) != receipt["rows"]:
            raise ContractError("checkpoint row count changed")
        return rows

    def write_batch(self, name, rows, *, artifacts=()):
        if name in self.state["completed_batches"]:
            raise ContractError("refuse to overwrite completed checkpoint")
        path = self.root / (name + ".json")
        pending = self.root / (name + ".pending")
        pending.write_bytes(canonical(rows))
        os.replace(pending, path)
        self.state["completed_batches"][name] = {
            "file": path.name, "rows": len(rows), "sha256": file_hash(path),
            "artifacts": [{"file": Path(p).name, "sha256": file_hash(p)} for p in artifacts]}
        pending = self.root / "CHECKPOINT_STATE.pending"
        pending.write_bytes(canonical(self.state))
        os.replace(pending, self.path)
