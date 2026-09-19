# OPSD_OOD_STATISTICS_PRELOCK_v1

Date: 2026-09-19  
Status: FROZEN BEFORE OOD PERFORMANCE EXECUTION

## Inferential unit

The optimizer seed is the inferential replication unit. The 3,312 external
replay blocks per candidate and the six household×target-site strata are not
treated as independent optimizer replicates.

## Primary OOD value per method and seed

The primary value for every frozen minimization objective is the already
prelocked equal-weight macro average over six risk-aggregated strata:

- residential3 × target site 1/2
- residential4 × target site 1/2
- residential6 × target site 1/2

The pooled-all-days OOD summary remains diagnostic only and is not used for
primary inferential tests.

## Paired analysis across 30 seeds

For each of the four frozen objectives:

- descriptive mean/std/median/IQR/min/max by method;
- Friedman repeated-measures test across the five methods;
- all ten two-sided paired Wilcoxon signed-rank comparisons;
- Holm correction across the ten pairs within that objective;
- paired rank-biserial effect size;
- median paired difference with deterministic 95% percentile-bootstrap CI.

Bootstrap draws remain 10,000. The OOD report uses the frozen base seed plus a
fixed 200,000 offset so it is deterministic and distinct from the primary
internal-test report.

## Evidence gate

Every seed directory must pass:

- OOD stage/protocol/seed verification;
- hash verification for macro, stratum and pooled OOD CSVs;
- exactly one row per frozen method in the macro summary;
- exactly six primary strata;
- equal-household×target-site macro-weighting label;
- non-empty selection-lock and primary-internal-test evidence hashes;
- identical OPSD package and replay-inventory identities across all seeds.

## Claim boundary

This document freezes analysis mechanics only. It does not state or imply that
one optimizer or controller is superior.
