# OPSD_OOD_SIGNAL_POLICY_v1

Date: 2026-09-18  
Status: PRELOCKED SIGNAL PROCESSING — OOD PERFORMANCE NOT RUN

## Cohort

Admitted households are exactly residential3, residential4 and residential6.
Each must expose cumulative grid_import, grid_export and pv channels in the
official one-minute schema.

## Native power derivation

The official fields are cumulative kWh. For consecutive exact one-minute
samples:

- import kW = 60 × Δgrid_import_kWh
- export kW = 60 × Δgrid_export_kWh
- PV kW = 60 × Δpv_kWh
- uncontrolled net-grid base kW = import kW − export kW
- reconstructed load kW = base kW + PV kW

An interval is invalid if timestamps are not exactly one minute apart; either
endpoint is marked interpolated for any required channel; a required delta is
non-finite; or a cumulative channel decreases beyond 1e-9 kWh.

Invalid intervals are not clipped or imputed by this project.

## One-minute to two-minute replay

The frozen OpenCEM controller remains at two-minute cadence. OPSD is downsampled
only: each two-minute UTC bin must contain exactly two clean one-minute power
intervals and the replay value is their arithmetic mean.

There is no upsampling, sub-minute reconstruction or project-added interpolation.

## Day eligibility

A UTC day is eligible only if at least 95% of the 720 expected two-minute replay
bins survive the checks above.

The final eligible-day inventory must be generated and hash-locked after the
official package SHA-256 is frozen and before any OOD controller output is
viewed.

## Transfer semantics

The external profile supplies only the disturbance trajectory. Controller
parameters and the OpenCEM hardware/site model remain frozen. External data are
not used to resize batteries, tune thresholds, choose candidates or modify the
selection rule.

Any later OOD claim is limited to profile/domain transfer under the frozen
OpenCEM EMS model, not validation of German household battery hardware.
