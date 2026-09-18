# CONFIRMATORY_TRAIN_RUNNER_v1

Date: 2026-09-18  
Status: IMPLEMENTED — FULL CONFIRMATORY RUNS NOT YET LAUNCHED

## Purpose

`tools/opencem_confirmatory_train.py` is the fail-closed, TRAIN-only execution
entry point for the frozen OpenCEM optimizer comparison.

It does not expose validation or internal-test blocks to the optimizer.

## Fail-closed checks

Before optimization, the runner:

1. accepts only previously verified OpenCEM partitions;
2. reconstructs the complete-day inventory;
3. recomputes and verifies the frozen block-manifest SHA-256;
4. requires exactly 210 TRAIN blocks;
5. orders TRAIN blocks by local date and then inverter ID;
6. verifies the first four CRMT blocks cover both physical subsystems;
7. uses inverter-specific SiteConfig objects;
8. accepts only frozen method IDs and seeds 1001–1030;
9. requires exact EvaluationLedger exhaustion.

## Multi-site semantics

OpenCEM inverter 1 and inverter 2 are independent physical subsystems and have
different TRAIN-derived grid-stress thresholds. Every replay block therefore
carries a `site_id`, and the candidate is evaluated using the SiteConfig that
belongs to that subsystem. Normalized controller parameters remain shared
across sites.

## Evidence outputs

Each baseline run writes:

- `candidate_evaluations.csv`
- `optimizer_front.csv`
- `ledger.csv`
- `run_summary.json`

Each CRMT run writes:

- `candidate_metrics.csv`
- `optimizer_front.csv`
- `ledger.csv`
- `run_summary.json`

The summary records the frozen protocol, seed, controller-block budget,
block-manifest hash and SHA-256 values for generated evidence files.

## Execution boundary

The GitHub Actions workflow is manual (`workflow_dispatch`) only. Adding this
runner does not automatically start the 150 frozen method×seed confirmatory runs.

TRAIN optimizer artifacts alone do not establish validation/internal-test
performance, robustness, external generalization or scientific superiority.
