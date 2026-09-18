# CONFIRMATORY_REPORT_GENERATOR_v1

Date: 2026-09-18  
Status: IMPLEMENTED — NO CONFIRMATORY TABLES GENERATED YET

`tools/opencem_confirmatory_report.py` consumes only hash-verified validation
selection artifacts and their matching one-shot internal-test artifacts.

For every seed it verifies:

- protocol version and seed;
- validation candidate-score SHA-256;
- selected-candidate SHA-256;
- exact selection-lock SHA used by the internal test;
- internal risk-summary SHA-256;
- common immutable OpenCEM block-manifest SHA.

It then generates the exact tables predeclared in
`STATISTICAL_AND_OPTIMIZER_QUALITY_PRELOCK_v1.md`.

The default CLI requires the complete frozen 30-seed registry. The report tool
contains no logic for choosing methods, endpoints, statistical tests, reference
points or multiplicity corrections after observing results.

A separate run-registry artifact will be frozen after the 30-seed execution so
GitHub Actions can collect the exact validation/internal workflow artifacts
without manual file substitution.
