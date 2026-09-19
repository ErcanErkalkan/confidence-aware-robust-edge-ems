# CRMT_ABLATION_INTERNAL_BATCH_v1

Status: READY — launch token intentionally absent.

This stage runs only after the CRMT ablation validation-selection batch has
completed. For each ablation and seed it accepts exactly one
SHA-256-locked validation-selected candidate and evaluates it once on the 78
frozen internal-test blocks under the primary held-out risk functional.

Execution matrix: 3 ablations × 5 six-seed shards = 15 jobs.

No internal-test outcome can trigger reselection or retuning.
