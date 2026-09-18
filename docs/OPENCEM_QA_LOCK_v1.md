# OPENCEM_QA_LOCK_v1

Date: 2026-09-18  
Project: Confidence-Aware Robust Edge EMS  
Status: DATA/QA LOCK — no controller-performance claim

## Immutable source

The OpenCEM measurement snapshot is frozen to upstream commit:

`5884d253a5267fb240b7a8df6fa9e4d49a905167`

The confirmatory ingest manifest contains 19 measurement partitions.

Verified GitHub Actions evidence:

- Full immutable verification + QA workflow run: `35328402398`
- Temporal-mapping regression run: `35328887919`
- Normal regression status after cadence wiring: **55/55 PASS**

## Integrity result

All 19/19 partitions passed:

1. expected byte-size verification;
2. Git blob SHA-1 verification;
3. local SHA-256 recording;
4. single immutable-commit enforcement.

Total verified bytes:

`883,382,698`

Raw measurement rows:

`4,021,635`

Observed inverter IDs:

`1, 2`

Observed UTC coverage:

- minimum: `2025-07-12T13:31:35+00:00`
- maximum: `2026-04-11T18:29:20+00:00`

## Duplicate timestamp semantics

Raw data contains:

- duplicate `(read_ts, inverter)` extra rows: **1,287,290**
- duplicate key groups: **1,287,290**
- maximum key multiplicity: **2**
- replay-signal-exact duplicate extra rows: **774,765**
- replay-signal-conflicting groups: **512,525**

Because conflicting duplicate pairs can contain materially different load/PV telemetry, row-order rules such as `keep=first` or `keep=last` are forbidden.

Frozen collapse rule:

> Before temporal resampling, average available replay-driving load/PV channels within each identical `(read_ts, inverter)` key.

This rule is deterministic, order-independent, preserves exact duplicates, and prevents repeated timestamps from receiving extra weight in a later replay bin.

Rows after timestamp collapse:

`2,734,345`

## TRAIN-only cadence lock

Replay cadence is selected from TRAIN timestamps only.

Frozen train date range:

`2025-07-14` through `2025-12-31`

Candidate grids:

`{1, 2, 5, 10, 15, 30}` minutes

Selected cadence:

**2 minutes**

For both inverters the TRAIN p95 non-outage timestamp gap is 110 seconds.

Validation and internal-test timestamps do not enter cadence selection.

## Complete-day gate and split counts

Daily replay blocks require at least 95% coverage under the selected 2-minute grid.

Complete days:

- inverter 1: **204**
- inverter 2: **202**

Frozen chronological assignment counts:

| Inverter | Train | Validation | Internal test |
| --- | ---: | ---: | ---: |
| 1 | 104 | 59 | 41 |
| 2 | 106 | 59 | 37 |

Peak/stress windows are not inferred from telemetry. Raw reconstructed replay remains neutral (`peak_flag=0`) until a protocol-defined window is explicitly applied.

## Availability observations

The primary served-load channel `outsumw` has low missingness in the full QA:

- inverter 1: approximately 0.064%
- inverter 2: approximately 0.116%

The `pv1power` channel is materially sparser:

- inverter 1: approximately 24.45%
- inverter 2: approximately 28.84%

This supports retaining the explicit complete-day availability gate rather than silently interpolating all missing measurements.

Some battery telemetry contains implausible/sentinel-like values; for example, `battcurr` reaches values around 6553 A. Therefore battery power/ramp/efficiency assumptions must not be inferred directly from unfiltered telemetry.

## 2-minute controller temporal mapping

The selected 2-minute cadence is wired into the real-data controller construction.

Mapped values include:

- `ts_hours = 2/60`
- one-minute physical ramp assumption is multiplied by 2 for per-tick limits;
- `t_min`: target 3 min -> 2 ticks -> achieved 4 min;
- cap-fix hold: target 3 min -> 2 ticks -> achieved 4 min;
- prep hold: target 5 min -> 3 ticks -> achieved 6 min;
- forecast window `w_f`: target 5 min -> 3 ticks -> achieved 6 min;
- horizon: target 10 min -> 5 ticks -> achieved 10 min;
- near-cap window: target 3 min -> 2 ticks -> achieved 4 min;
- `d_lim`: 8 kW/min -> 16 kW/tick;
- FBRL EMA beta: `0.4375`;
- Proposed hold decay: `0.36`.

The upward quantization of 3- and 5-minute mechanisms is explicit. A dedicated sensitivity/validity decision for this quantization remains open before confirmatory claims.

## Claim boundary

This lock establishes data provenance, integrity, replay preprocessing, cadence, and chronological block availability only.

It does **not** establish:

- controller superiority;
- optimizer superiority;
- robustness improvement;
- battery-lifetime improvement;
- real-time deployment certification;
- external-domain generalization.

Those require later confirmatory experiments after the remaining P0 site-assumption, optimizer-budget, quantization-sensitivity, and OOD gates are closed.
