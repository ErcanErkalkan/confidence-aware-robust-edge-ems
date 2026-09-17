# TEMPORAL_PARAMETER_MAPPING_PRELOCK_v1

Date: 2026-09-17
Project: 02_CONFIDENCE_AWARE_ROBUST_EDGE_EMS
Status: PRELOCKED BEFORE REAL-DATA CADENCE IS KNOWN

## Purpose

The frozen controller snapshot was authored at a one-minute sampling interval (`SiteConfig.ts_hours = 1/60`). OpenCEM cadence is selected later from TRAIN timestamps only. If the selected replay cadence is not one minute, raw tick counts and per-tick rates cannot be reused silently.

This prelock defines how temporal semantics are converted to physical time before any confirmatory replay. It does **not** select the OpenCEM cadence and does **not** authorize a real-data result.

## Source snapshot inspected

Frozen controller source under `03_CONTROLLER/02_FIXED_EDGE_EMS/01_SOURCE_SNAPSHOT_2026-09-17/jer_microgrid`:

- `config.py` SHA-256 `c54cb75d454fb99ead7bd19a7b7c9da3b9a13bca30b9ff72b54b873c9bf63efb`
- `controllers.py` SHA-256 `0fe615f10dd12ce2ed69fc876142d17b3bbcfc5b6507f5fdf2ea6e093b372a82`
- `simulation.py` SHA-256 `a67be540b089336d63b2d4001c076048a6aff464dc52a2cb9f94e2ebf20353fa`
- `optimization_refs.py` SHA-256 `8fe1580e328be88a271b377d2ae2538ea2ec9f41a394461a5b4375d93577f3f1`
- `metrics.py` SHA-256 `fea9a667a28637c3d17db3cdf5e3929090cf9ffea71b4bac7ba12064a4f32dee`
- `pipeline.py` SHA-256 `6cb8775851e705f6d258a1e8eda5024f4ebf8443e4ffc739ad72c3a0db13241c`

The one-minute source encodes temporal behavior in more places than `ts_hours` alone.

## Frozen mapping rule

Let `c` be the selected replay cadence in minutes, where `c` must come from `OPENCEM_CADENCE_PRELOCK_v1` and therefore be one of `{1,2,5,10,15,30}`.

### 1. Integration step

`ts_hours = c / 60`.

This value must drive SOC integration, energy throughput and time-based metrics.

### 2. Per-tick rate limits

The one-minute source has:

- `r_max_kw_per_tick = 20`
- `d_lim = 8`

At one minute these encode physical rates of 20 kW/min and 8 kW/min respectively. Preserve those physical rates as:

- `r_max_kw_per_tick(c) = 20 * c`
- `d_lim_kw_per_tick(c) = 8 * c`

The same rule applies to any TRAIN-only sensitivity candidate originally expressed as a one-minute per-tick value: interpret the frozen candidate as a physical per-minute rate and multiply by `c` before replay.

### 3. Integer tick durations/windows

The one-minute source encodes these active physical targets:

- `t_min_ticks = 3` -> 3 min
- Proposed cap-fix hold = `max(1, t_min_ticks)` -> 3 min at the frozen default
- Proposed prep hold = cap-fix hold + 2 ticks -> 5 min at the frozen default
- `w_f = 5` -> 5 min trailing forecast window
- `horizon_k = 10` -> 10 min forecast/MPC horizon
- Proposed near-cap forecast slice `forecast[:3]` -> 3 min

Map each target duration `T` independently as:

`ticks(c) = ceil(T / c)`.

Do **not** implement prep hold as `mapped_cap_ticks + 2`; the `+2` in the frozen source means two **minutes** at the one-minute source cadence, not two arbitrary new-cadence ticks.

The mapper must record both target physical duration and achieved quantized duration (`ticks * c`). If `c > T`, one replay bin is already coarser than the target. That condition must be reported as a coarse-resolution flag and must not be described as exact behavioral equivalence to the one-minute controller.

### 4. FBRL EMA

The frozen FBRL controller computes `beta = 2/(w_ema+1)` with `w_ema=7`, so the one-minute smoothing factor is `beta_1=0.25` and one-minute retention is `0.75`.

Do not map this by simply rounding `7/c` to an integer span. Preserve exponential decay in physical time:

- `retention_c = 0.75^c`
- `beta_c = 1 - retention_c`
- optional equivalent span for reporting: `span_c = 2/beta_c - 1`

If cadence is not one minute, the real-data controller implementation must consume the mapped `beta_c` (or a mathematically equivalent representation) rather than silently forcing an integer `w_ema` approximation.

### 5. Proposed-controller hold decay

The frozen Proposed controller uses `hold_decay = 0.60` once per one-minute tick. Preserve equal physical-time decay:

`hold_decay_c = 0.60^c`.

### 6. Quantities that do not receive a cadence conversion

No direct temporal rescaling is applied merely because cadence changes to:

- SOC thresholds/margins,
- import/export power caps,
- battery nominal energy,
- charge/discharge efficiencies,
- power thresholds and slack thresholds,
- `alpha` itself,
- `lookahead_gain` itself,
- reserve enter/exit SOC margins,
- `prep_slack_gain`, `prep_slack_offset`, `near_cap_*` power/SOC thresholds.

Their scientific values may still require separate real-data assumptions or TRAIN-only calibration, but they are not tick-duration conversions.

### 7. Inactive/dead configuration field

`h_rg_ticks = 10` exists in `SiteConfig`, but no active use was found in the inspected controller/simulation/optimization/metric/pipeline source set. It must not be presented as an active 10-minute mechanism. If later code activates it, its temporal semantics must be added to this mapping before confirmatory replay.

### 8. MPC/reference discretization safeguard

`optimization_refs.py` uses `horizon_k`, per-step ramp constraints, SOC integration through `ts_hours`, and an objective containing unweighted discrete sums plus a command-difference penalty. Changing cadence changes the discretization even when physical horizon is preserved.

Therefore, for non-one-minute confirmatory baselines:

- horizon and ramp constraints must use the physical-time mappings above;
- SOC integration must use mapped `ts_hours`;
- the discrete MPC objective must not be claimed cadence-equivalent until its time-discretization/weight normalization is explicitly frozen and regression-tested, or the relevant weights are re-selected using TRAIN only under the selected cadence.

This safeguard prevents an apparently identical hyperparameter tuple from silently representing a different physical optimization problem.

## Implementation artifact

`08_REPRODUCIBILITY/05_TOOLS/temporal_mapping_prelock.py` implements the cadence-independent mapping rule. Its regression tests are in `08_REPRODUCIBILITY/05_TOOLS/tests/test_temporal_mapping_prelock.py`.

The mapper is a preflight/protocol artifact. It does not mutate the frozen controller snapshot. If selected cadence != 1 minute, confirmatory replay remains fail-closed until the mapped values (including exact EMA beta and hard-coded Proposed-controller temporal constants) are actually wired into the replay controller path and the integration is regression-tested.

## Claim boundary

This prelock is engineering/protocol evidence only. It contains no OpenCEM cadence result, no real-data controller result and no performance claim.
