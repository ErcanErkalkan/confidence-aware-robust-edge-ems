from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

DEFAULT_REPO = "OpenCEM-platform/opencem-dataset"
DEFAULT_URL_TEMPLATE = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"


@dataclass(frozen=True)
class ManifestRow:
    commit_sha: str
    tree_sha: str
    path: str
    git_blob_sha1: str
    size_bytes: int


@dataclass
class VerificationResult:
    path: str
    local_path: str
    size_bytes: int
    expected_size_bytes: int
    git_blob_sha1: str
    expected_git_blob_sha1: str
    sha256: str
    verified: bool
    source_url: str
    status: str


def git_blob_sha1(path: Path, chunk_size: int = 1024 * 1024) -> str:
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                ManifestRow(
                    commit_sha=r["commit_sha"],
                    tree_sha=r["tree_sha"],
                    path=r["path"],
                    git_blob_sha1=r["git_blob_sha1"].lower(),
                    size_bytes=int(r["size_bytes"]),
                )
            )
    if not rows:
        raise ValueError("Manifest is empty")
    commits = {r.commit_sha for r in rows}
    trees = {r.tree_sha for r in rows}
    if len(commits) != 1 or len(trees) != 1:
        raise ValueError("Manifest must contain exactly one commit and one tree")
    if len({r.path for r in rows}) != len(rows):
        raise ValueError("Manifest contains duplicate paths")
    return rows


def verify_file(path: Path, row: ManifestRow, source_url: str = "") -> VerificationResult:
    if not path.is_file():
        return VerificationResult(
            path=row.path, local_path=str(path), size_bytes=-1,
            expected_size_bytes=row.size_bytes, git_blob_sha1="",
            expected_git_blob_sha1=row.git_blob_sha1, sha256="", verified=False,
            source_url=source_url, status="MISSING",
        )
    size = path.stat().st_size
    blob = git_blob_sha1(path)
    sha256 = sha256_file(path)
    ok = size == row.size_bytes and blob == row.git_blob_sha1
    status = "VERIFIED" if ok else (
        "SIZE_MISMATCH" if size != row.size_bytes else "GIT_BLOB_SHA1_MISMATCH"
    )
    return VerificationResult(
        path=row.path, local_path=str(path), size_bytes=size,
        expected_size_bytes=row.size_bytes, git_blob_sha1=blob,
        expected_git_blob_sha1=row.git_blob_sha1, sha256=sha256,
        verified=ok, source_url=source_url, status=status,
    )


def _download_http(url: str, dest: Path, expected_size: int, timeout: int = 120) -> None:
    """Resumable HTTP(S) download to `dest` using a .part file.

    Resume is accepted only when the server returns HTTP 206. If it ignores the
    Range request and returns 200, the partial file is replaced from byte zero.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    start = part.stat().st_size if part.exists() else 0
    if start > expected_size:
        part.unlink()
        start = 0
    if start == expected_size:
        os.replace(part, dest)
        return

    headers = {"User-Agent": "crmt-opencem-ingest/1.0"}
    if start:
        headers["Range"] = f"bytes={start}-"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", None) or resp.getcode()
        mode = "ab" if start and status == 206 else "wb"
        if start and status != 206:
            start = 0
        with part.open(mode) as out:
            shutil.copyfileobj(resp, out, length=1024 * 1024)
    if part.stat().st_size != expected_size:
        raise IOError(
            f"Downloaded size mismatch for {url}: {part.stat().st_size} != {expected_size}"
        )
    os.replace(part, dest)


def download_one(
    row: ManifestRow,
    raw_root: Path,
    *,
    repo: str = DEFAULT_REPO,
    url_template: str = DEFAULT_URL_TEMPLATE,
    retries: int = 3,
    timeout: int = 120,
) -> VerificationResult:
    dest = raw_root / row.path
    url = url_template.format(repo=repo, commit=row.commit_sha, path=row.path)
    existing = verify_file(dest, row, url)
    if existing.verified:
        existing.status = "VERIFIED_EXISTING"
        return existing
    if dest.exists():
        bad = dest.with_suffix(dest.suffix + ".invalid")
        if bad.exists():
            bad.unlink()
        os.replace(dest, bad)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            _download_http(url, dest, row.size_bytes, timeout=timeout)
            result = verify_file(dest, row, url)
            if not result.verified:
                raise IOError(f"Post-download verification failed: {result.status}")
            result.status = "DOWNLOADED_AND_VERIFIED"
            return result
        except Exception as exc:  # network and verification failures are fail-closed
            last_error = exc
            if dest.exists():
                dest.unlink()
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"Failed after {retries} attempts: {row.path}: {last_error}")


def write_results(results: Iterable[VerificationResult], out_csv: Path, out_json: Path) -> None:
    rows = [asdict(r) for r in results]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(VerificationResult.__dataclass_fields__.keys())
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    payload = {
        "files": len(rows),
        "verified": sum(bool(r["verified"]) for r in rows),
        "all_verified": bool(rows) and all(bool(r["verified"]) for r in rows),
        "total_verified_bytes": sum(r["size_bytes"] for r in rows if r["verified"]),
        "results": rows,
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Download and verify frozen OpenCEM partitions")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--result-csv", type=Path, required=True)
    p.add_argument("--result-json", type=Path, required=True)
    p.add_argument("--repo", default=DEFAULT_REPO)
    p.add_argument("--url-template", default=DEFAULT_URL_TEMPLATE)
    p.add_argument("--verify-only", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="0 = all manifest rows")
    args = p.parse_args()

    rows = load_manifest(args.manifest)
    if args.limit:
        rows = rows[: args.limit]
    results: list[VerificationResult] = []
    for i, row in enumerate(rows, 1):
        url = args.url_template.format(repo=args.repo, commit=row.commit_sha, path=row.path)
        if args.verify_only:
            result = verify_file(args.raw_root / row.path, row, url)
        else:
            result = download_one(
                row, args.raw_root, repo=args.repo, url_template=args.url_template
            )
        print(f"[{i}/{len(rows)}] {row.path}: {result.status}", flush=True)
        results.append(result)
    write_results(results, args.result_csv, args.result_json)
    return 0 if all(r.verified for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
