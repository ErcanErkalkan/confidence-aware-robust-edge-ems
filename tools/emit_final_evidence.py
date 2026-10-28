"""Emit only shareable report files for connector-mediated readback.

This deliberately excludes raw observations, profiles, event receipts and private
configuration. The same files remain in the downloadable Actions artifact.
"""
import json
from pathlib import Path
for path in sorted(Path("reports/final").glob("*")):
    if path.is_file() and path.suffix in {".json",".csv",".md"}:
        print("CRMT_EVIDENCE_FILE "+json.dumps({"path":path.as_posix(),"content":path.read_text(encoding="utf-8")},ensure_ascii=True),flush=True)
for path in sorted(Path("reports/environment").glob("*")):
    if path.is_file() and path.name in {"pip-freeze.txt","platform.json","git-head.txt"}:
        print("CRMT_EVIDENCE_FILE "+json.dumps({"path":path.as_posix(),"content":path.read_text(encoding="utf-8")},ensure_ascii=True),flush=True)
