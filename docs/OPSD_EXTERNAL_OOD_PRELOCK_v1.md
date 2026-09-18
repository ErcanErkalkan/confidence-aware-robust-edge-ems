# OPSD_EXTERNAL_OOD_PRELOCK_v1

Date: 2026-09-18  
Status: ARTIFACT IDENTITY LOCKED — PERFORMANCE NOT RUN

## Why OPSD is the primary external OOD candidate

The Open Power System Data (OPSD) Household Data package version
`2020-04-15` contains measured household load/grid/PV time series from southern
Germany. The official package documents measurements at 1-minute intervals and
publishes a uniform regularized 1-minute series.

This is cadence-compatible with the primary 2-minute OpenCEM controller after a
deterministic 1→2 minute aggregation. It is therefore a stronger mechanism-level
external-domain test than the Ausgrid half-hour dataset.

## Frozen source candidate

- package: Household Data
- version: `2020-04-15`
- fixed URL:
  `https://data.open-power-system-data.org/household_data/opsd-household_data-2020-04-15.zip`
- license expected from datapackage: CC-BY-4.0
- byte size: **156,642,459 bytes**
- SHA-256: `17c41c778bf8ce9a6e483c179664afc66af2e5eddda869e359c719fc037013b3`
- acquisition-only GitHub Actions run: `35375814588`
- immutable machine-readable lock: `reproducibility/manifests/opsd_household_2020-04-15_lock_v1.json`

## Frozen OOD cohort candidate

Only residential households that expose all three required channels in the
official 1-minute schema are admitted:

- `DE_KN_residential3`
- `DE_KN_residential4`
- `DE_KN_residential6`

Required channels for every admitted household:

- `grid_import`
- `grid_export`
- `pv`

Residential1 is not admitted because the published schema lacks a matching
grid-export channel. Residential2 and residential5 are not admitted because the
published schema lacks PV.

## Physical signal reconstruction prelock

The package fields are cumulative energy (kWh). OOD replay must derive interval
power by first differencing cumulative grid import/export at native 1-minute
resolution, then convert kWh/minute to kW.

For the uncontrolled external net-grid profile:

`base_kw = 60 × (Δgrid_import_kWh - Δgrid_export_kWh)`

PV is retained for provenance/QA but is not algebraically re-added to base_kw:
grid import/export already represents the external net-grid exchange and these
households have no battery-storage channel in the admitted cohort.

Negative cumulative-energy deltas, reset boundaries, non-finite deltas and
timestamp discontinuities must be treated as invalid intervals rather than
clipped into plausible values.

## Cadence prelock

- native official processed cadence: 1 minute;
- controller replay cadence: 2 minutes;
- conversion: average valid 1-minute net-power samples in each exact UTC
  2-minute bin;
- no upsampling;
- no synthetic sub-minute interpolation;
- complete-day gate and interpolation-marker policy must be frozen before OOD
  execution.

## Hardware-transfer boundary

The external profiles test disturbance/domain transfer of the already frozen
OpenCEM EMS. They do **not** claim that the German households possess the same
battery/inverter hardware.

No controller parameter, optimizer hyperparameter, battery assumption, selection
rule, or OpenCEM result may be changed from an OPSD outcome.

## Ausgrid role

Ausgrid remains useful as a secondary coarse-cadence stress dataset, but its
native half-hour cadence collapses the 3–10 minute short-horizon mechanisms into
a single coarse tick. It must therefore not be presented as mechanism-equivalent
external validation.

## Next gate

Generate the interpolation-aware eligible-day inventory from this exact locked package, hash-lock that inventory, and only then implement/execute OPSD OOD performance evaluation.
