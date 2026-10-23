# CRMT → EAAI: GitHub/Drive evidence synchronization (2026-10-11)

**Status:** Exploratory revision tracking. **NOT EAAI submission-ready. NOT a new blind confirmatory run.**

## Immutable provenance boundaries

- GitHub `main` head at inspection: `3cc57fb5dbe16f2ed729e91bb505a0f023f7bf8e` (2026-09-21, ASOC v12 documentation).
- Audited Gate2 research head: `b087f15fd795f667a9b86ef13d789344960387dd` (2026-10-09); 18 commits ahead of `main`, 0 behind.
- This editorial branch was created **from that audited research head**, without changing `main`, the older audit branch, the source-code freeze, or the Zenodo release.
- Immutable TRAIN/source-code reference: `be5756321617087ca421a639d60a99513f29d889`.
- OpenCEM source commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- Frozen block inventory SHA-256: `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.
- ASOC v12 PDF SHA-256: `160133edf019c0849f0c74b02dc905ba249cf308f0c0673b69d841286e8e12b9`; the original PDF is **not changed**.

## Gate2: historically verified records, not a new experiment

The 2026-10-09 audit records **150/150 source TRAIN runs**, 30 optimizer seeds × five comparison methods, and **150 SHA-locked TRAIN-only K20 shortlists**, corresponding to 3,000 candidate slots. Among these: 2,193 existing historical validation-cache matches, 805 missing cache entries and two ambiguous repeated-parameter matches, conservatively requiring **807** new or repeated candidate validations. At 118 blocks per candidate, the missing subset implies 95,226 controller–block evaluations; a clean common-environment validation replay requires **354,000** evaluations. The audited 2026-10-09 environment lacked all required raw-data/derived-block-lock source inputs; only preflight and 17/17 local checks were reported. There is **no verified new clean 30-seed Gate2 VAL replay**.

Source: [Gate2 2026-10-09 README](../crmt_eaai_gate2_30seed_20261009/README_TR.md) and [status](../crmt_eaai_gate2_30seed_20261009/STATUS_2026-10-09.md).

## Gate3: 2026-10-11 Drive visibility snapshot (five seed-1001 TRAIN records)

An authenticated listing of the Drive Gate3 TRAIN/seed1001 folder shows five condition folders, each including `run_summary.json`, `ledger.csv`, `optimizer_front.csv`, `candidate_metrics.csv`. The five run summaries self-report 256 candidates, 12,600 TRAIN controller–block evaluations per condition and the frozen block manifest. This is **file-presence plus summary inspection**, not independent recalculation of each CSV checksum, not a new validation or TEST result.

| Condition | CVaR | Confidence | Adaptive | Reported final archive count | Git provenance note |
|---|---|---|---|---:|---|
| `C0_F0_A0` | off | off | off | 143 | Frozen source SHA present |
| `C0_F0_A1` | off | off | on | 29 | Frozen source SHA present |
| `C0_F1_A0` | off | on | off | 250 | Frozen source SHA present |
| `C1_F1_A0` | on | on | off | 249 | Frozen source SHA present |
| `C1_F1_A1` | on | on | on | 236 | **`UNRECORDED_LOCAL_SHA`**; provenance repair required |

The exploratory 8-cell, 5-seed pilot requires 40 TRAIN condition–seed runs: five had visible summary/artifact sets at the time of this audit. Because none has a verified new VAL comparison or new independent TEST, **archive counts are not evidence of objective superiority, and no factorial effect is inferred**. File-presence progress `5/40` is not acceptance of the entire scientific evidence chain.

Drive source: https://drive.google.com/drive/folders/15-fxRdxsS99D22MtnEU7XA9l42FPGGVQ

## Manuscript edits justified now

1. Rename historical HV/IGD+/epsilon as **validation-evaluated approximation-set indicators for TRAIN-generated archives** wherever originally called TRAIN quality; the archived computation uses validation vectors.
2. State equal **TRAIN simulation-budget** parity, not equal complete pipeline cost; all-front VALIDATION expense varies by algorithm. K20 is a proposed/replayed fairness check, not yet a new result.
3. Reclassify old internal-test and OPSD observations as historical evidence available to the revision; not new untouched holdouts.
4. Report that full CRMT and NO_ADAPTIVE selected the same controller in 30/30 original paired seeds; do not claim isolated adaptive advantage.
5. Distinguish upper-\u2308(0.1n) finite-sample tail-average estimator from exact weighted fractional-quantile empirical CVaR.
6. Clarify that Bonferroni control over four objectives in one pairwise decision does not automatically yield simultaneous coverage over the entire archive.
7. Separate the accepted prior EJT **fixed-controller/benchmark** contribution from the new CRMT **offline decision framework**; do not invent final EJT DOI or pages.
8. Preserve original experimental values as **historical ASOC v12 only**. No new Gate2, Gate3, TEST statistical result is asserted.

## Remaining blockers and editorial gate

- Complete verifiable clean 30-seed Gate2 K20 validation replay with source locks, run metadata and exact cost accounting.
- Complete Gate3 experimental matrix, inspect batch/seed-specific checksums and `UNRECORDED_LOCAL_SHA` exception, then VAL analysis with a frozen script.
- Define, lock and evaluate a genuinely **new independent TEST** before any confirmatory generalization claim.
- Confirm full source-level method edge cases and final per-reference bibliographic metadata.
- Rewrite results, discussion, abstract, highlights and conclusions only after such experimental results exist.

**Verdict: EAAI submission NO-GO as of this document.** This file is an editorial synchronization record, not an experiment or a replacement for immutable source data.
