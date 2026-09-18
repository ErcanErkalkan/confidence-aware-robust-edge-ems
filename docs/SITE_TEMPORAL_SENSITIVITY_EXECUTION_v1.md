# SITE_TEMPORAL_SENSITIVITY_EXECUTION_v1

Date: 2026-09-18  
Status: IMPLEMENTED — SENSITIVITY RESULTS NOT YET GENERATED

The sensitivity suite operates only on candidates already frozen by validation.

Before running, it verifies that:

1. the validation `selection_lock.json` and `selected_candidates.csv` hashes match;
2. a primary `ONE_SHOT_INTERNAL_TEST` artifact exists;
3. that primary internal-test artifact used the exact same selection lock;
4. the immutable OpenCEM block-manifest hash matches.

Only then are the six predeclared one-at-a-time variants evaluated:

- ETA_LOW_090
- ETA_IDEAL_100
- SOC_CONSERVATIVE_15_95
- RAMP_HALF
- RAMP_QUARTER
- TEMPORAL_FLOOR

Every variant evaluates the same five validation-frozen candidates on the same
78 internal-test blocks. No sensitivity outcome can trigger retuning or
candidate reselection.

The manual GitHub Actions workflow requires both the validation-selection run
ID and the primary internal-test run ID to enforce this execution order.
