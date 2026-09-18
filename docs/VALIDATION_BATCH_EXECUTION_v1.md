# VALIDATION_BATCH_EXECUTION_v1

Status: READY — launch token intentionally absent.

This layer changes no selection rule. It downloads the completed TRAIN batch
artifacts, reconstructs the frozen 118 validation blocks once per six-seed shard,
and calls the already locked equal-weight Chebyshev selection implementation.

Five shards cover seeds 1001–1030. Each seed still receives an independent
`selection_lock.json` and SHA-256-locked `selected_candidates.csv`.

The workflow can run only after a launch token records a successful TRAIN batch
workflow run ID. No internal-test data are read by this stage.
