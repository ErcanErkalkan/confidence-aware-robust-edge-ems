# OPSD_OOD_ELIGIBLE_DAY_INVENTORY_v1

Status: IMPLEMENTED — INVENTORY NOT YET LAUNCHED

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
