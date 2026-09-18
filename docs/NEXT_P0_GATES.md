# Next P0 Gates

The repository is software-regression clean and the OpenCEM data/QA path is now locked.
Confirmatory scientific experiments must still not start until the remaining open gates are closed.

## CLOSED — P0-REALDATA-01 — Immutable OpenCEM acquisition

**Closed 2026-09-18.**

- 19/19 immutable measurement partitions verified.
- upstream commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`
- total verified bytes: `883,382,698`
- expected byte size, Git blob SHA-1 and local SHA-256 are all enforced.

See `docs/OPENCEM_QA_LOCK_v1.md`.

## CLOSED / PARTIAL — P0-REALDATA-02 — QA and cadence lock

Completed:

- verified-data QA;
- per-inverter availability/missingness review;
- duplicate timestamp diagnostics and deterministic order-independent collapse;
- TRAIN-only replay cadence frozen at **2 minutes**;
- 95% complete-day gate;
- chronological block counts frozen;
- cadence-to-physical-time controller mapping wired and regression-tested.

Still open before confirmatory claims:

- explicit sensitivity/validity treatment for upward temporal quantization
  (e.g. 3 min -> 4 min and 5 min -> 6 min at the 2-minute cadence).

## OPEN — P0-SITE-01 — Physical-assumption lock

OpenCEM variables not established by public source documentation must remain explicit assumptions, not inherited silently from the synthetic benchmark.

Freeze, with provenance/rationale:

- battery power limit;
- charge/discharge efficiency;
- SOC limits and initial SOC;
- command-ramp physical assumption;
- import/export cap construction;
- any explicit peak/stress window.

Do not infer these from obviously invalid/sentinel-like raw telemetry.

## OPEN — P0-OPT-01 — Confirmatory optimizer budget

Already locked:

- expensive evaluation unit = `1 controller configuration × 1 predeclared block`;
- optimizer seeds = 1001–1030;
- central `EvaluationLedger` audit implementation.

Still required:

- freeze one numeric total controller-block evaluation budget for Sobol, NSGA-II, MOPSO, MODE and CRMT;
- freeze final baseline hyperparameters before viewing confirmatory results.

## OPEN — P0-EXP-01 — Confirmatory split and holdout discipline

Chronological split definitions and available block counts are locked, but final machine-readable block manifests must be generated and frozen.

Test data must not be used to alter parameter bounds, optimizer settings, objectives, cadence, duplicate policy or method selection.

## OPEN — P0-OOD-01 — External-domain validation

External OOD evaluation (planned Ausgrid adapter) must be treated separately from OpenCEM internal testing. Site scaling and physical assumptions must be explicit.

## OPEN — P0-CLAIM-01 — No premature scientific claims

Pilot, smoke, unit-test, CI, QA, or synthetic-development results are engineering evidence only. Manuscript claims may be promoted only after their corresponding confirmatory evidence gates are closed.
