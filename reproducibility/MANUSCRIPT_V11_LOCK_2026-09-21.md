# Manuscript v11 Provenance Lock — 2026-09-21

This file records the canonical manuscript identities after the figure-correction and placement revision.

## Canonical manuscript

| Artifact | SHA-256 |
|---|---|
| `MANUSCRIPT_ASOC_FULL_v11.pdf` | `5afb80cebee41f14f50232ef38d47b5a3027c8bda6fb1f1ee993adb469e2f220` |
| `ASOC_FULL_MANUSCRIPT_v11_SUBMISSION_READY.zip` | `d5726eccd8ed45050fb06c272bca4f63bf013e2535246be7f3c8559e17fb754f` |
| Figure 1 vector PDF | `b33a4bd6b2d70766a371a44cde4a9fbaaf0825a1211799241abb7b18f3821fd1` |
| Figure 2 vector PDF | `4cc5562c387dec47ed1c3eb30f14c223b775501775c0f2a6b289a2e545a4e451` |
| `ASOC_PORTAL_SUBMISSION_PACKAGE_FINAL_v7.zip` | `93bfabf015a712e4ee4fa3723a8e5292902b329de2fe89adb8dee1a4107d42a2` |

## v11 figure correction

- Figure 1 is a programmatic vector schematic of the executed CRMT order: initial paired replay; four block objectives; mean + 0.50 CVaR_0.90 risk and relative-SE uncertainty; adaptive TRAIN-block allocation until exact budget exhaustion; final paired-bootstrap confidence analysis; final confidence-aware Pareto archive; validation-only representative selection; controller lock; fixed online edge execution.
- Figure 1 is placed immediately after the Introduction contributions and claim boundary.
- Figure 2 is a programmatic vector schematic of the leakage-safe evidence chain: TRAIN generates search sets, validation selects, then internal-test and OPSD OOD data evaluate the locked controller with no retuning/reselection.
- The previous synthetic objective-space schematic and previous AI-generated explanatory raster artwork are not used in the final manuscript.
- Figures 3–7 remain frozen data-derived result figures.

## Scientific integrity

A SHA-256 comparison of 17 checked frozen scientific artifacts (all data-derived result PNGs, result/protocol tables, and the verified bibliography) between v10 and v11 produced 17/17 exact matches and zero mismatches.

The v11 figure and placement revision does not change experiments, seeds, budgets, data splits, controller selections, objective definitions, statistical tests or decisions, reported numerical values, evidence roots, ablation/OOD conclusions, or claim boundaries.

`CLAIM_EVIDENCE_RECONCILIATION_FINAL_v1` remains authoritative.

## Release boundary

The GitHub/Zenodo software archival releases are software/reproducibility records and are not reissued solely for this manuscript-layout revision. This v11 lock updates main-branch manuscript provenance without redefining the frozen software evidence chain.
