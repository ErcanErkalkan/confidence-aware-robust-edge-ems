# SENSITIVITY_BATCH_EXECUTION_v1

Status: READY — launch token intentionally absent.

This wrapper does not alter the six predeclared site/temporal variants. It
downloads completed validation-selection and primary internal-test evidence,
reconstructs the frozen internal-test blocks once per six-seed shard, and runs
the existing sensitivity implementation.

Every seed must have both a hash-valid selection bundle and the corresponding
primary one-shot internal-test summary before sensitivity analysis is allowed.
No variant may retune or reselect a controller.
