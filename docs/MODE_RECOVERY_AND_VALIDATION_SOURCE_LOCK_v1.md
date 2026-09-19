# MODE_RECOVERY_AND_VALIDATION_SOURCE_LOCK_v1

Date: 2026-09-19  
Status: RECOVERY WORKFLOW PREPARED — VALIDATION NOT YET LAUNCHED

## Why recovery is needed

Original confirmatory TRAIN workflow run `35368457130` completed successfully
for:

- SOBOL seeds 1001–1030;
- NSGA-II seeds 1001–1030;
- MOPSO seeds 1001–1030;
- CRMT seeds 1001–1030 across five shards.

The MODE job had no scientific/code failure. It entered the frozen optimizer and
was terminated by the GitHub Actions job limit after 360 minutes. No MODE
artifact was uploaded.

## Recovery rule

MODE is rerun only, in five six-seed shards:

- 1001–1006
- 1007–1012
- 1013–1018
- 1019–1024
- 1025–1030

Each recovery job checks out the exact original TRAIN code snapshot:

`be5756321617087ca421a639d60a99513f29d889`

Therefore recovery does not inherit later OPSD, reporting, or orchestration code
changes.

The scientific protocol remains:

- method = MODE;
- frozen seed registry 1001–1030;
- 210 TRAIN blocks;
- 12,600 controller-block evaluations per seed;
- identical immutable OpenCEM source/block lock;
- same MODE hyperparameters.

## Validation-source rule

Validation selection will combine:

1. successful artifacts from original run `35368457130` for
   SOBOL/NSGA-II/MOPSO/CRMT; and
2. the successful MODE recovery workflow artifacts.

The existing per-run validation loader still verifies method, seed, protocol,
budget, manifest SHA-256 and optimizer-front SHA-256. A missing or duplicate
method/seed directory fails closed.

No validation or internal-test result is produced by the recovery workflow.
