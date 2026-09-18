# CONFIRMATORY_REPORT_BATCH_EXECUTION_v1

Status: READY — launch token intentionally absent.

The report generator now accepts both direct seed directories and nested
GitHub-Actions batch artifact layouts. It still requires exactly one validation
and one internal-test evidence directory per seed and preserves all existing
SHA-256 checks.

The workflow will only run after a launch token records successful validation
and internal-test batch workflow IDs. Statistical tests and optimizer-quality
metrics remain exactly those frozen in
`STATISTICAL_AND_OPTIMIZER_QUALITY_PRELOCK_v1.md`.
