# CRMT R18 — Current evidence status (24 October 2026)

**Scope:** Historical, exploratory TRAIN archive/source audit. **Not a new experiment or new independent TEST.**

## Source locations

- [R18 proof package and readable report on Google Drive](https://drive.google.com/drive/folders/13v08AhC4ktFHlxrEDNUQ0_LUt0jye6a-), under the original `02_CONFIDENCE_AWARE_ROBUST_EDGE_EMS/11_PROJECT_CONTROL_20261022/R18_20261024`.
- Historical candidate-front URLs and run summaries: `reproducibility/r9_historical_train_sources_20261023/seed1001.csv` through `seed1005.csv`.
- This update supersedes the **current-coverage reading** of the 2026-10-23 reports. Those reports remain immutable descriptions of what had been checked on that earlier date.

## What R18 newly confirms

All **20/20** F0/F1 paired `optimizer_front.csv` archives have been compared by their original candidate IDs via Google Drive. Across 20 seed/C/A combinations:

| Quantity | Result |
|---|---:|
| Pairs whose F0 candidate-ID set is contained in F1 | 18/20 |
| Pairs with an F0-only candidate | 2/20 |
| Exact F0-only candidate in both exceptions | `CRMT-c0089` |
| Exception 1 | seed1001 / C0 / A0 (F0=143, F1=250, intersection=142) |
| Exception 2 | seed1001 / C1 / A0 (F0=146, F1=249, intersection=145) |
| Natural F0 archive mean | 83.60 |
| Natural F1 archive mean | 226.95 |
| F1 minus F0 size mean | +143.35 |

**Corrected claim:** F1 is *not always* a superset of F0. This corrects blanket statements in previous R15–R16 conversational summaries; original source artifacts remain untouched.

**Evidence tier:** 12 of the 20 pairs have locally packed SHA-256-checked original `optimizer_front.csv` bytes in the R18 ZIP (10 R16 pairs plus 2 R17 pairs). The other 8 pairs were directly compared via their original Drive content but their 16 source CSV bytes are **not** packaged into R18; a fresh local byte audit of those 8 is **not** claimed. Historical separate R9 receipts and R16 10-pair full TRAIN source checks remain distinct.

## Critical remaining blockers (do not relabel as closed)

1. **Original execution SHA:** `seed1001/C1_F1_A1/run_summary.json` still says `UNRECORDED_LOCAL_SHA`. R17 found a later `frozen_repo_head_verified=be5756321617087ca421a639d60a99513f29d889`; this is post-hoc checkout evidence, **not** proof of the Git commit at that historical run's start. Do not edit the original source summary.
2. **R9 design:** Equal native archive capacity, B/K and any backfill, one primary hypothesis and inference unit, meaningful effects, safety thresholds and comparison budget are not prospectively locked. Retrofitting old archives changes the estimand.
3. **New independent, unexposed TEST:** No such eligible raw dataset, verified measurement compatibility/licensing, full OpenCEM+OPSD prior-exposure register, or signed/human-approved preregistration exists. The old 78-block internal OpenCEM TEST and OPSD replay are **historical and exposed**, not a new blind TEST.
4. **Physical deployment / Q1 claims:** No new real-world/HIL safety and computation tests, no demonstrated independent superiority. **EAAI NEW TEST = NO-GO.**

### Important inference boundary

Historical R7/R8 F0/F1 K20 selections were identical across all 20 pairs. Under the same deterministic controller selector and evaluation blocks, identical candidate/controller choices cannot yield an F-only operational outcome difference. Differences in archive memory are not evidence of improved deployed controller quality. R10–R13 synthetic exercises are exploratory diagnostics, not real OpenCEM confirmation.

### Reproduction

Download the linked R18 Drive ZIP; execute `python tools/audit_r18.py` and `python -m unittest discover -s tests -v`. The package includes original, locally SHA-verified CSV evidence for 12 paired fronts, 12 tests, a full 20-pair membership receipt, and fail-closed provenance / prospective-TEST gates.

**Provenance boundary:** Canonical GitHub main is live metadata/code; frozen run code SHA is not redefined by this documentation commit. The original frozen experiment outputs are unchanged.
