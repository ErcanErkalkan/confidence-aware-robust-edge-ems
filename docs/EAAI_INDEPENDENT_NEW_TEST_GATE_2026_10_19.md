# New independent blinded TEST — entry gate not passed (2026-10-19)

No new independent test dataset has yet been identified, frozen, or evaluated. This document is a **prospective methodology proposal**, not a preregistration certificate or test report.

## Before opening any new TEST outcome

1. Freeze source name/version, acquisition/site ID, UTC observation intervals, licensing, timezone and interval conversion, missingness policy, sensor units, hardware/software revisions, SHA-256 for each raw file and canonical block manifest.
2. Exclude all overlap or leakage against 210 TRAIN + 118 historical VALIDATION + 78 previously inspected internal TEST blocks, as well as earlier OPSD replay, including near-duplicate lag and look-ahead windows.
3. Fix all controller candidates and rank ties without TEST outcomes: five seeds, four effective C/A fronts, 20 K20 slots per front; deduplicate to 278 seed–controller pairs. Preserve 20 selected-deployment slots but acknowledge they collapse to 10 distinct seed–controller pairs.
4. Define TEST validity, incomplete/invalid controller evaluation handling, physical simulator and state resets, sampling bias and acceptable extreme out-of-reference values before scoring.
5. Resolve confirmatory inference unit (seeds vs. independent sites/time intervals), one- or two-sided hypotheses, confidence interval, multiple-comparison policy and fixed stopping rule.

## Proposed endpoints

- Primary: held-out four-objective normalized Hypervolume for λ=0.5 K20 fronts; `C1_A1` versus `C0_A0`, paired by optimizer seed, fixed **historical VAL** normalizers and 4D reference point 1.1.
- Secondary: λ=0 HV; IGD+, epsilon with fixed reference sets (133 and 118 historical-VAL nondominated points), individual physical loss profiles, A and C and interaction effects.
- Out-of-VAL-range TEST observations require a predecided, explicitly documented policy; never silently clamp and then claim confirmed results.
- F0/F1 selected candidates and scores are identical. No F-effect inference from this test; separate archive-fidelity experiment required.

## Confidence archive fidelity experiment

Hold candidate pool, evaluation budget and overlapping sampled TRAIN block IDs fixed across F0/F1. Compare false elimination and false retention against prespecified rescored nondomination labels, plus precision/recall, archive stability, calibration, overlapping sample count and run-time/memory. Reference labels based on TRAIN are diagnostic, not independent proof of field benefit.

**State:** NEW TEST BLOCKED / EAAI NO-GO. See [Gate3 status](EAAI_GATE3_2026_10_19_STATUS.md) and the Drive snapshot for the full pretest package.

## New-data and archive-fidelity tooling — 2026-10-19

A **read-only**, fail-closed readiness package is available under [`tools/eaai_newtest_readiness_20261019/`](tools/eaai_newtest_readiness_20261019/README_TR.md). Its candidate inventory checker requires historical exposure windows (210 TRAIN, 118 VAL, 78 previously inspected internal TEST and earlier external/OPSD windows), independently frozen SHA-256 and a *new* source manifest. It refuses raw-file hash changes, temporal overlap and unsupported physical objectives. Output `ELIGIBLE_FOR_MANUAL_REVIEW_ONLY` never authorizes or performs TEST. A separate F archive-fidelity diagnostic accepts only a uniformly rescored four-objective common-candidate reference; it cannot invent a reference or claim F0/F1 performance benefit.

- [Potential external sources and essential limitations](tools/eaai_newtest_readiness_20261019/NEW_TEST_SOURCES_CANDIDATES_TR.md) — Brazil STAR and SOFIE operate in island mode, so applicability to grid import/export constraints must be independently established.
- [Drive package including scripts, 8 synthetic tests and SHA-256 manifest](https://drive.google.com/drive/folders/1jLgWDfmFFBCCW3HrRXnseLNM7N7VzJUu)
- **State:** prospective eligibility **not passed**, new data not acquired, no new blind TEST; EAAI **NO-GO**.

## Historical OpenCEM 406-window provenance (2026-10-20)

The original Drive `canonical_block_manifest.csv` was separately re-hashed and verified against frozen SHA-256 `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`. An audit derived **406 true OpenCEM historical block intervals**, split 210 TRAIN / 118 validation / 78 previously inspected internal TEST; the metadata CSV SHA-256 is `85c295e39f43f0a64d06f720f7486255601f0ffa2486b56661bb98781da37f18`.

- [Historical 406 UTC windows, integrity checker and incomplete evidence status](tools/eaai_newtest_readiness_20261019/historical_406_metadata/README_TR.md)
- [Drive source-derived metadata & audit ZIP](https://drive.google.com/drive/folders/1heNTsoJlum0fuJCCcgk_uoRUTv7P1wux)

**Critical:** This is *metadata only*. The frozen OpenCEM block manifest has **no per-block raw file SHA-256 mapping**, and the prior OPSD/external temporal exposure register is incomplete. The generated CSV intentionally lacks the `raw_sha256` field needed by `pretest_readiness.py` and **must not be passed off as a complete historical registry**. `NEW_TEST_BLOCKED`; no new TEST performed. Source checksum and original evidence preserved.
