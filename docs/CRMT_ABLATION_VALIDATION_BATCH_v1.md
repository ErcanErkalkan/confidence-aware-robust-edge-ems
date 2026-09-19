# CRMT_ABLATION_VALIDATION_BATCH_v1

Status: READY — launch token intentionally absent.

For each ablation and seed, this batch layer evaluates the ablation TRAIN front
on the same 118 primary validation blocks, using the **primary held-out risk
functional** and the **primary validation normalization reference** already
frozen for that seed.

Execution matrix: 3 ablations × 5 six-seed shards = 15 jobs.

The workflow requires both:

- successful CRMT ablation TRAIN batch artifacts; and
- successful primary validation-selection batch artifacts.

No internal-test data are available to this stage.
