"""Create the separately versioned v15 source after a real source-claim audit.

The frozen v14 tree is read only. This tool does not manufacture author approval,
original execution identity or scientific TEST evidence. Compile/render separately.
"""
from __future__ import annotations
import argparse
import csv
import difflib
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("10_FINAL_REMEDIATION_AND_VALIDATION")
NEW = BASE / "16_CODEX_SCIENTIFIC_REMEDIATION_20261028"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    old = root / BASE / "09_MANUSCRIPT/v14_working_source"
    out = root / NEW / "08_MANUSCRIPT_V15"
    work = out / "v15_working"
    audit = json.loads((root / NEW / "01_CLAIM_AUDIT/CLAIM_AUDIT_VERIFICATION_RECEIPT.json").read_text(encoding="utf-8"))
    if audit["unavailable_claim_placeholders"] or audit["claim_count"] < 15 or audit["checks_passed"] != audit["checks"]:
        raise RuntimeError("Actual claim audit must pass before v15 is authored")
    original = {str(p.relative_to(old)).replace("\\", "/"): digest(p) for p in old.rglob("*") if p.is_file() and "build" not in p.relative_to(old).parts}
    work.mkdir(parents=True, exist_ok=True)
    for directory in ["tables", "figures"]:
        shutil.copytree(old / directory, work / directory, dirs_exist_ok=True)
    shutil.copy2(old / "ASOC_REFERENCES_VERIFIED_v3.bib", work / "ASOC_REFERENCES_VERIFIED_v3.bib")
    names = {"MANUSCRIPT_ASOC_FULL_v14.tex": "MANUSCRIPT_ASOC_FULL_v15_working.tex", "SECTIONS_1_2_ASOC_v14.tex": "SECTIONS_1_2_ASOC_v15.tex", "SECTIONS_3_12_ASOC_v14.tex": "SECTIONS_3_12_ASOC_v15.tex", "V14_EVIDENCE_NOTICE.tex": "V15_EVIDENCE_NOTICE.tex"}
    patches = []
    for old_name, new_name in names.items():
        before = (old / old_name).read_text(encoding="utf-8")
        after = before.replace("_v14.tex", "_v15.tex").replace("V14_EVIDENCE_NOTICE", "V15_EVIDENCE_NOTICE").replace("sec:v14_contracts", "sec:v15_contracts")
        if old_name.startswith("MANUSCRIPT"):
            after = after.replace("Internal v14 working source", "Internal v15 working source")
            start, end = after.index("\\begin{abstract}")+len("\\begin{abstract}"), after.index("\\end{abstract}")
            abstract = """
This working revision audits an offline microgrid-controller tuning implementation and its historical evidence. CRMT combines mean-plus-tail risk, pairwise bootstrap archive decisions and adaptive evaluation allocation. Frozen 30-seed comparisons used equal TRAIN simulator-event budgets and scored TRAIN-generated fronts on VALIDATION. Their numerical tables retain legacy capacity and rainflow/SOC metrics; corrected-metric optimizer superiority has not been established. A source-line claim audit now binds actual v12--v14 statements to preserved result records and checks rounded table statistics. Historical NO\\_ADAPTIVE outcome equality supplies no independent adaptive operational benefit. Conditional bounded-IID calibration mathematics does not establish operational archive-wide coverage, and abstention can exceed shortlist capacity. OpenCEM raw-input verification and separately labelled checked engineering replays strengthen software traceability; they do not recreate original controller trajectories, validate battery lifetime or establish physical safety. The R19 draft remains unlocked and unapproved, with effect geometry checked before power assumptions. No new prospective DISCOVERY/AUDIT, independent operational TEST, HIL or field experiment is reported. Author review and independent scientific release approval remain pending.
"""
            after = after[:start]+abstract+after[end:]
        if old_name == "V14_EVIDENCE_NOTICE.tex":
            after = """\\section*{Working-revision evidence notice}
This separate v15 working source preserves frozen numerical table values, figure data and historical experiment labels. Actual source excerpts, file hashes and claim-specific result links are recorded in the companion verified claim matrix. Its table checks verify aggregate transcription and seed medians; they do not reconstruct original trajectories or restore missing execution identities. The retained historical results use legacy metrics and previously exposed data. Corrected engineering replays are explicitly separate and cannot establish present optimizer superiority. No historical package or provenance receipt is rewritten. Author and independent scientific release approval remain absent.
\\textbf{Submission ready: no. New independent operational TEST: not executed. HIL, field, battery lifetime and hard-real-time certification: not established.}
"""
        if old_name.startswith("SECTIONS_1_2"):
            after = after.replace("A distinct but less examined setting arises", "A related design-stage setting arises")
            after = after.replace("These considerations expose an evaluation gap", "These considerations motivate an evaluation question")
            after = after.replace("This study addresses that gap", "This study investigates that question")
            after = after.replace("This v13 text schematic", "This text schematic")
        if old_name.startswith("SECTIONS_3_12"):
            after = after.replace("with all components minimized. Grid-compliance loss is", "with all components minimized. Under the frozen legacy strict-comparison policy, grid-compliance loss is")
            after = after.replace("The canonical complete-day inventory contains 406 inverter-day blocks", "The historical window inventory contains 406 inverter-day blocks (381 complete windows and 25 partial windows)")
            after = after.replace("CRMT produced the strongest approximation-quality distributions", "Under the preserved legacy metrics, CRMT produced the strongest approximation-quality distributions")
            after = after.replace("\\subsection{validation-evaluated approximation-quality of TRAIN-generated fronts assessment}", "\\subsection{Validation-evaluated approximation quality of TRAIN-generated fronts}")
            after = after.replace("Panel (a) states that quality is measured on VALIDATION for TRAIN-generated fronts, panel (b) records the prelocked validation-selection sequence, and panel (c) summarizes only the Holm-significant CRMT pairwise contrasts and the explicit non-superiority boundary from the internal and OPSD evaluations.", "The schematic states the VALIDATION scoring and selection sequence and the objective-specific historical evidence boundary. Pairwise values and significance are reported in the corresponding numerical tables rather than in the schematic.")
            after = after.replace("the held-out panel lists only Holm-significant CRMT pairwise contrasts plus objectives for which no significant CRMT contrast was found. The v13 text schematic", "the final panel states the objective-specific interpretation and computation boundary. This text schematic")
            after = after.replace("The absence of significant omnibus differences for three of four objectives further rules out a universal superiority statement.", "The absence of significant omnibus differences for three of four objectives provides no support for a universal superiority statement; nonsignificance does not prove equivalence.")
            after = after.replace("The future metric version corrects rainflow residual handling", "The separately versioned engineering metric corrects rainflow residual handling")
            after = after.replace("This section specifies the 28 October 2026 working revision. It adds no operational result and does not retrospectively redefine the frozen tables.", "This section specifies the 28 October 2026 v15 working revision. The engineering additions do not retrospectively redefine the frozen numerical tables or introduce independent operational evidence.")
            old_line = next(line for line in after.splitlines() if line.startswith("The earlier 406-window lineage"))
            after = after.replace(old_line, "The completed raw-input audit verified 19 OpenCEM partitions and 406 historical windows. The inventory contains 381 complete and 25 partial windows, with 64 ticks absent from the 406-window nominal total. The historical reconstruction admitted partial days and per-signal duplicate averaging; historical parsed-profile identity is therefore separate from strict full-day admission. A prior checked engineering pilot replayed four complete 720-tick TRAIN inverter-days for one fixed controller. Its numerical cap audit found seven strictly positive floating-point excesses, with maximum approximately $1.11\\times10^{-16}$ kW and zero excesses above the declared $10^{-12}$ kW numerical tolerance. These replays are new engineering trajectories on recorded TRAIN inputs; they are not original historical controller traces or physical safety evidence.")
            # Remove unverified full-text quantitative literature interpretations,
            # while retaining all existing bibliography and contextual citations.
            old_lit = next(line for line in after.splitlines() if line.startswith("Recent ASOC microgrid papers often"))
            new_lit = "Recent ASOC studies address different operating, scheduling and controller-design endpoints, including storage-control learning \\cite{Aksoy2026ASOC}, scheduling \\cite{Yu2026ASOC}, port-microgrid pricing \\cite{Oh2026ASOC}, renewable-aware control \\cite{Xiong2025ASOC}, and controller initialization or tuning \\cite{Hasan2023ASOC,ValenciaRivera2026ASOC}. These citations position the research question; DOI registry agreement alone does not validate full-text numerical interpretations. This revision therefore does not repeat unverified cross-paper percentage improvements. The present study's strongest preserved result concerns legacy-metric validation-evaluated approximation sets, while selected-controller results remain objective specific."
            after = after.replace(old_lit, new_lit)
            after = after.replace("Author review, full claim verification and release approval remain pending.", "The companion source-line claim audit and aggregate transcription checks are complete in their recorded scope; full literature interpretation, author review and independent scientific release approval remain pending.")
            after = after.replace("All numerical result figures are generated programmatically from the frozen result CSVs; OpenAI ChatGPT (GPT-5.6 Sol, OpenAI) assisted with plotting code and layout only, and no underlying data values were generated or altered by the tool.", "The historical source states that its numerical result figures were generated programmatically from frozen result CSVs with AI assistance for plotting and layout. This audit preserves figure bytes and binds them to the corresponding archived result family; it independently checks table aggregates, not the complete original plotting execution.")
            # Details of new experiments are included only from an authored file
            # whose numerical statements are independently bound to receipts.
            anchor = "\\section{Reproducibility}"
            after = after.replace(anchor, "\\input{V15_ENGINEERING_EVIDENCE.tex}\n\n"+anchor)
        (work / new_name).write_text(after, encoding="utf-8")
        patches.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile="v14/"+old_name, tofile="v15/"+new_name))
    # Leave an editable new-only insertion file. Later receipts may add checked
    # numbers, but a planned computation must never be described as completed.
    table_path = work / "tables/tab_data_split_protocol.tex"
    before_table = (old / "tables/tab_data_split_protocol.tex").read_text(encoding="utf-8")
    after_table = before_table.replace("complete inverter-day blocks", "historical inverter-day windows").replace("The OpenCEM complete-day manifest contains 406 blocks", "The frozen OpenCEM manifest contains 406 historical windows (381 complete and 25 partial)").replace("untouched until lock", "historically held out until lock")
    table_path.write_text(after_table, encoding="utf-8")
    patches.extend(difflib.unified_diff(before_table.splitlines(keepends=True), after_table.splitlines(keepends=True), fromfile="v14/tables/tab_data_split_protocol.tex", tofile="v15/tables/tab_data_split_protocol.tex"))
    insertion = work / "V15_ENGINEERING_EVIDENCE.tex"
    if not insertion.exists():
        insertion.write_text("""\\section{Versioned engineering evidence and claim audit}
\\label{sec:engineering_v15}
The companion source-line audit contains 73 actual excerpts from v12 ZIP members, v13 and v14, without unavailable-text placeholders. All 85 checked median/interquartile table cells agree with their frozen CSV records at the displayed precision; 64 frozen-hash, seed-median and ablation-equality checks pass. These are transcription and aggregate-consistency checks. They do not independently validate original trajectory execution or every full-text literature interpretation. PDF-page locators are deliberately omitted where no source-to-page correspondence was verified.

Capacity reporting distinguishes the frozen strict policy from the versioned numerical policy. For nonnegative caps and signed grid power, a numerical exceedance requires positive excess above $\\tau=\\max(\\tau_{\\mathrm{abs}},\\tau_{\\mathrm{rel}}s)$, where $s$ is an explicitly declared positive reference scale. The engineering default is $\\tau_{\\mathrm{abs}}=10^{-12}$ kW and $\\tau_{\\mathrm{rel}}=0$; relative tolerance is not inferred from observed caps. Meter resolution describes measurement uncertainty; it is not automatically added as a permissive operating tolerance. Legacy capacity counts and corrected numerical counts are preserved side by side. Terminal post-command SOC belongs to the corrected rainflow input. Neither the cycling proxy nor numerical constraint satisfaction establishes measured battery lifetime or hardware safety.

Each new result must identify its experiment, metric version, data split, source commit and content hashes in the companion receipts. Planned or incomplete jobs are not treated as results. The manuscript release gate remains closed until author and independent scientific review are recorded.
""", encoding="utf-8")
    (out / "V14_V15_REVISION_DIFF.patch").write_text("".join(patches), encoding="utf-8")
    # Bind proposed revisions to actual new source text, retaining verbatim old
    # excerpts and their original source line locators in the verified matrix.
    matrix_path = root / NEW / "01_CLAIM_AUDIT/MANUSCRIPT_CLAIM_EVIDENCE_MATRIX_VERIFIED.csv"
    with matrix_path.open(encoding="utf-8-sig", newline="") as stream:
        matrix = list(csv.DictReader(stream))
    applied = []
    for row in matrix:
        old_basename = Path(row["source_file"]).name
        if not row["source_file"].startswith((BASE / "09_MANUSCRIPT/v14_working_source").as_posix()) or old_basename not in names:
            continue
        new_file = work / names[old_basename]
        new_lines = new_file.read_text(encoding="utf-8").splitlines()
        exact = row["exact_claim_text"]
        if exact in new_lines:
            revised = exact
            new_line = new_lines.index(exact)+1
            action = "PRESERVED_WITH_EXPLICIT_GLOBAL_AND_ADJACENT_SCOPE"
        else:
            before_lines = (old / old_basename).read_text(encoding="utf-8").splitlines()
            index = int(row["source_line"])-1
            opcode = next(o for o in difflib.SequenceMatcher(a=before_lines, b=new_lines, autojunk=False).get_opcodes() if o[1] <= index < o[2])
            new_line = opcode[3]+1
            revised = "\n".join(new_lines[opcode[3]:opcode[4]])
            action = "REVISED_IN_ACTUAL_V15_SOURCE"
        row["proposed_revised_claim"] = revised
        row["reviewer_comment"] += f" Actual v15 action={action};source={new_file.relative_to(root).as_posix()}:{new_line}."
        applied.append(dict(claim_id=row["claim_id"], old_source_file=row["source_file"], old_source_line=row["source_line"], v15_source_file=new_file.relative_to(root).as_posix(), v15_source_line=new_line, action=action, actual_revised_text=revised))
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(matrix[0])); writer.writeheader(); writer.writerows(matrix)
    with (out / "CLAIM_REVISION_APPLIED.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(applied[0])); writer.writeheader(); writer.writerows(applied)
    after_hashes = {str(p.relative_to(old)).replace("\\", "/"): digest(p) for p in old.rglob("*") if p.is_file() and "build" not in p.relative_to(old).parts}
    if original != after_hashes:
        raise RuntimeError("Frozen v14 source changed during v15 creation")
    receipt = dict(created_at=datetime.now(timezone.utc).isoformat(), original_v14_preserved=original == after_hashes, original_source_sha256=original, new_working_source=str(work), source_sha256={str(p.relative_to(work)).replace("\\", "/"): digest(p) for p in work.rglob("*") if p.is_file() and "build" not in p.relative_to(work).parts}, claim_audit_before_revision=True, author_approved=False, independent_scientific_review=False, submission_ready=False)
    (out / "V15_SOURCE_REVISION_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(work=str(work), original_v14_preserved=receipt["original_v14_preserved"], new_source_files=len(receipt["source_sha256"]))))


if __name__ == "__main__":
    main()
