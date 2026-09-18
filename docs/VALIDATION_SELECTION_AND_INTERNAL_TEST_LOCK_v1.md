# VALIDATION_SELECTION_AND_INTERNAL_TEST_LOCK_v1

Date: 2026-09-18  
Status: PROTOCOL IMPLEMENTED — RESULTS NOT YET GENERATED

## Validation selection

For each frozen optimizer seed, candidate eligibility is limited to the
`optimizer_front.csv` emitted by the TRAIN-only run of each frozen method.

Every eligible front candidate is evaluated on all 118 frozen validation blocks
using the same primary multi-site OpenCEM model and the same risk aggregation
(`q=0.90`, tail weight `0.50`).

The common reference set is the union of all five methods' validation-evaluated
front candidates for that seed. For each minimization objective `j`:

`z_j = (f_j - min_j) / (max_j - min_j)`

If `max_j - min_j <= 1e-12`, the normalized contribution is defined as zero.

The prelocked compromise rule is:

1. minimize equal-weight Chebyshev distance `max_j z_j`;
2. tie-break by `sum_j z_j`;
3. final deterministic tie-break by lexicographic candidate ID.

Exactly one candidate per method is selected. No method is ranked or removed by
this rule; it only chooses a representative candidate within each method.

The resulting `selected_candidates.csv` is SHA-256 locked in
`selection_lock.json`.

## Internal test

`tools/opencem_internal_test.py` accepts only a selection bundle whose:

- protocol version matches;
- selection rule matches;
- block-manifest hash matches;
- selected-candidate CSV hash matches;
- method set contains exactly one candidate for each frozen method.

Only after those checks does it evaluate the five already-frozen candidates on
the 78 internal-test blocks.

Internal-test outcomes cannot modify parameter bounds, optimizer budget,
hyperparameters, candidate identity, validation selection rule, or data splits.

## Claim boundary

This implementation defines the anti-leakage execution protocol. Until the
frozen TRAIN runs, validation selection and one-shot internal test are actually
executed, no performance or superiority claim is authorized.
