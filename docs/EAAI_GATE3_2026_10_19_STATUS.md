# EAAI Gate3 extension — status as of 2026-10-19

> **Exploratory historical VALIDATION only — NOT an independent new TEST. EAAI submission: NO-GO.**
>
> This is an **additive EAAI research extension**, not a replacement for the earlier frozen v0.1.0/v0.1.1 software and Applied Soft Computing manuscript evidence described elsewhere in this repository. Nothing in this note redefines an earlier confirmatory release or its frozen source, results, and DOI.

## Locked provenance

- CRMT source snapshot: `be5756321617087ca421a639d60a99513f29d889`
- OpenCEM source commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`
- Canonical OpenCEM manifest: `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`
- Dataset inventory: 210 TRAIN, 118 historical VALIDATION, 78 previously inspected internal-test blocks.
- Original pilot lock: `481e4a23b64fbaf8bb78cc613b2311bbf39f819fedbc68e0efcdceb44253a994`
- Extension lock: `f7f50650b4f7e1c8fbf6b18ae2c56c78f00252e74e6623e6b8080350d6dcc437`

## Design and verified completion

Five optimizer seeds (1001–1005), eight 2×2×2 conditions per seed: C (risk weight), F (archive rule), A (allocation policy). Training: 40/40 cells, 256 proposals/cell, 504,000 total TRAIN controller-block evaluations. TRAIN-only full-pool K20 shortlists: 40/40. **Do not confuse 20 K20 slots with 20 independent physical controllers.**

All five seeds have historical VALIDATION coverage on the same 118 block identities. The post-processed four new seed reports were hash-checked with the following results:

| Seed | Distinct controller identities | Controller–block rows | Final manifest SHA-256 |
|---|---:|---:|---|
| 1001 | 54 | 6,372 | historical seed1001 evidence, see Drive package |
| 1002 | 54 | 6,372 | `9feba8f38742b9769e89e7333635aa3ea8e1d50ad8fbd20c9459ef62cdf7a35a` |
| 1003 | 60 | 7,080 | `b64870b0f8327826d0b8b8a9a86e00f52a5d937507a68c16c4b67fb3413f2be6` |
| 1004 | 59 | 6,962 | `1b5d5611afcf6a773e7d6e8ebe2922ab9cbc5b35d09107d586e0aa182b0dbf19` |
| 1005 | 51 | 6,018 | `b8daf9c584a514a6bb6048f939157eb7b5260929863a25b983f8932d9fec708e` |

The common historical-VAL synthesis contains 1,600 candidate scores (5 seeds × 8 cells × 20 K20 slots × 2 common risk scales, collapsed F-equivalent cells for indicator analysis), 40 Pareto indicator rows, 18 paired descriptive effects, and two pooled normalization references.

Five-seed analysis manifest SHA-256: `a85ed87afdf171dbeea1c9b87e662e65aa3ffaa0b6333e2a06d05f0e7028446e`.

## Honest scientific conclusions

- Across five historical-VAL seeds, adaptive allocation A1 and risk-aware optimization C1 show favorable *descriptive* multi-objective results, but no independent new TEST has been run for this extension.
- **F0 and F1 paired K20 selections and all scored objectives are exactly identical in all five seeds**; there is no identifiable independent F performance effect from these data.
- Seed-level paired effects are descriptive (n=5), not independent sites, prospective preregistration, significance evidence, or proof of transfer.
- Pooled Pareto normalization is historical-VAL-derived and data-dependent. The risk-weight 0 vs. 0.5 normalization scales are different; compare ranks *within* scales only.

## New independent TEST: blocked

A prospective decision-lock proposal has been prepared **without new test acquisition or evaluation**. Current proposed front-level primary endpoint: four-objective normalized HV for λ=0.5 K20 fronts, primary comparison C1_A1 vs C0_A0, common historical-VAL reference, reference point 1.1. It is a proposal, not a completed new-data eligibility gate or external preregistration.

- 400 effective K20 front slots across five seeds × four unique C/A conditions × 20.
- 278 distinct seed–controller pairs for full-front evaluation.
- 20 VAL-selected controller slots but only 10 distinct seed–controller identities.
- Historical 78 internal-test blocks and past OPSD replay must **not** be rebranded as new blind TEST.
- Independent dataset/version, raw checksums, temporal/site leakage test, inference unit, invalid-run policy, and fixed TEST evaluation procedure are required **before opening the new TEST**.

The F mechanism needs a separate equal-budget archive fidelity experiment (false eliminations, false retentions, calibration, and stability) before claiming independent value.

## Storage and synchronization

Current snapshot archive: [Google Drive / EAAI Gate3 2026-10-19](https://drive.google.com/drive/folders/1KKEWjGgn9TiaH9OgyOG3QqQ3S5SBxKlm). It contains the four-CSV evidence ZIP, the source/analysis scripts ZIPs, the PDF review, the manuscript-ready artifacts, the pre-TEST lock package, and a SHA-256 file inventory.

Public GitHub contains provenance and status; **the large raw measurement partitions, local E:\\ working directory, and unpublished full experimental datasets are not asserted to be synchronized here**. Preserve prior scientific locks and release metadata.
