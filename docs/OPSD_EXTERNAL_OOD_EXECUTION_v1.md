# OPSD_EXTERNAL_OOD_EXECUTION_v1

Date: 2026-09-18  
Status: IMPLEMENTED — LAUNCH TOKEN INTENTIONALLY ABSENT

## Eligibility and anti-leakage prerequisites

The runner accepts only:

1. the exact OPSD package SHA-256 lock;
2. the 1,786-day strict QA inventory lock;
3. the 1,656-day full-regular replay inventory lock;
4. a validation SHA-locked OpenCEM selection;
5. evidence that the same selection already completed its primary one-shot
   OpenCEM internal-test stage.

Internal-test metric values are not read for OOD selection or tuning. The
internal artifact is used only to enforce experiment ordering and immutable
candidate identity.

## External replay design

Every one of the 1,656 locked household-days is evaluated under both frozen
primary OpenCEM site configurations. This yields 3,312 external replay blocks
per selected candidate.

No OPSD-derived battery sizing, grid-cap calibration, controller repair, method
selection, threshold tuning or site scaling is allowed.

## Primary OOD aggregation

The three households contain unequal numbers of full days. Pooled aggregation
would therefore overweight households with more eligible days.

The primary OOD summary is the equal-weight macro average of six independently
risk-aggregated strata:

- residential3 × OpenCEM site 1
- residential3 × OpenCEM site 2
- residential4 × OpenCEM site 1
- residential4 × OpenCEM site 2
- residential6 × OpenCEM site 1
- residential6 × OpenCEM site 2

Within each stratum the frozen CRMT risk functional is used:
mean + 0.50 × empirical CVaR(q=0.90) for the four frozen minimization objectives.

A pooled-all-days risk summary is emitted only as a secondary diagnostic.

## Outputs per seed

- `ood_block_metrics.csv`
- `ood_stratum_risk_summary.csv`
- `ood_macro_risk_summary.csv` (primary)
- `ood_pooled_risk_summary.csv` (secondary)
- `ood_run_summary.json` with source, selection and internal-evidence hashes

## Batch plan

Thirty frozen seeds are split into ten three-seed jobs. The workflow is not
launchable until an explicit token records successful validation-selection and
primary internal-test batch workflow IDs.
