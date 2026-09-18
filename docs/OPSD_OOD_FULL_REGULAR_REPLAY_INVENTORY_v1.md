# OPSD_OOD_FULL_REGULAR_REPLAY_INVENTORY_v1

Status: LOCKED — OOD PERFORMANCE NOT YET RUN

The base strict inventory allows >=95% daily coverage for QA. The simulator,
however, advances SOC and controller state with a fixed two-minute timestep and
does not expand missing timestamp gaps.

Therefore external OOD performance is restricted further, before viewing any
controller result, to household-days containing exactly all 720 unique
two-minute UTC bins from 00:00 through 23:58.

This is a strict subset of the already hash-locked 1,786-day QA inventory. The
base inventory remains unchanged; this additional gate prevents silent temporal
compression during OOD replay.

The full-regular subset will be hash-locked before any OOD controller execution.


## Locked full-regular result

QA-only workflow run `35376830942` produced the final controller-safe subset:

- total: **1,656 household-days**
- residential3: **458**
- residential4: **505**
- residential6: **693**
- every retained day: exactly **720** unique 2-minute UTC bins
- manifest SHA-256:
  `7e6137adf98a4b5c604fd047891297458b0a2dc606e32f2e8b9e3dba562bea1d`

Machine-readable lock:
`reproducibility/manifests/opsd_ood_full_regular_replay_lock_v1.json`.

External OOD execution must regenerate both the base strict inventory and this
full-regular subset from the exact locked OPSD package and fail closed before
any controller is evaluated.
