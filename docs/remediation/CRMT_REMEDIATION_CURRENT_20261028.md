# CRMT remediation status — 2026-10-28

The local remediation continuation completed a 944/944-event four-block TRAIN engineering rescore, all 6/6 synthetic CAL-v2/v3 scenarios, 1,280 R19 geometry cells and 3,600 paired-power cells, and a 38-page internal v15 manuscript build. The full Python test suite passed 537/537 with pytest capture disabled (`python -m pytest -s -q`).

## Evidence boundary

- The replay rescores a fixed candidate archive; it is not the historical optimizer run or its missing trajectories.
- CAL-v2/v3 comparisons are synthetic stress tests plus historical TRAIN resampling, not independent operational validation of a conditional guarantee.
- R19 remains unapproved, unlocked, and not prospectively executed.
- The v15 PDF is an internal working revision; author approval, independent scientific review, and submission readiness are false.
- Physical meter resolution is unknown. Numerical capacity-tolerance results do not establish physical safety.
- Historical execution provenance, including `seed1001/C1_F1_A1`, remains unresolved.
- No Drive upload/readback or public-GitHub upload of private raw data/trajectory NPZ was performed.

The detailed, hash-bound experiment records and delivery package remain in the local project delivery tree under `10_FINAL_REMEDIATION_AND_VALIDATION/16_CODEX_SCIENTIFIC_REMEDIATION_20261028`; that tree was not uploaded or made part of this public repository.

**Decision:** scientific release **NO-GO**; `CALIBRATION_SCIENTIFICALLY_VALIDATED=false`, `R19_DESIGN_APPROVED=false`, `R19_PROSPECTIVE_EXECUTED=false`, `INDEPENDENT_TEST_EXECUTED=false`, `PHYSICAL_SAFETY_VALIDATED=false`, `HIL_VALIDATED=false`, `FIELD_VALIDATED=false`, and `submission_ready=false`.
