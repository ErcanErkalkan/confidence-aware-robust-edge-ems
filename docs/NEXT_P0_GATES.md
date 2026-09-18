# Next P0 Gates

The internal OpenCEM pre-run protocol gates are now closed. Confirmatory
optimization may proceed only through the frozen protocol; scientific claims
remain blocked until the confirmatory analyses themselves are completed.

## CLOSED — P0-REALDATA-01 — Immutable OpenCEM acquisition

- 19/19 immutable measurement partitions verified.
- upstream commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`
- total verified bytes: `883,382,698`
- expected byte size, Git blob SHA-1 and local SHA-256 are enforced.

See `docs/OPENCEM_QA_LOCK_v1.md`.

## CLOSED — P0-REALDATA-02 — QA, cadence and temporal semantics

- verified-data QA complete;
- duplicate timestamp policy frozen;
- TRAIN-only cadence = **2 minutes**;
- >=95% complete-day gate frozen;
- cadence-aware controller mapping wired and regression-tested;
- primary integer-duration mapping = ceil;
- temporal-resolution sensitivity = predeclared floor bracketing.

The ceil/floor sensitivity must still be executed as part of the confirmatory
sensitivity analysis, but the pre-run selection rule is no longer open.

## CLOSED — P0-SITE-01 — Physical/model-assumption lock

Source-derived OpenCEM facts used by the model include:

- 10.24 kWh nominal battery energy from 200 Ah × 51.2 V;
- 6.0 kW published battery maximum output;
- 7.68 kW nominal-current charging bound from 150 A × 51.2 V;
- 8 kW inverter rating as an interface upper bound.

Protocol/model assumptions are explicit rather than presented as measured facts:

- eta_ch = eta_dis = 0.95 primary, with 0.90 and 1.00 sensitivities;
- hard SOC envelope [0.10, 1.00], initial SOC 0.50;
- conservative SOC sensitivity [0.15, 0.95];
- primary command ramp is non-binding at the 2-minute cadence, with half/quarter sensitivities;
- grid stress thresholds are TRAIN-only directional q=0.90 values per inverter;
- raw primary replay uses no inferred tariff/peak window (`peak_flag=0`).

See `docs/EXPERIMENT_PROTOCOL_PRELOCK_v1.md`.

## CLOSED — P0-OPT-01 — Confirmatory optimizer fairness/budget

Frozen before confirmatory results:

- unit = `1 controller configuration × 1 frozen block`;
- seeds = 1001–1030;
- baseline hyperparameters;
- CRMT hyperparameters and 256-candidate proposal pool;
- numeric budget = **12,600 controller-block evaluations per seed per method**;
- exact central `EvaluationLedger` accounting.

See `docs/OPTIMIZER_BUDGET_LOCK_v1.md`.

## CLOSED — P0-EXP-01A — Split/block-manifest lock

The complete-day manifest is cryptographically frozen:

- rows: 406;
- TRAIN: 210;
- validation: 118;
- internal test: 78;
- SHA-256:
  `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.

Runtime and confirmatory tools must regenerate this manifest and fail closed if
the hash differs.

## OPEN — P0-EXP-01B — Confirmatory execution

Still to execute:

- 30-seed Sobol/NSGA-II/MOPSO/MODE/CRMT optimization under exact budget;
- execute the implemented TRAIN-front validation selection protocol;
- freeze each seed's `selected_candidates.csv` via `selection_lock.json`;
- execute the implemented one-shot internal-test runner only after selection lock;
- ablations: no CVaR, no confidence-aware dominance, no adaptive allocation;
- predeclared site/temporal sensitivities;
- statistical and optimizer-quality reports from raw outputs.

Internal-test outcomes must not alter parameter bounds, budget, hyperparameters,
objectives, cadence, block membership, duplicate policy or method selection.

## PARTIALLY CLOSED — P0-OOD-01 — External-domain validation

Primary external OOD source is now OPSD Household Data version 2020-04-15.

Closed before any OOD result:
- fixed official package URL/version;
- exact artifact byte size = 156,642,459;
- exact SHA-256 =
  `17c41c778bf8ce9a6e483c179664afc66af2e5eddda869e359c719fc037013b3`;
- cohort = residential3/residential4/residential6;
- required import/export/PV channels;
- cumulative-energy differencing/reset/interpolation policy;
- deterministic 1-minute → 2-minute downsampling;
- no battery/site rescaling from OOD data.

Also closed:
- strict interpolation-aware eligible-day inventory;
- 1,786 locked household-days;
- inventory SHA-256 =
  `740028dbc0be6ec1c9dca1c1e44541c4380044ac86108c8e819e31f24a363ced`.

Still open:
- execute external OOD only from hash-frozen validation selections after the
  confirmatory selection pipeline completes.

Ausgrid is retained only as a secondary coarse-cadence stress dataset, not
mechanism-equivalent validation, because its native cadence is 30 minutes.

## OPEN — P0-CLAIM-01 — Scientific-claim promotion

CI, QA, runtime preflight, smoke tests and synthetic development remain
engineering evidence only. Scientific claims may be promoted only after the
corresponding confirmatory and external-domain evidence is available.
