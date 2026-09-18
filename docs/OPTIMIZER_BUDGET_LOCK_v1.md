# OPTIMIZER_BUDGET_LOCK_v1

Date: 2026-09-18  
Project: Confidence-Aware Robust Edge EMS  
Status: LOCKED BEFORE CONFIRMATORY OPTIMIZER RESULTS

## Fairness unit

One expensive evaluation unit is:

`1 controller configuration × 1 predeclared replay block`

Candidate proposal generation, archive operations, sorting and bootstrap
calculations do not consume this unit. Actual EMS replay does.

## Runtime evidence used only for feasibility planning

GitHub Actions runtime preflight:

- workflow run: `35360236642`
- immutable block-manifest SHA-256:
  `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`
- representative TRAIN blocks: 5 from inverter 1 + 5 from inverter 2
- overall median controller-block wall time: about **0.0588 s**
- overall p95 controller-block wall time: about **0.0742 s**
- maximum observed in the 10-block preflight: about **0.0865 s**
- estimated one full 210-block TRAIN candidate from per-inverter medians:
  about **12.34 s**

These timings are engineering/runtime evidence on one hosted runner. They are
not controller-performance or optimizer-quality results.

## Frozen numeric budget

For every optimizer seed and every method:

`12,600 controller-block evaluations`

TRAIN contains exactly 210 frozen blocks, so the baseline full-candidate capacity
is:

`12,600 / 210 = 60 complete TRAIN candidates`

Population/swarm size is frozen at 20 for NSGA-II, MOPSO and MODE. Therefore
60 complete candidates correspond to exactly three population-equivalents:
initial population plus two further population-equivalents.

Sobol receives the same 12,600 controller-block budget and therefore the same
60 complete TRAIN candidates.

CRMT receives exactly the same 12,600 controller-block budget. Its candidate
proposal pool is frozen at 256 Sobol proposals. Every CRMT candidate receives
the prelocked initial 4 blocks before adaptive allocation. The remaining budget
is allocated by the already frozen confidence/uncertainty mechanism.

## Seeds and total accounting

Optimizer seeds are frozen at 1001–1030 (30 runs).

Per method across all seeds:

`12,600 × 30 = 378,000 controller-block evaluations`

Across Sobol, NSGA-II, MOPSO, MODE and CRMT:

`378,000 × 5 = 1,890,000 controller-block evaluations`

Every run must use a fresh `EvaluationLedger(12600)` and must finish with exact
ledger accounting. No method receives free retries or partial extra generations.

## Claim boundary

The budget was chosen for fairness and computational feasibility before
confirmatory optimizer results. The runtime preflight does not support any claim
about scientific superiority, convergence quality or real-world deployment.
