"""Extract verbatim manuscript claims and verify frozen table/result bindings.

No raw data are embedded. Run with --project-root pointing to the private canonical
project tree. Empty page cells intentionally mean that no source-to-PDF page mapping
was independently verified. Source lines, not guessed PDF pages, are authoritative.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FIELDS = "claim_id exact_claim_text source_file source_line manuscript_section manuscript_page_if_verified referenced_table_or_figure evidence_file experiment_id dataset data_split measurement_type metric_version execution_commit statistic uncertainty evidence_verified scientific_support_level unsupported_interpretation required_revision proposed_revised_claim reviewer_comment".split()
BASE = Path("10_FINAL_REMEDIATION_AND_VALIDATION")
NEW = BASE / "16_CODEX_SCIENTIFIC_REMEDIATION_20261028"
V14 = BASE / "09_MANUSCRIPT/v14_working_source"
V13 = Path("06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13")
RESULTS = Path("05_RESULTS_AND_EVIDENCE/01_INITIAL_30_SEED_EVIDENCE (2)")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def section(lines, line_number):
    headings = [m.group(1) for line in lines[:line_number] if (m := re.match(r"\\(?:sub)*section\*?\{(.+)\}", line))]
    return " / ".join(headings[-2:]) or "Abstract/front matter"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output or root / NEW / "01_CLAIM_AUDIT"
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    hashes = {}

    def evidence(paths):
        resolved = []
        for path in paths:
            rel = Path(path)
            full = root / rel
            if not full.is_file():
                raise FileNotFoundError(full)
            hashes[rel.as_posix()] = sha(full)
            resolved.append(rel.as_posix())
        return "; ".join(resolved)

    frozen = evidence([RESULTS / name for name in ["optimizer_quality_seed.csv", "optimizer_quality_descriptive.csv", "optimizer_quality_pairwise_wilcoxon_holm.csv", "internal_seed_metrics.csv", "internal_descriptive.csv", "internal_pairwise_wilcoxon_holm.csv", "ood_macro_seed_metrics.csv", "ood_macro_descriptive.csv", "ood_macro_pairwise_wilcoxon_holm.csv", "ablation_internal_seed_metrics.csv", "ablation_internal_pairwise_wilcoxon_holm.csv", "sensitivity_paired_contrasts.csv", "analysis_summary.json", "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv"]])
    # Audit hash declarations where the frozen report actually declares them.
    summary = json.loads((root / RESULTS / "analysis_summary.json").read_text(encoding="utf-8-sig"))
    for name, expected in summary.get("files_sha256", {}).items():
        actual = sha(root / RESULTS / name)
        checks.append(dict(check="FROZEN_REPORT_SHA256", item=name, expected=expected, observed=actual, passed=actual == expected))

    # A rounded table cell is accepted only within half a unit of its final digit.
    bindings = []
    methods = ["CRMT", "SOBOL", "NSGAII", "MOPSO", "MODE"]
    metric_rows = {"Hypervolume": "hypervolume", "IGD+": "igd_plus", "Additive epsilon": "additive_epsilon", "Capacity violation": "cap_violation_pct_total", "LFP cycle-loss": "lfp_cycle_loss_pct", "95th-percentile ramp": "ramp95_kw_per_min", "Switching flips/day": "flip_per_day"}
    for table, source in [("tab_optimizer_quality.tex", "optimizer_quality_descriptive.csv"), ("tab_internal_operational.tex", "internal_descriptive.csv"), ("tab_OPSD_OOD_operational.tex", "ood_macro_descriptive.csv")]:
        rows = read_csv(root / RESULTS / source)
        lookup = {(r["method"], r["metric"]): r for r in rows}
        for line_no, line in enumerate((root / V14 / "tables" / table).read_text(encoding="utf-8").splitlines(), 1):
            metric = next((v for k, v in metric_rows.items() if line.startswith(k)), None)
            if not metric:
                continue
            cells = line.split("&")
            offset = 2 if table == "tab_optimizer_quality.tex" else 1
            for method, cell in zip(methods, cells[offset:offset + 5]):
                nums = re.findall(r"[-+]?\d+\.\d+(?:[eE][-+]?\d+)?|[-+]?\d+(?:[eE][-+]?\d+)?", cell)
                keys = ["median", "q25", "q75"] if table == "tab_optimizer_quality.tex" else ["median"]
                for key, token in zip(keys, nums):
                    decimals = len(token.split(".")[1].split("e")[0]) if "." in token else 0
                    exponent = int(token.lower().split("e")[1]) if "e" in token.lower() else 0
                    tolerance = .500001 * 10 ** (exponent - decimals)
                    actual = float(lookup[(method, metric)][key])
                    passed = abs(float(token) - actual) <= tolerance
                    bindings.append(dict(manuscript_asset=(V14 / "tables" / table).as_posix(), source_line=line_no, result_file=(RESULTS / source).as_posix(), experiment_id=source.split("_")[0].upper(), result_selector=f"method={method};metric={metric};statistic={key}", manuscript_value=token, evidence_value=repr(actual), rounding_tolerance=tolerance, passed=passed, measurement_type="FROZEN_LEGACY_SIMULATION_STATISTIC", original_trajectory_reconstructed=False))
    def bind_tokens(table, line_no, result_file, selector, tokens, values):
        for token, (statistic, actual) in zip(tokens, values):
            decimals = len(token.split(".")[1].split("e")[0]) if "." in token else 0
            exponent = int(token.lower().split("e")[1]) if "e" in token.lower() else 0
            tolerance = .500001 * 10 ** (exponent - decimals)
            bindings.append(dict(manuscript_asset=(V14 / "tables" / table).as_posix(), source_line=line_no, result_file=(RESULTS / result_file).as_posix(), experiment_id=result_file.split("_")[0].upper(), result_selector=selector+";statistic="+statistic, manuscript_value=token, evidence_value=repr(actual), rounding_tolerance=tolerance, passed=abs(float(token)-actual) <= tolerance, measurement_type="FROZEN_LEGACY_SIMULATION_STATISTIC", original_trajectory_reconstructed=False))

    for line_no, line in enumerate((root / V14 / "tables/tab_ablation_CRMT_contrasts.tex").read_text(encoding="utf-8").splitlines(), 1):
        metric = next((v for k,v in metric_rows.items() if line.startswith(k)), None)
        if metric is None:
            continue
        cells = line.split("&")
        method = cells[1].strip().replace("\\_", "_")
        row = next(r for r in read_csv(root / RESULTS / "ablation_internal_pairwise_wilcoxon_holm.csv") if r["metric"] == metric and r["method_b"] == method)
        tokens = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", " ".join(cells[2:]))
        columns = ["median_difference_a_minus_b", "median_difference_ci_low", "median_difference_ci_high", "rank_biserial_a_minus_b", "p_value_holm"]
        bind_tokens("tab_ablation_CRMT_contrasts.tex", line_no, "ablation_internal_pairwise_wilcoxon_holm.csv", f"metric={metric};method_a=CRMT;method_b={method}", tokens, [(k,float(row[k])) for k in columns])
    variant_names = {"Efficiency 0.90":"ETA_LOW_090", "Ideal efficiency":"ETA_IDEAL_100", "SOC conservative":"SOC_CONSERVATIVE_15_95", "Ramp limit $\\times 0.5$":"RAMP_HALF", "Ramp limit $\\times 0.25$":"RAMP_QUARTER", "Temporal floor":"TEMPORAL_FLOOR"}
    for line_no, line in enumerate((root / V14 / "tables/tab_sensitivity_CRMT_contrasts.tex").read_text(encoding="utf-8").splitlines(), 1):
        variant = next((v for k,v in variant_names.items() if line.startswith(k)), None)
        if variant is None:
            continue
        for metric, cell in zip(["cap_violation_pct_total", "lfp_cycle_loss_pct", "ramp95_kw_per_min", "flip_per_day"], line.split("&")[1:]):
            normalized = re.sub(r"\\!\\times\\!10\^\{([-+]?\d+)\}", r"e\1", cell)
            tokens = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", normalized)
            row = next(r for r in read_csv(root / RESULTS / "sensitivity_paired_contrasts.csv") if r["method"] == "CRMT" and r["objective"] == metric and r["variant_id"] == variant)
            keys = ["median_difference_sensitivity_minus_primary", "p_value_holm_within_method_objective"]
            bind_tokens("tab_sensitivity_CRMT_contrasts.tex", line_no, "sensitivity_paired_contrasts.csv", f"method=CRMT;objective={metric};variant_id={variant}", tokens, [(k,float(row[k])) for k in keys])
    # Verify frozen aggregate medians against the actual 30-seed rows.
    for kind in ["optimizer_quality", "internal", "ood_macro"]:
        seed_name = "optimizer_quality_seed.csv" if kind == "optimizer_quality" else f"{kind}_seed_metrics.csv"
        seed_rows = read_csv(root / RESULTS / seed_name)
        for row in read_csv(root / RESULTS / f"{kind}_descriptive.csv"):
            vals = [float(r[row["metric"]]) for r in seed_rows if r["method"] == row["method"]]
            checks.append(dict(check="SEED_MEDIAN_RECALCULATED", item=f"{kind}:{row['method']}:{row['metric']}", expected=float(row["median"]), observed=statistics.median(vals), passed=len(vals) == int(row["n"]) == 30 and abs(statistics.median(vals) - float(row["median"])) < 1e-12))
    ab = read_csv(root / RESULTS / "ablation_internal_seed_metrics.csv")
    met = ["cap_violation_pct_total", "lfp_cycle_loss_pct", "ramp95_kw_per_min", "flip_per_day"]
    equality = all(all(float(next(r for r in ab if r["seed"] == str(seed) and r["method"] == "CRMT")[m]) == float(next(r for r in ab if r["seed"] == str(seed) and r["method"] == "NO_ADAPTIVE")[m]) for m in met) for seed in range(1001, 1031))
    checks.append(dict(check="NO_ADAPTIVE_OUTCOME_EQUALITY", item="30 seeds x four objectives", expected=True, observed=equality, passed=equality))

    claims = []
    default = dict(dataset="OpenCEM/OPSD as indicated", data_split="HISTORICAL_EXPOSED", measurement_type="SIMULATION_USING_RECORDED_MEASUREMENTS", metric_version="FROZEN_LEGACY_METRICS", execution_commit="ORIGINAL_EXECUTION_NOT_RECOVERED_FROM_STATISTICAL_CSV; see immutable experiment manifests; seed1001/C1_F1_A1 remains UNRECORDED_LOCAL_SHA", statistic="Claim-specific archived table/result; table medians independently recalculated where applicable", uncertainty="30 optimizer seeds conditional on fixed dataset; frozen paired inference does not measure independent-site uncertainty", scientific_support_level="HISTORICAL_PROTOCOL_SPECIFIC_ONLY", unsupported_interpretation="Corrected-metric or universal superiority, new independent TEST, physical validity", required_revision="State legacy version, exposure and conditional scope adjacent to the result", proposed_revised_claim="Preserved historical evidence only; corrected-metric results and independent validation remain separate.", reviewer_comment="Source excerpt verified byte-for-byte as a complete nonempty LaTeX source line; no PDF-page number inferred.")

    def add(file, line_numbers, refs, paths, experiment, **overrides):
        text = (root / file).read_text(encoding="utf-8")
        lines = text.splitlines()
        hashes[file.as_posix()] = sha(root / file)
        for line_no in line_numbers:
            exact = lines[line_no - 1]
            if not exact.strip() or exact.startswith("%"):
                raise ValueError(f"Not a claim: {file}:{line_no}")
            row = {**default, **overrides, "claim_id": f"MC{len(claims) + 1:03d}", "exact_claim_text": exact, "source_file": file.as_posix(), "source_line": line_no, "manuscript_section": section(lines, line_no), "manuscript_page_if_verified": "", "referenced_table_or_figure": refs, "evidence_file": evidence(paths), "experiment_id": experiment, "evidence_verified": "SOURCE_EXCERPT_AND_FILE_HASH_VERIFIED; statistical_scope_requires_frozen_original_execution"}
            claims.append(row)

    intro = V14 / "SECTIONS_1_2_ASOC_v14.tex"
    body = V14 / "SECTIONS_3_12_ASOC_v14.tex"
    main_file = V14 / "MANUSCRIPT_ASOC_FULL_v14.tex"
    add(intro, [13, 15, 17], "Fig. crmt_architecture; tab_optimizer_protocol", [RESULTS / "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv"], "ASOC-TRAIN/VAL/ITEST/OOD", scientific_support_level="IMPLEMENTATION_DESCRIPTION_AND_SCOPED_CONTRIBUTION", unsupported_interpretation="A new optimizer primitive or proved research novelty from metadata alone", required_revision="Avoid unsupported exhaustive novelty/gap claim; distinguish wrapper design from validated advantage")
    add(body, [21, 23, 25, 30, 32], "Operational objective equations", [BASE / "12_METRIC_REVISION_PILOT_20261028/LEGACY_VS_V2_OBJECTIVES.csv", BASE / "15_OPENCEM_4DAY_CHECKED_EMS_20261028/CAP_VIOLATION_FLOAT_EPSILON_AUDIT.json"], "LEGACY-OBJECTIVE-DEFINITION", scientific_support_level="IMPLEMENTATION_FORMULA_WITH_KNOWN_DEFECTS", required_revision="Label the strict-cap and rainflow equations as frozen legacy semantics; declare separately versioned corrected metrics", proposed_revised_claim="Frozen results use strict capacity comparison and legacy SOC/rainflow; v3 engineering results include terminal SOC and an explicit capacity tolerance.")
    add(body, [35, 40, 43, 46, 49, 52, 55], "tab_controller_parameter_space;tab_optimizer_protocol", [RESULTS / "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv", BASE / "09_MANUSCRIPT/v14_working_source/tables/tab_optimizer_protocol.tex"], "ASOC-METHODS", scientific_support_level="METHOD_DESCRIPTION_CONDITIONAL_NOT_PERFORMANCE_PROOF", required_revision="Describe what code/protocol specifies; do not infer archive-wide confidence, efficiency or hardware safety")
    add(body, [60], "tab_data_split_protocol", [BASE / "14_OPENCEM_19_RAW_VALUES_20261028/FULL_19_REGRESSION_TEST_RECEIPT.json"], "OPENCEM-RAW-19", scientific_support_level="PARTIALLY_INCORRECT_COMPLETE_DAY_WORDING", statistic="406 historical windows: 381 complete and 25 partial, not 406 complete days", required_revision="Replace complete-day inventory with historical window inventory; distinguish min-coverage from strict full-day admission", proposed_revised_claim="The 406 historical windows comprise 381 complete and 25 partial windows; the frozen chronological split remains 210/118/78.")
    add(body, [63, 66, 73, 78, 81, 87, 90], "tab_data_split_protocol;tab_optimizer_protocol", [RESULTS / "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv", RESULTS / "analysis_summary.json"], "ASOC-PROTOCOL", required_revision="Use historically held-out/previously exposed in the current audit; seed replication is conditional on the dataset")
    add(body, [99, 108], "tab_optimizer_quality;Fig.optimizer_quality", [RESULTS / f"optimizer_quality_{x}.csv" for x in ["seed", "descriptive", "friedman", "pairwise_wilcoxon_holm"]], "ASOC-VAL-QUALITY", data_split="VALIDATION_EVALUATION_OF_TRAIN_GENERATED_FRONTS", statistic="CRMT median HV=0.6605029428074898; IGD+=0.00339128658754564; epsilon=0.05581939707945394", uncertainty="Medians/IQR across 30 optimizer seeds; paired Wilcoxon Holm p in result CSV", required_revision="Place legacy metric scope directly beside advantage and clarify VALIDATION scoring; total cost parity unproven")
    add(body, [113, 120], "tab_internal_operational;Fig.internal_effects", [RESULTS / f"internal_{x}.csv" for x in ["seed_metrics", "descriptive", "friedman", "pairwise_wilcoxon_holm"]], "ASOC-ITEST", data_split="PREVIOUSLY_EXPOSED_HISTORICAL_INTERNAL_TEST", required_revision="Retain objective-specific adverse/favorable signs; no fresh independent-test label")
    add(body, [125, 132], "tab_OPSD_OOD_operational;Fig.ood_effects", [RESULTS / f"ood_macro_{x}.csv" for x in ["seed_metrics", "descriptive", "friedman", "pairwise_wilcoxon_holm"]], "ASOC-OOD", dataset="OPSD Household Data 2020-04-15", data_split="PREVIOUSLY_EXPOSED_EXTERNAL_OOD", required_revision="No universal robustness; conditional optimizer seeds are not independent households/sites")
    add(body, [137, 139, 144], "Fig.cross_stage_evidence", [RESULTS / "optimizer_quality_descriptive.csv", RESULTS / "internal_pairwise_wilcoxon_holm.csv", RESULTS / "ood_macro_pairwise_wilcoxon_holm.csv"], "ASOC-CROSS-STAGE", required_revision="Correct schematic caption: current box does not list pairwise contrasts; refer to tables for those results")
    add(body, [153, 160], "tab_ablation_CRMT_contrasts;Fig.ablation_effects", [RESULTS / "ablation_internal_seed_metrics.csv", RESULTS / "ablation_internal_pairwise_wilcoxon_holm.csv"], "ASOC-ABLATION", statistic="30/30 NO_ADAPTIVE vectors equal to CRMT on four outcomes", scientific_support_level="NO_INDEPENDENT_ADAPTIVE_OPERATIONAL_BENEFIT_ESTABLISHED", required_revision="Outcome equality is verified; complete controller-parameter identity and causal effects remain unproven")
    add(body, [165, 172], "tab_sensitivity_CRMT_contrasts;Fig.sensitivity", [RESULTS / "sensitivity_paired_contrasts.csv", RESULTS / "sensitivity_variant_seed_metrics.csv"], "ASOC-SENSITIVITY", required_revision="Legacy metric objective-specific sensitivity; cannot generalize robustness to all operating regimes")
    add(body, [180, 183, 185, 188, 191, 194, 197, 201], "Historical discussion/threats", [RESULTS / "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv"], "ASOC-DISCUSSION", required_revision="Maintain conditional legacy scope; avoid interpreting nonsignificance as proof of equivalence")
    add(body, [208, 231], "CAL assumptions and evidence status", [BASE / "09_MANUSCRIPT/v14_working_source/SECTIONS_3_12_ASOC_v14.tex"], "CAL-v2-CONDITIONAL-CONTRACT", dataset="Synthetic diagnostics/conditional model", data_split="SYNTHETIC_AND_METHOD_CONTRACT", measurement_type="MATHEMATICAL_CONDITIONAL_AND_SYNTHETIC", metric_version="CAL-v2 conditional risk bounds; legacy bootstrap separately", scientific_support_level="CONDITIONAL_NOT_OPERATIONALLY_VALIDATED", uncertainty="No archive-wide operational 95% guarantee", required_revision="Separate mathematical conditional coverage, simulated family coverage, false elimination and capacity overflow")
    add(body, [210, 212, 237, 239, 241], "F0/F1 archive; R19 geometry", [BASE / "09_MANUSCRIPT/v14_working_source/SECTIONS_3_12_ASOC_v14.tex", RESULTS / "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv"], "R19-DRAFT/ARCHIVE-DIAGNOSTIC", data_split="HISTORICAL_DIAGNOSTIC_AND_UNEXECUTED_PROSPECTIVE_DRAFT", measurement_type="ALGEBRAIC_GEOMETRY_AND_ARCHIVED_RECORDS", scientific_support_level="GEOMETRY_CHECKABLE_PROSPECTIVE_NOT_APPROVED", uncertainty="P and K determine attainable effects; power needs assumptions and independent approval", required_revision="Retain unlocked/NO-GO; optimizer seeds are not independent sites; no invented R19 outcomes")
    add(body, [214, 216, 218, 225, 228, 234, 244, 245, 248, 252, 256], "Scope, implementation and reproducibility", [BASE / "15_OPENCEM_4DAY_CHECKED_EMS_20261028/CHECKED_EMS_ENGINEERING_STATUS.json", BASE / "12_METRIC_REVISION_PILOT_20261028/VALIDATION_RECEIPT.json"], "ENGINEERING-SCOPE", scientific_support_level="SCOPE_LIMIT_OR_IMPLEMENTATION_REQUIRING_UPDATED_RECEIPTS", required_revision="Update stale replay status with measured four-day pilot; keep actual historical provenance blocker; state explicit compute phase scope")
    add(main_file, [25, 37, 49], "Abstract/data/disclosure", [BASE / "09_MANUSCRIPT/V14_BUILD_CHECK.json", BASE / "09_MANUSCRIPT/V14_SOURCE_REVISION_RECEIPT.json"], "V14-WORKING", scientific_support_level="WORKING_SOURCE_NOT_AUTHOR_APPROVED", required_revision="Replace stale full-claim-review-pending with completed source-excerpt audit scope; retain author and independent scientific release gates")

    # Trace prior actual text without mutating or extracting into the frozen tree.
    for rel, line_no in [(V13 / "SECTIONS_1_2_ASOC_v13.tex", 13), (V13 / "SECTIONS_3_12_ASOC_v13.tex", 99)]:
        add(rel, [line_no], "Historical predecessor text", [RESULTS / "HISTORICAL_EXPERIMENT_LEDGER_20261022.csv"], "V13-TEXT-LINEAGE", scientific_support_level="PREDECESSOR_TEXT_NOT_NEW_EVIDENCE", required_revision="Preserve source; current v15 interpretation follows actual claim-specific evidence")
    zip_rel = Path("06_MANUSCRIPT_AND_PUBLICATION/01_MANUSCRIPT_SNAPSHOT (1)/CRMT_MANUSCRIPT_SOURCE_v12.zip")
    hashes[zip_rel.as_posix()] = sha(root / zip_rel)
    with zipfile.ZipFile(root / zip_rel) as archive:
        for name in archive.namelist():
            if Path(name).name in {"MANUSCRIPT_ASOC_FULL_v12.tex", "SECTIONS_1_2_ASOC_v12.tex", "SECTIONS_3_12_ASOC_v12.tex"}:
                lines = archive.read(name).decode("utf-8-sig").splitlines()
                candidates = [(i, line) for i, line in enumerate(lines, 1) if len(line) > 100 and any(w in line.lower() for w in ["superior", "contribution", "hypervolume", "adaptive", "confidence"]) and not line.startswith("%")]
                for line_no, exact in candidates[:2]:
                    claims.append({**default, "claim_id": f"MC{len(claims)+1:03d}", "exact_claim_text": exact, "source_file": zip_rel.as_posix()+"!"+name, "source_line": line_no, "manuscript_section": section(lines, line_no), "manuscript_page_if_verified": "", "referenced_table_or_figure": "v12 historical predecessor", "evidence_file": frozen, "experiment_id": "V12-TEXT-LINEAGE", "evidence_verified": "ZIP_MEMBER_SOURCE_EXCERPT_AND_ARCHIVE_HASH_VERIFIED", "scientific_support_level": "PREDECESSOR_TEXT_REQUIRES_CURRENT_SCOPE", "required_revision": "Retain historical source; do not carry unsupported superiority or adaptive claim into v15"})

    for claim in claims:
        if claim["source_file"] == body.as_posix() and claim["source_line"] == 183:
            claim.update(scientific_support_level="LITERATURE_FULL_TEXT_INTERPRETATION_NOT_VERIFIED", evidence_verified="SOURCE_EXCERPT_VERIFIED; listed experiment ledger DOES_NOT_SUPPORT_EXTERNAL_PAPER_PERCENTAGES", required_revision="Remove unverified cross-paper percentages and retain contextual citations pending full-text author review", proposed_revised_claim="These cited papers address different control, scheduling and pricing endpoints; no cross-paper numerical performance claim is made.")
        if claim["experiment_id"] == "CAL-v2-CONDITIONAL-CONTRACT":
            claim["evidence_file"] = evidence([BASE / "03_CALIBRATION/ci_40645435132/SUMMARY.json", BASE / "03_CALIBRATION/ci_40645435132/PREDECLARED_CONFIG.json", Path("03_CODE_AND_CONTROLLER/06_SCIENTIFIC_REMEDIATION_20261028/src/crmt_edge_ems/calibration/conservative_v2.py")])
        src = claim["source_file"]
        if "!" in src:
            archive_path, member = src.split("!", 1)
            with zipfile.ZipFile(root / archive_path) as archive:
                lines = archive.read(member).decode("utf-8-sig").splitlines()
        else:
            lines = (root / src).read_text(encoding="utf-8").splitlines()
        if lines[int(claim["source_line"])-1] != claim["exact_claim_text"]:
            raise ValueError(f"Source excerpt mismatch: {claim['claim_id']}")
    write_csv(output / "MANUSCRIPT_CLAIM_EVIDENCE_MATRIX_VERIFIED.csv", claims, FIELDS)
    write_csv(output / "MANUSCRIPT_TABLE_RESULT_BINDINGS.csv", bindings)
    write_csv(output / "MANUSCRIPT_EVIDENCE_CHECKS.csv", checks)
    receipt = dict(created_at=datetime.now(timezone.utc).isoformat(), claim_count=len(claims), actual_verbatim_source_line_count=len(claims), unavailable_claim_placeholders=0, source_versions=["v12 ZIP members", "v13", "v14"], page_mapping="NOT_ASSERTED; use actual source lines", table_numeric_bindings=len(bindings), table_numeric_bindings_passed=sum(r["passed"] for r in bindings), checks=len(checks), checks_passed=sum(r["passed"] for r in checks), full_original_trajectories_recomputed=False, original_execution_identity_reconstructed=False, evidence_sha256=hashes, manuscript_submission_ready=False, independent_scientific_review=False, limitations=["Verbatim line audit contains compound claims; no claim of exhaustive semantic coverage of every literature sentence", "Historical CSV aggregate verification is not reconstruction of original trajectories", "DOI registry metadata checks do not validate full-text cited interpretations", "Original execution commits not invented where statistical CSVs omit them"])
    (output / "CLAIM_AUDIT_VERIFICATION_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    failures = [r for r in bindings+checks if not r["passed"]]
    print(json.dumps({k:v for k,v in receipt.items() if k != "evidence_sha256"}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(f"{len(failures)} evidence checks failed; inspect CSV before release")


if __name__ == "__main__":
    main()
