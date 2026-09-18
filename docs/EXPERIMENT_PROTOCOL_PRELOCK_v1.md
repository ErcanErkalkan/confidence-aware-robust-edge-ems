# EXPERIMENT_PROTOCOL_PRELOCK_v1

Date: 2026-09-18  
Project: Confidence-Aware Robust Edge EMS  
Status: PRELOCK — before confirmatory optimizer results

## Scope

This document freezes the remaining modeling-sensitivity axes and optimizer
hyperparameters before confirmatory OpenCEM optimization is run. It does not
contain controller-performance or optimizer-superiority results.

## Primary OpenCEM model

The primary real-data site factory remains `build_primary_opencem_site()`.

Source-derived hardware/interface facts are kept separate from protocol/model
assumptions. The primary model uses the selected 2-minute TRAIN-only cadence and
the previously frozen TRAIN-q90 grid-stress thresholds.

## One-at-a-time site sensitivities

The following variants are frozen before confirmatory results:

| ID | Change from primary | Purpose |
| --- | --- | --- |
| ETA_LOW_090 | eta_ch=eta_dis=0.90 | lower model-efficiency bound |
| ETA_IDEAL_100 | eta_ch=eta_dis=1.00 | ideal-loss upper bound |
| SOC_CONSERVATIVE_15_95 | hard SOC [0.15, 0.95] | conservative SOC envelope |
| RAMP_HALF | 0.5 × primary command-ramp rate | tighter ramp sensitivity |
| RAMP_QUARTER | 0.25 × primary command-ramp rate | stronger ramp sensitivity |
| TEMPORAL_FLOOR | floor integer-duration mapping | lower bracket for 2-min temporal quantization |

The primary temporal mapping uses ceil quantization. At 2 minutes, 3-minute
mechanisms become 4 minutes and 5-minute mechanisms become 6 minutes. The
TEMPORAL_FLOOR sensitivity gives the opposite bracket: 3 minutes becomes 2 and
5 minutes becomes 4. EMA retention and hold-decay mappings remain exact in
physical time under both policies.

Sensitivity variants are not measured hardware claims. They are applied only
after the candidate/method selection rules are frozen. Internal-test results
must not be used to choose among these variants or retune the controller.

## Baseline optimizer hyperparameters

Frozen values:

- Sobol: batch size 20.
- NSGA-II: population 20; crossover probability 0.90; eta_c=15; eta_m=20.
- MOPSO: swarm 20; archive 100; inertia 0.50; c1=c2=1.50; velocity clip 0.20.
- MODE: population 20; differential weight 0.50; crossover rate 0.90.
- CRMT: initial blocks 4; allocation batch 2; alpha 0.05; 2000 bootstrap draws;
  risk q=0.90; tail weight 0.50.

Optimizer seeds remain 1001 through 1030.

## Budget lock

The fairness unit remains exactly:

`1 controller configuration × 1 predeclared replay block`.

After the real-data runtime preflight, the per-seed, per-method budget is frozen
at **12,600 controller-block evaluations**. With 210 TRAIN blocks this equals 60
complete TRAIN-candidate evaluations for full-block baselines. CRMT receives the
same controller-block budget with a frozen 256-candidate Sobol proposal pool.

See `docs/OPTIMIZER_BUDGET_LOCK_v1.md`.

## Block-manifest rule

The full immutable OpenCEM QA now emits a machine-readable complete-day block
manifest. A block ID has the form:

`opencem:inv<id>:YYYY-MM-DD`

and records inverter ID, local date, split, cadence, tick count, UTC start/end,
and immutable source commit. Only >=95% complete-day blocks can enter this
manifest. The canonical generated manifest is now hash-locked in `reproducibility/manifests/opencem_complete_day_blocks_lock_v1.json`. Confirmatory/runtime tools must regenerate it and fail closed on any SHA-256 mismatch.

## Claim boundary

This is protocol/engineering evidence only. It does not authorize claims of
superiority, robustness, or external generalization.
