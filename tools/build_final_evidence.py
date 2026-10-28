"""Portable, fail-closed engineering evidence reports; never authorizes science."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "CRMT-FINAL-ENGINEERING-EVIDENCE-v1"
REQUIRED = [
    "A01_A32_FINAL_TRACKER.csv", "A_Z_FINAL_ACCEPTANCE_AUDIT.md",
    "FINAL_STATUS.json", "BLOCKERS_EXTERNAL.json", "BLOCKERS_SCIENTIFIC.json",
    "SOURCE_INTEGRITY_REPORT.json", "TEST_SUMMARY.json", "CI_MATRIX.json",
    "DATA_LINEAGE_REPORT.json", "CALIBRATION_VALIDATION.json",
    "R19_DESIGN_REVIEW.md", "R19_EFFECT_FEASIBILITY.csv",
    "COMPUTE_FAIRNESS_REPORT.json", "SAFETY_VERIFICATION.json",
    "MANUSCRIPT_CLAIM_MATRIX.csv", "ARTIFACT_MANIFEST_SHA256.json",
    "GITHUB_DRIVE_SYNC_RECEIPT.json",
]
LABELS = [
    "Kaynak: sekiz açıklanamayan tarihsel fark", "ZIP ve manifest", "Durum indeksi",
    "Google Docs revision", "160 tarihsel kaynak", "Tarihsel eşli karşılaştırmalar",
    "Eksik özgün yürütme SHA", "R9 platform", "Strict risk",
    "Confidence kalibrasyonu", "İddia kapsamı", "R19 etki geometrisi",
    "K10 kapasite", "Normalizasyon ve Pareto", "Adaptive faktöriyel",
    "Tam hesaplama maliyeti", "Veri lineage", "Maruziyet ve sızıntı",
    "Güç ve bağımsız birim", "Güvenlik ve process", "Bağımsız ön kayıt",
    "Tam gün entegrasyonu", "Yetkili prospektif yürütme", "Dış fiziksel veri",
    "Lisans ve AI/cloud izni", "Bağımsız TEST", "Makale", "İddialar",
    "Ortam ve CI", "Arşiv sınıflaması", "İndeks bakımı", "Fiziksel iddialar",
]
ACCEPTANCE = [
    "Current source identity", "160 source artifacts", "Execution SHA exception",
    "Tests", "Lineage", "Paired F0/F1", "B10 semantics", "Deterministic selection",
    "Archive confidence calibration", "False removal vs undercoverage",
    "Adaptive contribution", "Full cost fairness", "Inference justified",
    "Power defensible", "Safety enforced", "Leakage prevented",
    "New external source accepted", "Externally preregistered",
    "New confirmatory AUDIT", "Independent operational TEST",
    "Manuscript supported claims", "A01–A32",
]
EXTERNAL = [
    ("E01", "Özgün seed1001/C1_F1_A1 yürütme SHA", "UNRECORDED_LOCAL_SHA; sonraki HEAD özgün yürütme kimliği olamaz."),
    ("E02", "Bağımsız ön kayıt ve otorite", "Bağımsız yetkili sicil, zamanında kilit ve gerçek receipt gereklidir."),
    ("E03", "Yeni veri ve fiziksel semantik", "Sağlayıcı ölçümü, SOC/kimya/güç/grid sözleşmesi ve tam lineage gereklidir."),
    ("E04", "Lisans ve AI/cloud işleme", "Veri hakları ile AI/cloud işleme izni ayrıca doğrulanmalıdır."),
    ("E05", "Maruziyet ve bağımsız TEST", "Yeni, uygun, görülmemiş veri ve bağımsız operasyonel TEST planı gereklidir."),
    ("E06", "Fiziksel güvenlik ve yayın", "Donanım/HIL/saha, yazar incelemesi ve açık yayın yetkisi mevcut yazılım kanıtından çıkmaz."),
]
SCIENTIFIC = [
    ("S01", "Arşiv-geneli kalibrasyon", "Sentetik geçiş bile bağımlılık varsayımlarını ve bağımsız doğrulamayı tamamlamaz."),
    ("S02", "Adaptive katkı", "Sentetik faktöriyel ayrıştırma bağımsız operasyonel fayda kanıtı değildir."),
    ("S03", "R19 etki ve güç", "N=256,K=10 için P>200 durumunda 0.05 etki geometrik olarak imkansızdır; P bilinmiyor."),
    ("S04", "Bağımsız birim ve güç", "Seed sayısı veri kümesi bağımsızlığının veya yeterli gücün yerine geçmez."),
    ("S05", "Batarya ömrü", "Rainflow yazılım düzeltmesi ve LFP model proxy fiziksel ömür doğrulaması değildir."),
    ("S06", "Tarihsel sürüm farkı", "Aktif kaynak hash doğrulaması sekiz tarihsel farkı veya eski yürütmeyi yeniden doğrulamaz."),
]
GROUPS = {
    "engineering": "reports/engineering",
    "calibration": "reports/calibration_v2",
    "factorial": "reports/strict_factorial",
    "compute": "reports/compute_full256",
}

def reject_constant(value):
    raise ValueError("non-finite JSON constant: " + value)

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject_constant)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout

def source_integrity(root):
    result = {"scope": "CURRENT_ACTIVE_TRACKED_FILES_ONLY_NOT_HISTORICAL_160_RECERTIFICATION",
              "excluded_prefixes": ["reports/", "outputs/", "artifacts/"],
              "records": [], "errors": [], "git_commit": None, "passed": False}
    try:
        result["git_commit"] = git(root, "rev-parse", "HEAD").decode().strip()
        tree = git(root, "ls-tree", "-rz", "--full-tree", "HEAD")
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            header, raw_path = entry.split(b"\t", 1)
            mode, kind, expected = header.decode().split()
            path = raw_path.decode("utf-8")
            if any(path.startswith(p) for p in result["excluded_prefixes"]):
                continue
            record = {"source_path": path, "git_blob_expected": expected, "sha256": None}
            target = root / path
            if kind != "blob" or mode == "120000" or not target.is_file():
                record["verification_result"] = "UNSUPPORTED_OR_MISSING"
            else:
                data = target.read_bytes()
                blob = lambda b: hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
                record["sha256"] = digest(data)
                record["bytes"] = len(data)
                record["git_blob_observed"] = blob(data)
                record["verification_result"] = ("EXACT_MATCH" if blob(data) == expected
                    else "NEWLINE_EQUIVALENT" if blob(data.replace(b"\r\n", b"\n")) == expected
                    else "CONTENT_DIFFERENCE")
            result["records"].append(record)
        result["passed"] = bool(result["records"]) and all(
            r["verification_result"] in {"EXACT_MATCH", "NEWLINE_EQUIVALENT"} for r in result["records"])
        result["counts"] = {key: sum(r["verification_result"] == key for r in result["records"])
                            for key in ("EXACT_MATCH", "NEWLINE_EQUIVALENT", "CONTENT_DIFFERENCE", "UNSUPPORTED_OR_MISSING")}
        result["untracked_and_status"] = git(root, "status", "--porcelain=v1", "--untracked-files=normal").decode("utf-8", "replace").splitlines()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        result["errors"].append(str(exc))
    return result

def parse_junit(path):
    result = {"source_path": str(path), "available": False, "passed": False,
              "tests": 0, "failures": 0, "errors": 0, "skipped": 0, "cases": []}
    if not Path(path).is_file():
        result["blocking_reason"] = "CURRENT_JUNIT_MISSING"
        return result
    result["sha256"] = file_sha(path)
    try:
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        if not cases:
            raise ValueError("JUnit contains no testcase records")
        for case in cases:
            state = "failed" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
            result["cases"].append({"name": case.get("name"), "class": case.get("classname"),
                                    "file": case.get("file"), "status": state})
        result["tests"] = len(cases)
        result["failures"] = sum(r["status"] == "failed" for r in result["cases"])
        result["errors"] = sum(r["status"] == "error" for r in result["cases"])
        result["skipped"] = sum(r["status"] == "skipped" for r in result["cases"])
        result["passed_count"] = result["tests"] - result["failures"] - result["errors"] - result["skipped"]
        result["available"] = True
        result["passed"] = result["failures"] == result["errors"] == 0 and result["passed_count"] > 0
    except (ET.ParseError, OSError, ValueError) as exc:
        result["blocking_reason"] = str(exc)
    return result

def scalars(value, prefix="", limit=70):
    rows = []
    def visit(obj, name, depth):
        if len(rows) >= limit or depth > 5:
            return
        if isinstance(obj, dict):
            for key, item in obj.items():
                visit(item, name + "." + str(key) if name else str(key), depth + 1)
        elif isinstance(obj, list):
            rows.append({"field": name + ".length", "producer_reported_value": len(obj)})
            for index, item in enumerate(obj[:3]):
                visit(item, name + "[" + str(index) + "]", depth + 1)
        elif obj is None or isinstance(obj, (str, int, float, bool)):
            rows.append({"field": name, "producer_reported_value": obj})
    visit(value, prefix, 0)
    return rows[:limit]

def inspect_inputs(root, commit):
    groups, records, errors = {}, [], []
    for group, relative in GROUPS.items():
        folder = root / relative
        entries = []
        for path in sorted(folder.rglob("*")) if folder.is_dir() else []:
            if not path.is_file() or path.is_symlink():
                continue
            row = {"artifact_id": group + ":" + path.relative_to(folder).as_posix(),
                   "source_type": "GENERATED_ENGINEERING_INPUT", "source_path": path.relative_to(root).as_posix(),
                   "sha256": file_sha(path), "bytes": path.stat().st_size, "experiment_id": None,
                   "protocol_version": None, "git_commit": None, "data_version": None,
                   "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                   "verification_method": "Read available bytes, SHA-256; parse supported format; execution claims not independently verified",
                   "verification_result": "BYTES_HASHED", "observed_by_commit": commit,
                   "scientific_scope": "ENGINEERING_ONLY; no independent TEST, authority or physical validation inferred"}
            try:
                if path.suffix.lower() == ".json":
                    payload = read_json(path)
                    row["verification_result"] = "JSON_PARSED_AND_BYTES_HASHED"
                    row["producer_reported_fields"] = scalars(payload)
                    if isinstance(payload, dict):
                        for key in ("experiment_id", "protocol_version", "git_commit", "data_version"):
                            row[key] = payload.get(key)
                elif path.suffix.lower() == ".csv":
                    with path.open(encoding="utf-8-sig", newline="") as stream:
                        reader = csv.reader(stream)
                        row["columns"] = next(reader, [])
                        row["row_count"] = sum(1 for _ in reader)
                    row["verification_result"] = "CSV_PARSED_AND_BYTES_HASHED"
            except (ValueError, OSError, csv.Error) as exc:
                row["verification_result"] = "PARSE_FAILED"
                row["error"] = str(exc)
                errors.append({"source_path": row["source_path"], "error": str(exc)})
            entries.append(row)
            records.append(row)
        groups[group] = {"source_path": relative, "available": bool(entries), "records": entries,
                         "scientific_status": "NOT_INDEPENDENTLY_VALIDATED"}
    return groups, records, errors

def read_original_rows(root, names):
    for relative in names:
        path = root / relative
        if path.is_file():
            with path.open(encoding="utf-8-sig", newline="") as stream:
                return list(csv.DictReader(stream)), relative
    return [], None

def write_csv(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

def build(root, out, junit):
    root, out, junit = Path(root).resolve(), Path(out).resolve(), Path(junit).resolve()
    if not out.is_relative_to(root):
        raise ValueError("output directory must remain within the checkout")
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    source = source_integrity(root)
    commit = source["git_commit"]
    tests = parse_junit(junit)
    groups, inputs, input_errors = inspect_inputs(root, commit)
    generated = []
    def metadata(name):
        return {"artifact_id": name, "source_type": "DERIVED_ENGINEERING_REPORT",
                "source_path": (out / name).relative_to(root).as_posix(), "sha256": None,
                "sha256_recorded_in": "ARTIFACT_MANIFEST_SHA256.json (self excluded)",
                "experiment_id": "ENGINEERING-ONLY-" + str(os.environ.get("GITHUB_RUN_ID", "LOCAL")),
                "protocol_version": PROTOCOL, "git_commit": commit, "data_version": "SYNTHETIC_OR_REPORTED_INPUT_SCOPE_ONLY",
                "created_at": now, "verification_method": "Source hashes, JUnit parsing and documented engineering checks",
                "verification_result": "DERIVED_NOT_INDEPENDENT_SCIENTIFIC_VERIFICATION",
                "scientific_scope": "No new scientific experiment or external authorization"}
    def json_out(name, payload):
        (out / name).write_text(json.dumps({"artifact_metadata": metadata(name), **payload},
            ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        generated.append(name)
    def text_out(name, text):
        (out / name).write_text(text.rstrip() + "\n", encoding="utf-8")
        generated.append(name)
    def csv_out(name, rows):
        write_csv(out / name, rows)
        generated.append(name)
    current_ok = source["passed"] and tests["passed"] and all(g["available"] for g in groups.values()) and not input_errors
    flags = {name: "NO" for name in (
        "SOFTWARE_READY REPRODUCIBILITY_READY CALIBRATION_SCIENTIFICALLY_VALIDATED "
        "ADAPTIVE_CONTRIBUTION_SUPPORTED R19_DESIGN_APPROVED R19_PROSPECTIVE_READY "
        "R19_PROSPECTIVE_EXECUTED EXTERNAL_DATA_READY INDEPENDENT_TEST_READY "
        "INDEPENDENT_TEST_EXECUTED PHYSICAL_SAFETY_VALIDATED MANUSCRIPT_READY "
        "Q1_SCIENTIFIC_CLAIMS_SUPPORTED GITHUB_MAIN_SYNCED GOOGLE_DRIVE_SYNCED").split()}
    flags["SOFTWARE_READY"] = "PARTIAL" if current_ok else "NO"
    flags["REPRODUCIBILITY_READY"] = "PARTIAL" if source["passed"] and tests["passed"] else "NO"
    json_out("FINAL_STATUS.json", {**flags, "CONFIRMATORY_STATUS": "NO_GO", "locked": False,
             "engineering_report_complete": current_ok, "scientific_go": False,
             "reason": "Software artifacts/tests do not supply calibration, independent data, preregistration, physical or release approval.",
             "engineering_input_errors": input_errors})
    for filename, blockers in (("BLOCKERS_EXTERNAL.json", EXTERNAL), ("BLOCKERS_SCIENTIFIC.json", SCIENTIFIC)):
        json_out(filename, {"status": "BLOCKED", "blockers": [
            {"blocker_id": key, "subject": subject, "blocking_reason": reason,
             "required_evidence": reason, "reviewer_or_authority": None,
             "verification_result": "NOT_SATISFIED_BY_THIS_ENGINEERING_RUN"}
            for key, subject, reason in blockers]})
    json_out("SOURCE_INTEGRITY_REPORT.json", {**source, "input_evidence_records": inputs,
             "historical_160_recertified": False, "historical_20_pairs_recertified": False,
             "original_execution_sha_exception": "UNRECORDED_LOCAL_SHA",
             "newline_policy": "Raw worktree SHA-256 always retained; LF-equivalent Git blobs separately classified"})
    json_out("TEST_SUMMARY.json", tests)
    baseline_path = root / "docs/remediation/CI_BASELINE_20261028.json"
    try:
        baseline = read_json(baseline_path) if baseline_path.is_file() else None
        baseline_error = None
    except (ValueError, OSError) as exc:
        baseline, baseline_error = None, str(exc)
    ci = {key: os.environ.get(key) for key in ("GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "RUNNER_OS", "RUNNER_ARCH")}
    json_out("CI_MATRIX.json", {"baseline_snapshot": baseline,
             "baseline_snapshot_sha256": file_sha(baseline_path) if baseline_path.is_file() else None,
             "baseline_error": baseline_error, "current_ci_context": ci,
             "current_workflow_status": "RUNNING_AT_REPORT_GENERATION_NOT_FINAL_CI_VERDICT",
             "current_junit_passed": tests["passed"], "python": sys.version, "platform": platform.platform(),
             "dependency_records": [r for r in inputs if "environment" in r["source_path"]],
             "scope": "Historical baseline readback and current job evidence remain separate"})
    json_out("DATA_LINEAGE_REPORT.json", {"engineering_evidence": groups["engineering"],
             "provider_measurements_admitted": False, "historical_raw_sources_rehashed": False,
             "lineage_scope": "Read available generated engineering records only",
             "exposure_register_independently_verified": False,
             "required": ["provider bytes and rights", "raw row/bin mapping", "physical semantics", "full exposure and split authority"]})
    json_out("CALIBRATION_VALIDATION.json", {"calibration_evidence": groups["calibration"],
             "family_coverage_claim": False, "scientifically_validated": False,
             "scope": "Producer-reported synthetic calibration metrics; file hashing does not validate assumptions",
             "required": ["per-scenario family coverage", "false pair/removal", "utility and abstention", "tail resolution",
                          "dependence assumptions", "independent validation"]})
    json_out("COMPUTE_FAIRNESS_REPORT.json", {"compute_evidence": groups["compute"],
             "factorial_evidence": groups["factorial"], "equal_budget_is_equal_total_cost": False,
             "energy_measured": False, "hardware_certification": False,
             "scope": "Measured producer fields only; wall/CPU/RSS vary by runner, no extrapolated energy or real-time guarantee"})
    sys.path.insert(0, str(root / "src"))
    rainflow = {"trace": [0.0, 1.0, 0.0], "expected_weighted_depth": 1.0,
                "legacy_retained": True, "physical_battery_validation": False}
    try:
        from jer_microgrid.metrics import rainflow_cycles_detailed
        from crmt_edge_ems.metrics_v2 import rainflow_cycles_detailed_v2, METRICS_VERSION
        rainflow["legacy_weighted_depth"] = sum(d * w for d, w, _, _ in rainflow_cycles_detailed(rainflow["trace"]))
        rainflow["future_weighted_depth"] = sum(d * w for d, w, _, _ in rainflow_cycles_detailed_v2(rainflow["trace"]))
        rainflow["future_counterexample_passed"] = math.isclose(rainflow["future_weighted_depth"], 1.0, abs_tol=1e-12)
        rainflow["future_metrics_version"] = METRICS_VERSION
    except (ImportError, ValueError, RuntimeError) as exc:
        rainflow["future_counterexample_passed"] = False
        rainflow["error"] = str(exc)
    relevant = [r for r in tests["cases"] if any(word in str(r).lower() for word in ("safety", "timeout", "deadline", "metrics_v2", "future_metrics", "leakage"))]
    json_out("SAFETY_VERIFICATION.json", {"rainflow_counterexample": rainflow,
             "relevant_current_junit_cases": relevant, "engineering_evidence": groups["engineering"],
             "physical_limits_independently_approved": False, "hil_or_field_verified": False,
             "battery_lifetime_validated": False, "scope": "Software veto/process and future metric evidence only"})
    grid = []
    for p in range(1, 257):
        lo, hi = max(0, 10 - (256 - p)), min(10, p)
        bound = (hi - lo) / p
        grid.append({"pool_size": 256, "shortlist_size": 10, "pareto_size": p,
                     "min_hits": lo, "max_hits": hi, "sharp_max_abs_delta_miss": bound,
                     "step_per_hit": 1 / p, "effect_threshold": 0.05,
                     "effect_geometrically_possible": hi - lo >= math.ceil(0.05 * p - 1e-12),
                     "scope": "DESIGN_GEOMETRY_ONLY_NOT_OBSERVED_AUDIT"})
    csv_out("R19_EFFECT_FEASIBILITY.csv", grid)
    text_out("R19_DESIGN_REVIEW.md", "# R19 tasarım incelemesi\n\n"
        "Durum: PARTIAL; bağımsız tasarım onayı yok, locked=false, prospektif yürütme yok.\n\n"
        "N=256 ve K=10 sabitken P AUDIT Pareto boyutu için minimum isabet=max(0,10-(256-P)), "
        "maksimum isabet=min(10,P). Keskin mutlak MissRate farkı sınırı=(maksimum-minimum)/P. "
        "P=1..256 tam ızgarası ekte; P>200 için 0.05 mutlak etki mümkün değildir. "
        "P gerçek AUDIT verisinden burada tahmin edilmedi. Sonuç planlama geometrisidir; "
        "etki büyüklüğü, güç veya F1 üstünlüğü kanıtı değildir. Δ=MissRate(F1)-MissRate(F0); negatif yön F1 lehinedir.\n\n"
        "K10 doğal shortlist, backfill yok, all256 DISCOVERY normalizasyonu ve sayısal Pareto politikası "
        "ayrıca onaylanmalıdır. Normalizasyon yalnız DISCOVERY; AUDIT seçim için kullanılamaz. "
        "Bağımsız birim, veri bölmesi, pratik etki ve güç varsayımları kilitlenmeden deney NO_GO.\n")
    gate_names = ["SOURCE_INTEGRITY", "DATA_SEMANTICS", "METHOD_AND_CAPACITY", "SPLIT_AND_EXPOSURE",
                  "POWER_AND_PREREGISTRATION", "DISCOVERY_AUDIT_EXECUTION", "INDEPENDENT_TEST", "MANUSCRIPT_RELEASE"]
    json_out("GATE_STATUS.json", {"CONFIRMATORY_STATUS": "NO_GO", "locked": False, "gates": [
        {"gate": "G" + str(i) + "_" + name, "status": "PARTIAL" if i == 0 and source["passed"] else "BLOCKED_EXTERNAL",
         "required_evidence": ("Current source hash plus independent execution identity" if i == 0 else "Independent approved evidence for " + name),
         "verification_method": "Current engineering bytes/JUnit checked; no independent authority installed",
         "evidence_hash": file_sha(out / "SOURCE_INTEGRITY_REPORT.json") if i == 0 else None,
         "blocking_reason": "Engineering evidence is insufficient for scientific authorization",
         "reviewer_or_authority": None, "last_checked": now} for i, name in enumerate(gate_names)]})
    originals, register_path = read_original_rows(root, [
        "docs/remediation/historical_20261027/A01_A32_REMEDIATION_MATRIX.csv",
        "08_OPEN_TASKS/CRMT_YAPILACAKLAR_20261027.csv",
        "docs/remediation/A01_A32_REMEDIATION_MATRIX.csv"])
    by_id = {r.get("id", r.get("task_id", "")): r for r in originals}
    tasks = []
    for i, label in enumerate(LABELS, 1):
        key = "A" + str(i).zfill(2)
        old = by_id.get(key, {})
        status = "BLOCKED_EXTERNAL" if i in (7, 21, 23, 24, 25, 26) else "BLOCKED_SCIENTIFIC" if i in (10, 19, 32) else "PARTIAL"
        tasks.append({"task_id": key, "original_problem": old.get("problem", old.get("task", old.get("original_problem", label))),
            "label_source": register_path or "User-carried normalized A01-A32 labels; original register absent",
            "prior_status": old.get("verification_status", old.get("status", "NOT_RECHECKED_HISTORICAL")),
            "current_status": status, "change": "Current source/test/evidence inspection; no historical or external reauthorization",
            "files": ";".join(r["source_path"] for r in inputs[:8]),
            "tests": str(tests.get("passed_count", 0)) + " current repository passes; scope in TEST_SUMMARY.json",
            "scientific_evidence": "Engineering/synthetic only; original scientific evidence not recertified",
            "historical_remaining_blocker": old.get("remaining_blocker", "NOT_AVAILABLE"),
            "current_status_reason": {
                16: "Full256 engineering measurements are read from compute evidence; energy/hardware and cross-method total fairness remain unvalidated",
                20: "Future safety/process/metric source and current JUnit are inspected; independent physical approval remains absent",
                22: "Full-day engineering smoke uses explicitly synthetic inputs; historical/provider real-data certification not implied",
                29: "Fresh baseline CI and current JUnit are separate; final current workflow completion is checked after this generator"
            }.get(i, "Current engineering evidence does not recertify historical or external scientific evidence"),
            "remaining_blocker": ("Independent external evidence required" if status == "BLOCKED_EXTERNAL" else
                "Energy, hardware and independently comparable end-to-end total cost" if i == 16 else
                "Independent physical/HIL approval" if i == 20 else
                "Provider-verified real-data full-day execution and exposure authority" if i == 22 else
                "Final current CI readback, exact environment and future execution lock" if i == 29 else
                old.get("remaining_blocker", "Independent scientific/protocol validation required")),
            "verification_status": status, "scientific_status": "NO_GO",
            "next_action": "Inspect linked evidence, obtain actual missing authority/data; do not close from code alone"})
    csv_out("A01_A32_FINAL_TRACKER.csv", tasks)
    claim_rows, claim_source = read_original_rows(root, [
        "06_MANUSCRIPT_AND_PUBLICATION/03_REVISIONS_20261027/CLAIM_EVIDENCE_CURRENT.csv",
        "docs/remediation/CLAIM_EVIDENCE_CURRENT.csv"])
    claims_by_id = {r.get("id", r.get("claim_id", "")): r for r in claim_rows}
    historical_claim_path = root / "docs/remediation/historical_20261027/12_MANUSCRIPT_CLAIM_AUDIT.md"
    historical_scopes = {}
    if historical_claim_path.is_file():
        for line in historical_claim_path.read_text(encoding="utf-8-sig").splitlines():
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) >= 5 and cells[1].startswith("C") and cells[1][1:].isdigit():
                historical_scopes[cells[1]] = {"allowed": cells[2], "remaining": cells[3]}
        claim_source = historical_claim_path.relative_to(root).as_posix()
    known = {"C03": "Tarihsel objective eşitliği bağımsız operational benefit değildir.",
             "C07": "Validation-evaluated approximation-set quality of TRAIN-generated fronts.",
             "C08": "Kaynak kökeni kapsamı ve özgün SHA istisnası korunmalıdır.",
             "C09": "Kaynak kökeni kapsamı ve özgün SHA istisnası korunmalıdır.",
             "C10": "Kaynak kökeni kapsamı ve özgün SHA istisnası korunmalıdır.",
             "C11": "Evrensel F0 subset iddiası yok; tarihsel 18/20 raporu burada yeniden doğrulanmadı.",
             "C12": "Arşiv-geneli yüzde 95 garanti iddiası yok.",
             "C13": "R22/R23 koşullu prototip; fiziksel güvence yok.",
             "C14": "R19 taslak ve NO_GO.",
             "C15": "R26–R30 metadata; bağımsız ölçüm TEST kanıtı yok."}
    csv_out("MANUSCRIPT_CLAIM_MATRIX.csv", [
        {"claim_id": key, "original_claim": claims_by_id.get(key, {}).get("iddia", claims_by_id.get(key, {}).get("claim", "ORIGINAL_CLAIM_TEXT_UNAVAILABLE")),
         "original_claim_source": claim_source or "Original claim CSV unavailable; no text invented",
         "historical_20261027_allowed_scope": historical_scopes.get(key, {}).get("allowed", "NOT_AVAILABLE"),
         "historical_20261027_remaining": historical_scopes.get(key, {}).get("remaining", "NOT_AVAILABLE"),
         "current_status_reason": "Historical quantitative claims are not recertified; current evidence is engineering/synthetic only",
         "allowed_scope": claims_by_id.get(key, {}).get("izin_verilen_ifade", historical_scopes.get(key, {}).get("allowed", known.get(key, "Original source and author review required"))),
         "current_evidence": "SOURCE_INTEGRITY_REPORT.json; historical README/builder statements remain historical",
         "verification_status": "PARTIAL_NOT_INDEPENDENTLY_VALIDATED", "manuscript_compiled_this_run": False,
         "remaining_blocker": "Read original manuscript, verify references and every quantitative claim; author review pending"}
        for key in ("C" + str(i).zfill(2) for i in range(1, 16))])
    findings = [
        {"finding_id": "N01", "priority": "P0", "subject": "Legacy rainflow and terminal SOC",
         "status": "FUTURE_COUNTEREXAMPLE_PASSED" if rainflow.get("future_counterexample_passed") else "OPEN",
         "evidence": json.dumps(rainflow, ensure_ascii=False), "remaining": "Historical outcomes unchanged; physical lifetime and full reference validation not inferred"},
        {"finding_id": "N02", "priority": "P0", "subject": "R19 practical effect geometry",
         "status": "DESIGN_REVIEW_REQUIRED", "evidence": "P>200 implies maximum absolute effect<0.05", "remaining": "Prospective effect/power plan independently approve"},
        {"finding_id": "N03", "priority": "P0", "subject": "External authority and independent TEST",
         "status": "BLOCKED_EXTERNAL", "evidence": "No verified new authority/data installed", "remaining": "BLOCKERS_EXTERNAL.json"},
        {"finding_id": "N04", "priority": "P1", "subject": "Branch protection",
         "status": "MANUAL_REVIEW_REQUIRED", "evidence": "Baseline reported protected=false, rulesets=[]; detail403 integration permission",
         "remaining": "CI success is not enforced review policy; no settings changed"},
        {"finding_id": "N05", "priority": "P1", "subject": "Historical source drift and execution SHA",
         "status": "OPEN", "evidence": "Current source hashes do not recertify historical160/pairs or explain eight prior differences",
         "remaining": "Original immutable historical evidence, not replacement HEAD"},
    ]
    csv_out("NEW_FINDINGS.csv", findings)
    historical_acceptance, acceptance_source = read_original_rows(root, [
        "docs/remediation/historical_20261027/ACCEPTANCE_22_QUESTIONS.csv"])
    old_questions = {int(r["question"]): r for r in historical_acceptance}
    audit_rows = []
    for i, subject in enumerate(ACCEPTANCE, 1):
        subject = old_questions.get(i, {}).get("subject", subject)
        status = "PARTIAL"
        if i in (2, 3, 5, 6, 16, 17, 18, 20):
            status = "BLOCKED_EXTERNAL_OR_NOT_RECHECKED"
        elif i in (9, 11, 13, 14):
            status = "BLOCKED_SCIENTIFIC"
        elif i == 19:
            status = "NOT_STARTED_AUTHORIZED_SCIENCE"
        elif i == 4:
            status = "CURRENT_JUNIT_PASSED" if tests["passed"] else "CURRENT_JUNIT_NOT_PASSED"
        old_status = old_questions.get(i, {}).get("status", "NOT_AVAILABLE")
        audit_rows.append(f"| {i} | {subject} | {old_status} | {status} |")
    text_out("A_Z_FINAL_ACCEPTANCE_AUDIT.md", "# A–Z nihai kabul denetimi\n\n"
        "Karar: Mühendislik kısmi; bilimsel GO yok. Dosya varlığı veya sentetik geçiş dış kapı kapatmaz.\n\n"
        "| No | Konu | 2026-10-27 tarihsel durum | Güncel kapsam |\n| --- | --- | --- | --- |\n" + "\n".join(audit_rows) +
        "\n\n22 konu önceki rapor builder'ındaki kabul listesiyle eşleşir. "
        "A01–A32 orijinal kayıt mevcut değilse normalize etiketler açıkça belirtilir. "
        "Tarihsel 160/20/419 kanıtı bu çalışmada yeniden sertifikalanmadı. Tüm 15 karar FINAL_STATUS.json içinde ayrıdır.\n")
    json_out("GITHUB_DRIVE_SYNC_RECEIPT.json", {"status": "PENDING", "github_main": {"verified": False,
             "expected_source_commit": commit, "verification_method": "Requires postmerge independent ref/readback"},
             "google_drive": {"verified": False, "folder_id": None, "uploaded_files": []},
             "not_authorization": True, "remaining": "Root agent must upload/read back artifacts and verify remote main; file existence is not sync"})
    phase = {
        "PHASE": "FINAL_ENGINEERING_EVIDENCE_ASSEMBLY",
        "FILES_INSPECTED": [r["source_path"] for r in inputs] + [str(junit), "Git HEAD tracked source", str(baseline_path)],
        "FILES_CHANGED": [str(out / name) for name in dict.fromkeys(REQUIRED + ["GATE_STATUS.json", "NEW_FINDINGS.csv", "PHASE_REPORT.json", "PHASE_REPORT_TR.md"])],
        "BUGS_FIXED": "This generator observes current evidence; fixes are attributed to source diff/CI, not invented here.",
        "TESTS_ADDED": "See current source tests/test_final_evidence.py and source commit; no guessed count",
        "TESTS_PASSED": tests.get("passed_count", 0), "TESTS_FAILED": tests["failures"] + tests["errors"],
        "SCIENTIFIC_EVIDENCE": "Engineering/synthetic only; no new approved AUDIT or independent TEST",
        "REMAINING_BLOCKERS": [reason for _, _, reason in EXTERNAL + SCIENTIFIC],
        "GIT_COMMIT": commit, "GOOGLE_DRIVE_ARTIFACTS": "PENDING independently verified upload/readback",
        "NEXT_ACTION": "Complete source review and CI, verify remote source/artifact hashes; keep scientific NO_GO"}
    json_out("PHASE_REPORT.json", phase)
    text_out("PHASE_REPORT_TR.md", "# Faz raporu — mühendislik kanıt paketi\n\n" +
        "\n\n".join("**" + key + "**\n\n" + (json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (list, dict)) else str(value))
                    for key, value in phase.items()) +
        "\n\nBu paket yayın veya bilimsel onay değildir. Ham veri, frozen sonuçlar ve özgün v12 üzerinde değişiklik yapılmadı; "
        "bu ifade bu generator'ın eylem sınırıdır, erişilemeyen eski dosyaların yeni hash sertifikası değildir.\n")
    json_out("ARTIFACT_MANIFEST_SHA256.json", {"self_excluded": "ARTIFACT_MANIFEST_SHA256.json",
             "mandatory_artifacts": REQUIRED, "artifacts": [
        {**metadata(name), "sha256": file_sha(out / name), "bytes": (out / name).stat().st_size,
         "verification_method": "SHA-256 of final generated file bytes", "verification_result": "BYTES_HASHED"}
        for name in generated], "input_evidence_artifacts": inputs,
        "scope": "Manifest certifies bytes only; no scientific or provider authority"})
    if any(not (out / name).is_file() for name in REQUIRED) or len(tasks) != 32 or len(grid) != 256:
        raise RuntimeError("required deliverable structure incomplete")
    return {"out": str(out), "artifacts": len(generated), "engineering_complete": current_ok,
            "git_commit": commit, "scientific_go": False, "test_passed_count": tests.get("passed_count", 0)}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("reports/final"))
    parser.add_argument("--junit", type=Path, default=Path("reports/test_results/junit.xml"))
    args = parser.parse_args(argv)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    junit = args.junit if args.junit.is_absolute() else ROOT / args.junit
    result = build(ROOT, out, junit)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0 if result["engineering_complete"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
