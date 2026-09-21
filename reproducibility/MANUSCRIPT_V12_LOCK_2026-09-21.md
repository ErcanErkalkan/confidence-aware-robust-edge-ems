# Manuscript v12 Provenance Lock — 2026-09-21

This file records the canonical manuscript identities after the final figure-correction and placement revision.

## Canonical manuscript

| Artifact | SHA-256 |
|---|---|
| `MANUSCRIPT_ASOC_FULL_v12.pdf` | `160133edf019c0849f0c74b02dc905ba249cf308f0c0673b69d841286e8e12b9` |
| `ASOC_FULL_MANUSCRIPT_v12_SUBMISSION_READY.zip` | `78c82ff0fba178807f53d1a9e58478c4b885f24edb8484544d1c6d1b315973a6` |
| Figure 1 vector PDF | `54003d1a4ee0477af1ac0231f7e7a3ebaaa3247084e61358d8ba80077dec041f` |
| Figure 5 cross-stage vector PDF | `2de05f355b7a9a43e6aa23bca5271cc9b44db61e9f49e84a915284872ad4e1c8` |
| `ASOC_PORTAL_SUBMISSION_PACKAGE_FINAL_v8.zip` | `be626a5951c04c503ce0a87fec0a7971904df2a96e73cd5565cd58666ba1d5fd` |

## v12 figure / placement change control

- Figure 1 is a programmatic vector schematic of the executed CRMT workflow: shared initial TRAIN replay, four minimized block objectives, mean + 0.50 CVaR_0.90 risk, relative-SE allocation uncertainty, adaptive TRAIN-block allocation until exact budget exhaustion, final paired-bootstrap confidence-risk dominance, final confidence-aware archive, validation-only representative selection, controller lock, then fixed online execution.
- Figure 1 is placed immediately after the Introduction claim boundary.
- The earlier synthetic objective-space schematic is not used in v12.
- Figure 5 is a programmatic vector cross-stage synthesis placed only after TRAIN, internal-test, and external-OOD results. It reports already frozen CRMT TRAIN medians, the prelocked validation-selection sequence, and only already reported held-out significance statements / non-superiority boundary.
- Figures 2–4 and 6–7 are frozen data-derived result figures.

## Scientific integrity

Seventeen checked frozen scientific artifacts (data-derived result PNGs, result/protocol tables, and the verified bibliography) were SHA-256 compared between v11 and v12: 17/17 exact matches, zero mismatches.

The v12 revision does not change experiments, seeds, budgets, data splits, controller selections, objective definitions, statistical tests or decisions, reported numerical values, evidence roots, ablation/OOD conclusions, or claim boundaries.

`CLAIM_EVIDENCE_RECONCILIATION_FINAL_v1` remains authoritative.

## Archive boundary

Published software release v0.1.0 and GitHub patch release v0.1.1 are not reissued solely for this manuscript-layout revision. Zenodo concept DOI remains `10.5281/zenodo.22862991`; frozen v0.1.0 DOI remains `10.5281/zenodo.22862992`.
