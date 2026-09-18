# Next P0 Gates

The repository is software-regression clean, but confirmatory scientific experiments
must not start until the remaining gates below are closed.

## P0-REALDATA-01 — Immutable OpenCEM acquisition

Acquire all 19 measurement partitions referenced by
`reproducibility/manifests/opencem_git_tree_manifest_v2.csv`.

For every file:

1. verify expected byte size;
2. verify Git blob SHA-1;
3. record local SHA-256;
4. reject partial or mixed-commit inputs;
5. preserve the immutable upstream commit
   `5884d253a5267fb240b7a8df6fa9e4d49a905167`.

No confirmatory result may be produced from an incomplete subset presented as the full
dataset.

## P0-REALDATA-02 — QA and cadence lock

Run `tools/opencem_qa.py` on the verified partitions.

The replay cadence must be selected from TRAIN timestamps only. Validation and test
timestamps must not influence cadence selection. The temporal controller mapping must
then be regenerated with `tools/temporal_mapping_prelock.py`.

## P0-SITE-01 — Physical-assumption lock

OpenCEM variables not established by the public source documentation must remain
explicit assumptions, not inherited silently from the synthetic benchmark.

Freeze, with provenance/rationale:

- battery power limit,
- charge/discharge efficiency,
- SOC limits and initial SOC,
- command ramp limit,
- import/export cap construction,
- any explicit peak/stress window.

## P0-OPT-01 — Confirmatory optimizer budget

Freeze one common expensive-evaluation unit:

`1 controller configuration × 1 predeclared block`.

Freeze the same total controller-block evaluation budget for Sobol, NSGA-II, MOPSO,
MODE, and CRMT. Preserve the prelocked 30 optimizer seeds.

## P0-EXP-01 — Confirmatory split and holdout discipline

Keep chronological train/validation/internal-test separation. Test data must not be
used to alter parameter bounds, optimizer settings, objectives, cadence, or method
selection.

## P0-OOD-01 — External-domain validation

External OOD evaluation (planned Ausgrid adapter) must be treated separately from
OpenCEM internal testing. Site scaling and physical assumptions must be explicit.

## P0-CLAIM-01 — No premature scientific claims

Pilot, smoke, unit-test, CI, or synthetic development results are engineering evidence
only. Manuscript claims may be promoted only after their corresponding confirmatory
evidence gates are closed.
