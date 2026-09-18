# CRMT_ABLATION_BATCH_EXECUTION_v1

Status: READY — launch token intentionally absent.

The batch layer preserves the three frozen one-factor-at-a-time CRMT ablations
and the same 12,600 controller-block budget. It only reuses reconstructed TRAIN
blocks across six seeds per job.

Execution matrix: 3 ablation families × 5 six-seed shards = 15 jobs. The launch
token is allowed only after the primary confirmatory TRAIN batch completes
successfully.
