# MANUAL_CONFIRMATORY_PIPELINE_v1

Date: 2026-09-18  
Status: IMPLEMENTED — EXECUTION REQUIRES EXPLICIT MANUAL DISPATCH

The confirmatory OpenCEM pipeline is intentionally split into three manual
GitHub Actions stages so that internal-test data cannot influence optimization
or validation selection.

## Stage 1 — TRAIN optimization

Workflow: `confirmatory-train.yml`

Run one frozen method and seed. The artifact contains the TRAIN-only optimizer
front and exact EvaluationLedger evidence.

## Stage 2 — validation selection

Workflow: `validation-selection.yml`

Inputs are one frozen seed and the five TRAIN workflow run IDs for that seed.

The workflow downloads the exact five artifacts, validates method, seed,
protocol, budget, manifest hash and front-file SHA-256, then evaluates eligible
front candidates on all 118 validation blocks.

It emits `selected_candidates.csv` and `selection_lock.json`. The selection
CSV is SHA-256 locked before any internal-test evaluation.

## Stage 3 — one-shot internal test

Workflow: `internal-test.yml`

Inputs are the same seed and the validation-selection workflow run ID.

The workflow downloads only the selection artifact, verifies its hashes and
protocol, then evaluates exactly the five already-selected candidates on the
78 internal-test blocks.

There is no code path from internal-test output back into candidate selection.

## Execution boundary

All three workflows use `workflow_dispatch`; none runs automatically on push.
The pipeline implementation itself is engineering/protocol evidence, not a
scientific result.
