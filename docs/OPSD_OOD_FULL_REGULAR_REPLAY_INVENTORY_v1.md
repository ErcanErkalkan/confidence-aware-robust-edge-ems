# OPSD_OOD_FULL_REGULAR_REPLAY_INVENTORY_v1

Status: IMPLEMENTED — NOT YET LAUNCHED

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
