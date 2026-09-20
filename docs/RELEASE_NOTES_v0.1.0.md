# Release Notes — v0.1.0

Date: 2026-09-20

This is the first archival release candidate for the closed confirmatory evidence chain supporting the manuscript:

**Confidence-Aware Risk-Calibrated Multiobjective Tuning for Edge Microgrid Energy Management under Distribution Shift**

## Scientific state

The confirmatory evidence chain is closed. This release does not redefine or recompute the frozen experimental results.

Supported interpretation remains bounded to:

- protocol-specific TRAIN approximation-quality comparisons;
- objective-specific internal held-out comparisons;
- objective-specific external-OOD comparisons;
- reproducibility/provenance claims supported by frozen manifests and evidence roots.

The release does not establish universal operational superiority, universal OOD robustness, independent held-out benefit of every CRMT component, certified hard-real-time behavior, or physical battery-lifetime extension.

## Manuscript synchronization

Canonical manuscript line at release preparation:

- Manuscript: `MANUSCRIPT_ASOC_FULL_v7.pdf`
- Manuscript SHA-256: `e43fe60378c128e2b29d8a0b3e2a82c185367183f50cd06f20e4e3f232050292`
- Editable source package: `ASOC_FULL_MANUSCRIPT_v7_SUBMISSION_READY.zip`
- Source SHA-256: `6d1a59fb329a0e1204ccd53a1a003bf0effe4ba08dfad7f239b57a014c6d5b11`
- Portal package: `ASOC_PORTAL_SUBMISSION_PACKAGE_FINAL_v3.zip`
- Portal-package SHA-256: `8719d6177cde36a46c48a2347c9fbcb1a1c3f208d8fdf1e019ced8ff5393e35b`

The manuscript binaries are intentionally not committed to Git history. Their hashes are recorded for provenance.

## Literature-state synchronization

The v7 manuscript contains 24 cited references, including 18 papers from *Applied Soft Computing*. The literature expansion changes positioning and discussion only; it does not alter frozen experimental outputs.

## Frozen confirmatory roots

See `reproducibility/CONFIRMATORY_EVIDENCE_ROOTS_2026-09-20.md`.

## Zenodo preparation

`CITATION.cff` is provided for GitHub citation support and Zenodo-compatible software metadata.

A root-level `.zenodo.json` is intentionally not committed yet because the repository currently has no software license selected. A Zenodo open-access software deposit requires a license choice; that legal/reuse choice must be made explicitly by the author before publication.
