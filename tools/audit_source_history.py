"""Recheck frozen SHA references against all fetched Git path histories."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
from crmt_edge_ems.contracts import canonical, file_hash
def git(*args):return subprocess.check_output(["git",*args],stderr=subprocess.DEVNULL)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True,type=Path);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    ref=Path("config/audit/frozen_reference_20261027.json");reference=json.loads(ref.read_text(encoding="utf-8"));rows=[]
    for original in reference["records"]:
        path=original["path"];expected=original["expected"];row={"path":path,"expected_sha256":expected,
            "scope":"SOURCE_BYTES_ONLY_NOT_EXECUTION_IDENTITY","historical_execution_sha_resolved":False}
        current=Path(path)
        if not current.is_file():row["classification"]="MISSING_SOURCE";rows.append(row);continue
        raw=current.read_bytes();lf=raw.replace(b"\r\n",b"\n")
        row.update(current_sha256=sha(raw),current_lf_sha256=sha(lf))
        if sha(raw)==expected:row["classification"]="EXACT_MATCH"
        elif sha(lf)==expected:row["classification"]="LINE_ENDING_ONLY"
        else:
            commits=git("log","--all","--format=%H","--",path).decode().split()
            row["examined_path_commits"]=len(commits);found=None;examined=set()
            for commit in commits:
                try:blob=git("rev-parse",f"{commit}:{path}").decode().strip()
                except subprocess.CalledProcessError:continue
                if blob in examined:continue
                examined.add(blob);data=git("cat-file","blob",blob)
                if sha(data)==expected or sha(data.replace(b"\r\n",b"\n"))==expected:
                    found=(commit,blob,data);break
            row["examined_unique_blobs"]=len(examined)
            safe=path.replace("/","__")
            if found:
                commit,blob,data=found;row.update(classification="TRACEABLE_HISTORICAL_CHANGE",
                    matched_commit=commit,matched_git_blob=blob,
                    commit_timestamp=git("show","-s","--format=%cI",commit).decode().strip(),
                    production_timestamp_proven=False)
                diff="".join(difflib.unified_diff(data.decode("utf-8-sig").splitlines(True),
                    raw.decode("utf-8-sig").splitlines(True),fromfile=f"{commit}/{path}",tofile=f"current/{path}"))
                dest=a.out/(safe+".diff");dest.write_text(diff,encoding="utf-8")
                row["diff_path"]=dest.as_posix();row["diff_sha256"]=file_hash(dest)
            else:
                row["classification"]="UNEXPLAINED_CONTENT_CHANGE"
                row["diff_status"]="UNAVAILABLE: original expected-hash bytes absent from fetched Git histories; no fabricated diff."
                dest=a.out/(safe+".missing.json");dest.write_bytes(canonical(row))
                row["missing_source_receipt"]=dest.as_posix()
        rows.append(row)
    head=git("rev-parse","HEAD").decode().strip()
    report={"source_commit":head,"reference_path":str(ref),"reference_sha256":file_hash(ref),
        "fetched_history_shallow":git("rev-parse","--is-shallow-repository").decode().strip()=="true",
        "counts":{s:sum(r["classification"]==s for r in rows) for s in ("EXACT_MATCH","LINE_ENDING_ONLY",
            "TRACEABLE_HISTORICAL_CHANGE","UNEXPLAINED_CONTENT_CHANGE","MISSING_SOURCE")},
        "records":rows,"UNRECORDED_LOCAL_SHA":"PRESERVED_UNRESOLVED",
        "execution_identity":"BLOCKED_EXTERNAL: immutable original execution receipt needed",
        "historical_archive_bytes_rechecked_this_run":False}
    (a.out/"SOURCE_HISTORY_AUDIT.json").write_bytes(canonical(report))
if __name__=="__main__":main()
