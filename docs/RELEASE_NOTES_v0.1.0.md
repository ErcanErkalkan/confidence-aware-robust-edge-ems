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

- Manuscript: `MANUSCRIPT_ASOC_FULL_v8.pdf`
- Manuscript SHA-256: `3ccbcfe2640f1adf06f3e545ea5a71174931fa820740242775b08fd81b8afa86`
- Editable source package: `ASOC_FULL_MANUSCRIPT_v8_SUBMISSION_READY.zip`
- Source SHA-256: `f86d4fefde20ffd0940c872ebae4028e421cc19a562c8428d0b6e63f8bc24498`
- Graphical abstract PDF SHA-256: `bb63130fa3bbf0160a698124b369d9f55552d4d1bdf22bdc4225796756e1fa14`
- Graphical abstract TIFF SHA-256: `e014677973f9dde0e80eebfbda376c47dcbae7de45db993479d739d70f4e90f8`
- Portal package: `ASOC_PORTAL_SUBMISSION_PACKAGE_FINAL_v4.zip`
- Portal-package SHA-256: `1c6fe92d682fa30c00b991718bea847fac1269c523391b568faf7a5bfc9b468a`

The manuscript binaries are intentionally not committed to Git history. Their hashes are recorded for provenance.

## v8 visual-evidence synchronization

The v8 manuscript contains 24 cited references (18 from *Applied Soft Computing*) and 8 manuscript figures.

The v8 presentation upgrade adds:
- a programmatic CRMT offline/online architecture schematic;
- a programmatic confirmatory information-flow/controller-lock schematic;
- a programmatic cross-stage synthesis derived only from already frozen reported values;
- a separate programmatic graphical abstract.

The five pre-existing result figures remain byte-identical to v7. A v7→v8 SHA-256 audit confirmed 24/24 checked pre-existing frozen/result artifacts are identical, with zero mismatches. No new experiment or inferential analysis was introduced.

## Frozen confirmatory roots

See `reproducibility/CONFIRMATORY_EVIDENCE_ROOTS_2026-09-20.md`.

## Licensing and Zenodo metadata

The repository is released under the **MIT License**.

- `LICENSE` contains the canonical MIT license text.
- `CITATION.cff` contains GitHub citation metadata.
- `.zenodo.json` contains Zenodo-specific archival metadata.
- `docs/ZENODO_RELEASE_PREPARATION_v0.1.0.md` records the Zenodo release checklist.

## Zenodo release state

Metadata and licensing blockers are closed. A Zenodo DOI has not yet been minted in this repository state. The remaining operational step is to create/publish GitHub release `v0.1.0` after the repository has been enabled in the author's Zenodo GitHub integration. Zenodo will then ingest the release according to the configured integration.
