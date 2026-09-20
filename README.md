# Confidence-Aware Robust Edge EMS

Reproducible research-code workspace for **confidence-aware, risk-calibrated, multi-objective tuning of an edge-executable battery-supported microgrid energy-management system (EMS)**.

This repository is scientifically distinct from the historical `microgrid-bess` and earlier `microgrid-ems-simulation` work. The fixed EMS/controller snapshot is used as a controlled baseline layer, while CRMT, common-budget baselines, real-data adapters, confirmatory workflows, and reproducibility tooling are maintained separately.

## Current scientific status — 2026-09-20

The **confirmatory experimental evidence chain is closed** and the repository is synchronized to the **v0.1.0 archival-release candidate**.

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

Current canonical manuscript revision: **v7**.

- 24 cited references;
- 18 references from *Applied Soft Computing*;
- literature positioning expanded without changing the frozen experimental evidence;
- manuscript/package SHA-256 identities are recorded in `reproducibility/MANUSCRIPT_V7_LOCK_2026-09-20.md`.

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

Release-preparation metadata is documented in:

- `docs/RELEASE_NOTES_v0.1.0.md`
- `docs/ZENODO_RELEASE_PREPARATION_v0.1.0.md`
- `reproducibility/MANUSCRIPT_V7_LOCK_2026-09-20.md`

A Zenodo DOI has **not yet been minted**. The repository is now license- and metadata-ready for the GitHub→Zenodo release flow; the remaining operational step is to enable the repository in the author's Zenodo GitHub integration and publish GitHub release `v0.1.0`.

## License

Copyright © 2026 Ercan Erkalkan.

This software is released under the **MIT License**. See [LICENSE](LICENSE).
