# CONFIRMATORY_TRAIN_BATCH_EXECUTION_v1

Date: 2026-09-18  
Status: READY — NOT LAUNCHED BY THIS COMMIT

The batch wrapper changes no scientific protocol. It reduces repeated data I/O
by reconstructing the frozen 210 TRAIN blocks once per job and then executing
multiple frozen seeds through the already-tested single-run implementation.

Execution plan:

- SOBOL: seeds 1001–1030 in one job;
- NSGA-II: seeds 1001–1030 in one job;
- MOPSO: seeds 1001–1030 in one job;
- MODE: seeds 1001–1030 in one job;
- CRMT: five shards of six seeds each.

Every child run still requires exactly 12,600 controller-block evaluations and
writes the same `run_summary.json`, front, and ledger evidence as the manual
single-run workflow.

The workflow is deliberately triggered only by creation/change of
`reproducibility/launch/CONFIRMATORY_TRAIN_BATCH_V1.token`. Adding the workflow
without that token does not launch scientific experiments.
