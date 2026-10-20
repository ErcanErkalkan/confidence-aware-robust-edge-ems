# Confidence-Aware Robust Edge EMS

Reproducible research-code workspace for **confidence-aware, risk-calibrated, multi-objective tuning of an edge-executable battery-supported microgrid energy-management system (EMS)**.

This repository is scientifically distinct from the historical `microgrid-bess` and earlier `microgrid-ems-simulation` work. The fixed EMS/controller snapshot is used as a controlled baseline layer, while CRMT, common-budget baselines, real-data adapters, confirmatory workflows, and reproducibility tooling are maintained separately.

## EAAI research extension — 2026-10-19 (exploratory, NO-GO)

The newer **EAAI Gate3 extension** is tracked separately from the historical v0.1.0/v0.1.1 release and the older Applied Soft Computing v12 manuscript. Five-seed 2×2×2 TRAIN and K20 selection, 118-block *historical VALIDATION*, and five-seed Pareto indicator analysis have been completed and hash audited. **F0/F1 select identical K20 candidates**; an independent confidence mechanism improvement is not shown. No new independent/blinded TEST has been acquired or executed. EAAI submission remains **NO-GO**.

- [Gate3 experimental status and result boundaries](docs/EAAI_GATE3_2026_10_19_STATUS.md)
- [EAAI Gate3 SHA-256 evidence registry](reproducibility/EAAI_GATE3_2026_10_19_LOCK_REGISTRY.md)
- [Independent NEW TEST prerequisites — BLOCKED](docs/EAAI_INDEPENDENT_NEW_TEST_GATE_2026_10_19.md)
- [Google Drive snapshot: source/analysis tools, archived CSV evidence, reports, LaTeX, pre-TEST lock](https://drive.google.com/drive/folders/1KKEWjGgn9TiaH9OgyOG3QqQ3S5SBxKlm)

The `Current scientific status — 2026-09-21` section below describes the **earlier closed and archived confirmatory evidence chain** and should not be confused with this EAAI extension. Local Windows working directories, raw OpenCEM partitions, and unprovided new data have not been asserted to be automatically mirrored by the new documentation commits.


## New-data and archive-fidelity tooling — 2026-10-19

A **read-only**, fail-closed readiness package is available under [`tools/eaai_newtest_readiness_20261019/`](tools/eaai_newtest_readiness_20261019/README_TR.md). Its candidate inventory checker requires historical exposure windows (210 TRAIN, 118 VAL, 78 previously inspected internal TEST and earlier external/OPSD windows), independently frozen SHA-256 and a *new* source manifest. It refuses raw-file hash changes, temporal overlap and unsupported physical objectives. Output `ELIGIBLE_FOR_MANUAL_REVIEW_ONLY` never authorizes or performs TEST. A separate F archive-fidelity diagnostic accepts only a uniformly rescored four-objective common-candidate reference; it cannot invent a reference or claim F0/F1 performance benefit.

- [Potential external sources and essential limitations](tools/eaai_newtest_readiness_20261019/NEW_TEST_SOURCES_CANDIDATES_TR.md) — Brazil STAR and SOFIE operate in island mode, so applicability to grid import/export constraints must be independently established.
- [Drive package including scripts, 8 synthetic tests and SHA-256 manifest](https://drive.google.com/drive/folders/1jLgWDfmFFBCCW3HrRXnseLNM7N7VzJUu)
- **State:** prospective eligibility **not passed**, new data not acquired, no new blind TEST; EAAI **NO-GO**.

## Current scientific status — 2026-09-21

The **confirmatory experimental evidence chain is closed**. The frozen software release **v0.1.0** is published on Zenodo, and the documentation/provenance synchronization patch release **v0.1.1** is published on GitHub.

Completed stages include:

- equal-budget TRAIN comparison of Sobol, NSGA-II, MOPSO, MODE, and CRMT over 30 seeds;
- frozen validation selection and one-shot internal held-out testing;
- CRMT one-factor ablations (`NO_CVAR`, `NO_CONFIDENCE`, `NO_ADAPTIVE`);
- six predeclared site/temporal sensitivity conditions;
- frozen external Open Power System Data (OPSD) out-of-distribution replay;
- paired nonparametric statistical reporting with multiplicity correction;
- immutable evidence roots and report freezes for each confirmatory stage.

The confirmatory results support a **protocol-specific TRAIN approximation-quality advantage for CRMT**, but held-out internal and external-OOD outcomes remain **objective-specific**. The evidence does **not** establish universal operational superiority, universal OOD robustness, independent held-out benefit of each CRMT component, certified hard-real-time behavior, or physical battery-lifetime extension.

## Manuscript synchronization

The current journal-facing manuscript line is:

**Confidence-Aware Risk-Calibrated Multiobjective Tuning for Edge Microgrid Energy Management under Distribution Shift**

Current canonical manuscript revision: **v12**.

- 33-page manuscript with 24 cited references;
- 18 references from *Applied Soft Computing*;
- 7 manuscript figures: Figure 1 is the corrected vector CRMT workflow; Figures 2–4 and 6–7 are frozen data-derived result figures; Figure 5 is an evidence-safe vector cross-stage synthesis;
- separate programmatic graphical abstract;
- v11→v12 integrity audit: 17/17 checked frozen scientific artifacts SHA-256 identical;
- manuscript/package SHA-256 identities are recorded in `reproducibility/MANUSCRIPT_V12_LOCK_2026-09-21.md`.

The v12 update is a manuscript-only figure-correction and placement revision. Figure 1 is rebuilt from the executed protocol and placed immediately after the Introduction. The former synthetic objective-space schematic is removed; Figure 5 summarizes only already reported frozen TRAIN, validation, internal-test, and external-OOD evidence. No frozen experiment, controller selection, statistical decision, numerical result, data-derived result figure, bibliography entry, or claim boundary is changed.

The manuscript PDF and editable source package are intentionally kept outside Git history. Their hashes provide provenance without allowing manuscript edits to redefine the frozen experiment chain.

## Frozen evidence anchors

- Primary validation root: `6481b5a363fa747a0f193b016105a806cd75827b03b43163715984f9a410610b`
- Primary internal-test root: `e39b4a1de6cfaff859ac54b3aa9c5a3388f89542367d1c2cb2b3b492d3f47100`
- Ablation TRAIN root: `4ef8b3dc4058232c26ab6bf9199fcfc58181e50e97cd157e851735288e47f74b`
- Ablation validation root: `377021e8627bd733411794e24c5f47bd58686e44143ffbe71c3354d9aabda32a`
- Ablation internal root: `7bdc251e57fd37c4eafe053406771991b3c102cacf68dbd04227bd35dd5f11a3`
- Sensitivity root: `7f530634a027e5c6647e93bd7b1cabcfebe34b5d8d3a000b0b359e8801111377`
- OPSD external-OOD root: `4e080b1957f13617f17a91949a553c9ccdc46a32879954bbe0a84f4f58cc808c`

Confirmatory results are bound to their frozen execution snapshots/manifests. Do not treat the newest commit on `main` as a substitute for those evidence locks.

## Current scope

The codebase contains:

- `src/crmt_edge_ems/` — normalized parameter space, mean/CVaR risk evaluation, paired confidence dominance, adaptive allocation, robust Pareto archive, auditable evaluation budget, replay evaluators, and study runners.
- `src/jer_microgrid/` — frozen fixed edge-EMS/controller family used by the tuning and replay layers.
- `src/baseline_optimizers/` — Sobol, NSGA-II, MOPSO, and MODE implementations using the common evaluation interface.
- `src/data_adapters/` — OpenCEM/OPSD-oriented data and replay support.
- `tools/` — ingest, verification, QA, evidence-audit, and workflow-support utilities.
- `tests/` — unit, integration, budget, replay, adapter, ingest/QA, and temporal-mapping regression tests.
- `reproducibility/` — immutable source/seed/manifest material used to bind confirmatory execution.
- `docs/` — engineering, release, and scientific-status documentation.

## Data provenance

Large upstream datasets and generated confirmatory outputs are intentionally not stored in Git history.

### OpenCEM

The frozen OpenCEM chain uses immutable source/provenance manifests and a chronological inventory of:

- 210 TRAIN blocks,
- 118 validation blocks,
- 78 internal-test blocks,
- 2-minute replay cadence.

Raw measurement partitions remain outside Git history.

### OPSD external replay

The external replay uses the locked OPSD household package version `2020-04-15`.

- Package SHA-256: `17c41c778bf8ce9a6e483c179664afc66af2e5eddda869e359c719fc037013b3`
- Frozen replay inventory: 1,656 full-regular household-days
- Seeds: 1001–1030
- External-OOD source run: `35492713949`

The OOD evidence lock is cryptographic provenance, not by itself a claim of general external superiority. Statistical interpretation must follow the frozen OOD report.

## Install

Windows / PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

The package requires Python `>=3.11`; core dependencies are declared in `pyproject.toml`.

## Run tests

```powershell
python -m pytest
```

## Reproducibility boundary

Reproduction should use the frozen data/source manifests, seed registry, run configuration, execution snapshot, and evidence-root checks associated with the target confirmatory stage.

Do not:

- retune or reselect candidates after held-out results are inspected;
- change objective definitions, budgets, seeds, or dataset splits and present the result as the frozen confirmatory chain;
- infer field-deployment, hard-real-time, or electrochemical lifetime guarantees from the simulation/replay evidence;
- treat untracked local data transformations as canonical evidence.

## Citation and archival release

`CITATION.cff` provides machine-readable citation metadata for GitHub. Zenodo-specific metadata is provided in `.zenodo.json`.

Release and archive metadata are documented in:

- `docs/RELEASE_NOTES_v0.1.0.md`
- `docs/RELEASE_NOTES_v0.1.1.md`
- `docs/ZENODO_RELEASE_PREPARATION_v0.1.0.md`
- `docs/ZENODO_ARCHIVE_STATUS.md`
- `reproducibility/MANUSCRIPT_V12_LOCK_2026-09-21.md`

## Archived software DOI

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22862991.svg)](https://doi.org/10.5281/zenodo.22862991)

- Zenodo concept DOI (all versions): **10.5281/zenodo.22862991**
- Frozen v0.1.0 release DOI: **10.5281/zenodo.22862992**
- Published Zenodo record: https://zenodo.org/records/22862992

The v0.1.0 archive is the frozen initial software release associated with the closed confirmatory chain. Patch release v0.1.1 synchronizes documentation, manuscript provenance, and DOI metadata only; it does not redefine the frozen scientific evidence.

## License

Copyright © 2026 Ercan Erkalkan.

This software is released under the **MIT License**. See [LICENSE](LICENSE).

## Historical OpenCEM 406-window provenance (2026-10-20)

The original Drive `canonical_block_manifest.csv` was separately re-hashed and verified against frozen SHA-256 `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`. An audit derived **406 true OpenCEM historical block intervals**, split 210 TRAIN / 118 validation / 78 previously inspected internal TEST; the metadata CSV SHA-256 is `85c295e39f43f0a64d06f720f7486255601f0ffa2486b56661bb98781da37f18`.

- [Historical 406 UTC windows, integrity checker and incomplete evidence status](tools/eaai_newtest_readiness_20261019/historical_406_metadata/README_TR.md)
- [Drive source-derived metadata & audit ZIP](https://drive.google.com/drive/folders/1heNTsoJlum0fuJCCcgk_uoRUTv7P1wux)

**Critical:** This is *metadata only*. The frozen OpenCEM block manifest has **no per-block raw file SHA-256 mapping**, and the prior OPSD/external temporal exposure register is incomplete. The generated CSV intentionally lacks the `raw_sha256` field needed by `pretest_readiness.py` and **must not be passed off as a complete historical registry**. `NEW_TEST_BLOCKED`; no new TEST performed. Source checksum and original evidence preserved.

## Historical source evidence update — 2026-10-20

The [source-level OpenCEM/OPSD audit](docs/EAAI_HISTORICAL_OPSD_OPENCEM_SOURCE_LINKAGE_20261020.md) independently verified original bytes from **19 OpenCEM source CSV partitions**, mapped all **406** historical daily block UTC windows to **434** raw partition/time-overlap edges (378 one-partition blocks and 28 two-partition blocks), and recovered the **original locked GitHub Actions OPSD inventories** covering 1,786 strict QA household-days and 1,656 full-regular historic replay-scope days. These results are documentary and source-level evidence; they do not provide exact per-bin raw lineage, establish exhaustive prior external-use history, or authorize a NEW TEST.

- [Locked original and derived bundle on Google Drive](https://drive.google.com/file/d/1gLhUviFTFeguHNnyyxKXT0YhBHGiCIfj/view)
- ZIP SHA-256: `0ca0f3ae3cd3f777cde38b8666999a9918d867767de88f1c5866712aee2aea6e`; seven source-audit tests passed.
- Prospective new-data eligibility: **BLOCKED**; EAAI: **NO-GO**.
