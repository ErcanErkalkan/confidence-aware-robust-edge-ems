# OPSD_OOD_ELIGIBLE_DAY_INVENTORY_v1

Status: LOCKED — OOD PERFORMANCE NOT YET RUN

This stage reads only the exact SHA-256-locked OPSD package and generates data
eligibility evidence. It does not execute the EMS controller.

For each of residential3/residential4/residential6 it applies the already frozen
signal policy:

1. exact 1-minute cumulative-energy differencing;
2. invalidation of relevant interpolation endpoints, resets, gaps and non-finite
   deltas;
3. exact two-clean-minute averaging to 2-minute replay;
4. UTC day eligibility at >=95% of 720 expected replay bins.

The canonical output is sorted by household/date and includes replay-bin count,
coverage, and first/last timestamp. Its SHA-256 is computed before any OOD
controller result is permitted.

If the strict policy produces zero eligible household-days, the OOD gate fails
closed. The policy will not be relaxed after observing that outcome.


## Locked inventory result

Acquisition-only workflow run `35376222952` regenerated the exact locked OPSD
artifact and produced the strict inventory without running the EMS controller.

- canonical rows: **1,786 household-days**
- residential3: **460**
- residential4: **632**
- residential6: **694**
- manifest SHA-256:
  `740028dbc0be6ec1c9dca1c1e44541c4380044ac86108c8e819e31f24a363ced`
- machine-readable lock:
  `reproducibility/manifests/opsd_ood_eligible_day_inventory_lock_v1.json`

Any external OOD runner must regenerate the inventory from the exact package and
fail closed on row-count or SHA-256 mismatch before executing a controller.
