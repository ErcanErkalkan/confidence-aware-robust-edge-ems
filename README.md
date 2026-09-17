# Confidence-Aware Robust Edge EMS

Reproducible research-code workspace for **confidence-aware, risk-calibrated, multi-objective tuning of an edge-executable battery-supported microgrid energy-management system (EMS)**.

This repository is a new project. It does **not** replace or modify the legacy `microgrid-bess` repository or the earlier `microgrid-ems-simulation` work. The fixed EMS controller is retained as a reference implementation, while the CRMT layer, common-budget baseline optimizers, real-data adapters, and reproducibility tooling are organized separately.

## Current scope

The codebase contains:

- `src/crmt_edge_ems/` — normalized parameter space, mean/CVaR risk evaluation, paired confidence dominance, adaptive allocation, robust Pareto archive, auditable evaluation budget, synthetic and replay evaluators, and study runner.
- `src/jer_microgrid/` — frozen fixed edge-EMS/controller snapshot used by the tuning and replay layers.
- `src/baseline_optimizers/` — Sobol, NSGA-II, MOPSO, and MODE comparison implementations using the common evaluation interface.
- `src/data_adapters/` — explicit OpenCEM and Ausgrid adapters; OpenCEM reconstruction uses served AC load and PV to form a battery-free exogenous profile rather than treating measured grid power as an uncontrolled baseline.
- `tools/` — immutable OpenCEM ingest, verification/QA, Windows wrapper, and physical-time temporal mapping prelock.
- `tests/` — unit, integration, budget, replay, data-adapter, ingest/QA, and temporal-mapping regression tests.
- `reproducibility/` — immutable OpenCEM partition manifest and frozen seed registries.
- `docs/` — P0 status, data-ingest blocker note, temporal mapping prelock, and engineering test report.

## Scientific-status boundary

This repository is currently a **P0 engineering/reproducibility artifact**. Passing software tests does not establish scientific superiority, optimizer quality, robustness, or real-world deployment effectiveness. Full confirmatory OpenCEM replay remains blocked until the frozen measurement partitions are acquired, verified, QA-reviewed, and the remaining real-data assumptions/budget locks are frozen.

## OpenCEM data

Raw OpenCEM measurement partitions are intentionally **not included** in this repository. The repository includes an immutable partition manifest and verification tools instead. Raw data should remain outside Git history.

The upstream OpenCEM repository and dataset have their own provenance/licensing. Their licensing does not automatically grant a license for this repository's original research code.

## Install

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Run tests

```powershell
python -m pytest
```

## OpenCEM ingest on Windows

The PowerShell wrapper is under `tools/run_opencem_ingest_windows.ps1`. It is designed to place raw files under the project data area and to verify immutable Git blob SHA-1, expected byte size, and local SHA-256 before QA.

## Reproducibility note

Do not commit downloaded measurement partitions, `.part` files, generated experiment outputs, or ad-hoc results. Confirmatory results should only be produced after all P0 blockers documented in `docs/IMPLEMENTATION_STATUS_P0_v6.md` are closed.

## License

No license has been selected for this repository yet. Do not infer permission to reuse this repository's original code from the licenses of upstream datasets or dependencies.
