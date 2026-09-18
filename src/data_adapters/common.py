from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
from urllib.request import urlopen, Request

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DownloadRecord:
    url: str
    sha256: str
    size_bytes: int
    output_path: str


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_freeze(url: str, output: str | Path, *, allow_mutable_url: bool = False, timeout: int = 120) -> DownloadRecord:
    """Download a dataset artifact and return a content hash.

    By default this refuses obvious mutable GitHub branch URLs such as /main/ or
    /master/. Confirmatory datasets should use immutable release/commit URLs or
    a separately archived file whose hash is frozen in the manifest.
    """
    if not allow_mutable_url and ("/main/" in url or "/master/" in url):
        raise ValueError("Mutable branch URL refused; freeze an immutable commit/release URL first")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "CRMT-reproducibility/1.0"})
    with urlopen(req, timeout=timeout) as r, output.open("wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return DownloadRecord(url=url, sha256=sha256_file(output), size_bytes=output.stat().st_size, output_path=str(output))


def write_provenance(record: DownloadRecord, path: str | Path, *, extra: dict | None = None) -> None:
    payload = {**record.__dict__, **(extra or {})}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def canonical_profile(timestamp, load_kw, pv_kw, *, wind_kw=None, peak_flag=None) -> pd.DataFrame:
    ts = pd.to_datetime(timestamp, utc=True)
    load = np.asarray(load_kw, dtype=float)
    pv = np.asarray(pv_kw, dtype=float)
    wind = np.zeros_like(load) if wind_kw is None else np.asarray(wind_kw, dtype=float)
    if not (len(ts) == len(load) == len(pv) == len(wind)):
        raise ValueError("timestamp/load/pv/wind lengths must match")
    base = load - pv - wind
    if peak_flag is None:
        peak = np.zeros(len(load), dtype=int)
    else:
        peak = np.asarray(peak_flag, dtype=int)
        if len(peak) != len(load):
            raise ValueError("peak_flag length must match")
    return pd.DataFrame({
        "timestamp": ts,
        "load_kw": load,
        "pv_kw": pv,
        "wind_kw": wind,
        "base_kw": base,
        "peak_flag": peak,
    })
