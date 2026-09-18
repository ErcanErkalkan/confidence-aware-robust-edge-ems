# INTERNAL_TEST_BATCH_EXECUTION_v1

Status: READY — launch token intentionally absent.

This execution wrapper changes no internal-test logic. It downloads the
completed validation-selection batch artifacts, reconstructs the frozen 78
internal-test blocks once per six-seed shard, and calls the existing one-shot
hash-verified internal-test implementation.

Five shards cover seeds 1001–1030. Every seed remains independently bound to its
`selection_lock.json` and `selected_candidates.csv`; a missing, duplicated,
or hash-mismatched selection fails closed.

The workflow can run only after a launch token records a successful validation
batch workflow run ID.
