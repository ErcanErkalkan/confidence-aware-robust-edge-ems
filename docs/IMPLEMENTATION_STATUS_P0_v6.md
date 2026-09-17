# 00_IMPLEMENTATION_STATUS_P0

Date: 2026-09-17
Project: 02_CONFIDENCE_AWARE_ROBUST_EDGE_EMS
Version: v6

## Closed P0 items

- Canonical `01_MICROGRID_EMS_SIMULATION` controller snapshot isolated from the source project.
- CRMT core implemented: normalized parameter space, mean+CVaR risk, risk-consistent paired confidence dominance, adaptive allocation, robust Pareto archive, budgeted study runner.
- Site-relative power parameterization implemented for cross-site transfer.
- Central `EvaluationLedger` implemented. Fairness unit = one controller configuration evaluated on one block; atomic reservation prevents partial extra batches.
- `LedgeredSyntheticEvaluator` implemented and integrated with `CRMTStudy`; candidate IDs and budget units are auditable end-to-end.
- Real-data `ReplayBlock` / `ReplayEvaluator` implemented with explicit schema guards and the same controller/metric stack as synthetic evaluation.
- OpenCEM source frozen at immutable commit `5884d253a5267fb240b7a8df6fa9e4d49a905167` and tree `5471f4cf87c3d4bcf0fe590c6cad69433cb5535b`.
- OpenCEM Git-tree lock enumerates all 19 measurement partitions with immutable Git blob SHA-1 and byte size; total measurement-partition size is 883,382,698 bytes.
- OpenCEM licensing provenance retained separately: repository LICENSE is MIT; dataset metadata in the README identifies the data license as CC BY 4.0.
- OpenCEM raw semantics frozen: `base_kw = AC load - PV`; `gridpowerw_*` is forbidden as uncontrolled base.
- Primary OpenCEM replay preserves the two documented independent PV-battery subsystems. Cross-inverter aggregation is secondary sensitivity only.
- Raw reconstruction has no inferred tariff/peak window; `peak_flag=0` until an explicit scenario transform is applied.
- Chronological split frozen: train 2025-07-14..2025-12-31; validation 2026-01-01..2026-02-28; internal test 2026-03-01..2026-04-11 (Asia/Shanghai local dates); partial boundary dates excluded.
- OpenCEM replay cadence is no longer assumed to be one minute. `OPENCEM_CADENCE_PRELOCK_v1` freezes a TRAIN-only empirical cadence-selection rule and a >=95% complete-day gate at the selected cadence. Validation/test timestamps do not influence cadence selection.
- Temporal-controller safeguard is locked: if the selected cadence is not one minute, tick-based controller/site timing quantities must be explicitly mapped to physical time with tests, or confirmatory replay fails closed.
- README-supported per-subsystem physical facts locked separately: 8 kW inverter, 200 Ah × 51.2 V nominal battery (10.24 kWh derived), 26 × 480 W PV (12.48 kWp derived).
- Strict OpenCEM SiteModel implemented: undocumented battery power limit, efficiency, SOC envelope, command-ramp limit and grid caps must be supplied explicitly; canonical synthetic defaults cannot silently leak into real-data replay.
- Train-only directional grid-cap calibration rule implemented. It fails closed if either import or export sample support is insufficient.
- Baseline optimizer package implemented: Sobol, NSGA-II, MOPSO and MODE.
- Baseline common-ledger integration verified on synthetic microgrid blocks; exact controller-block budget and same-seed reproducibility are tested.
- Baseline hyperparameter prelock, fairness lock, implementation manifest and existing 30-run seed registry are frozen before confirmatory results.
- Ausgrid adapter implemented but external-OOD artifact remains intentionally unfrozen.
- Immutable OpenCEM ingest tool implemented with resumable `.part` downloads, immutable commit URLs, expected byte-size verification, Git blob SHA-1 verification, and local SHA-256 audit output.
- OpenCEM QA tool implemented with fail-closed verified-partition intake, per-file and per-inverter availability/missingness, duplicate timestamps, power/extreme summaries, TRAIN-only cadence selection, per-inverter complete-day counts and split counts.
- Windows wrapper corrected to canonical path `02_DATA\01_RAW_EXTERNAL\OpenCEM`; tool-local frozen `data_adapters` dependency snapshot is used so QA does not depend on an ambiguous project import path.
- Canonical regression report v5: **36/36 PASS**. New immutable-ingest/QA regression: **10/10 PASS**. These are engineering tests only, not scientific evidence.

## Remaining P0 blockers before confirmatory experiments

1. Download all 19 frozen OpenCEM measurement partitions into `02_DATA/01_RAW_EXTERNAL/OpenCEM` and record local SHA-256 beside the frozen Git blob SHA-1/byte size.
2. Run the frozen QA tool on the complete verified partition set and review the generated report, including selected TRAIN-only replay cadence, per-inverter availability/missingness, duplicates, complete-day counts per split, power-unit/extreme-value audit, and inverter-ID integrity.
3. If the selected replay cadence is not one minute, freeze and regression-test the physical-time mapping for all tick-based controller/site timing quantities before any confirmatory replay.
4. Freeze explicit real-data modeling assumptions not documented by OpenCEM: battery power limit, efficiency, SOC safety envelope, command-ramp constraint; derive/freeze grid caps using the train-only rule.
5. Measure real-data per-block evaluation runtime; only then freeze the common maximum `controller_block_evaluation` budget.
6. Freeze the external OOD Ausgrid artifact and customer/site aggregation rule before the first OOD result is viewed.

## Claim boundary

No scientific superiority, robustness, optimizer-quality, or real-world deployment claim is authorized yet. Pilot/smoke outputs, regression tests, cadence selection, and data-quality reports remain engineering/protocol evidence only.
