# CRMT_ABLATION_PROTOCOL_v1

Date: 2026-09-18  
Status: IMPLEMENTED — ABLATION RESULTS NOT YET GENERATED

Three one-factor-at-a-time CRMT ablations are frozen:

| Ablation | Changed component | Unchanged components |
| --- | --- | --- |
| NO_CVAR | risk tail weight 0.50 → 0.00 | confidence archive, adaptive allocation, candidate pool, seed, budget |
| NO_CONFIDENCE | confidence archive → ordinary Pareto archive on aggregated risk vectors | risk functional, adaptive allocation, candidate pool, seed, budget |
| NO_ADAPTIVE | adaptive allocation → deterministic round-robin allocation | risk functional, confidence archive, candidate pool, seed, budget |

Every ablation uses the same 256-candidate Sobol pool construction, the same
optimizer seed, the same 210 frozen TRAIN blocks and the same 12,600
controller-block budget as full CRMT.

The ablation workflow is manual only. No ablation output is permitted to alter
the primary protocol or candidate-selection rule.
