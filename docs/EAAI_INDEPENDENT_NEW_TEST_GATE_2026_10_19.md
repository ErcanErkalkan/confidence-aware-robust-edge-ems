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
