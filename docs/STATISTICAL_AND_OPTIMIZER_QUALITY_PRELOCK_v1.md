# STATISTICAL_AND_OPTIMIZER_QUALITY_PRELOCK_v1

Date: 2026-09-18  
Status: ANALYSIS METHODS FROZEN BEFORE CONFIRMATORY RESULTS

## Replication unit

The optimizer seed is the inferential replication unit. The frozen registry
contains 30 paired seeds (1001–1030). Block-level rows are not treated as
independent optimizer replicates.

## Selected-candidate internal-test metrics

For each predefined risk objective:

- report mean, standard deviation, median, IQR, minimum and maximum across seeds;
- report a Friedman repeated-measures test across the five methods;
- report all ten paired method comparisons using two-sided Wilcoxon signed-rank tests;
- control the ten pairwise tests within each metric using Holm correction;
- report paired rank-biserial effect size;
- report median paired difference with deterministic 95% percentile-bootstrap CI
  (10,000 paired bootstrap resamples; seed 20260918 plus deterministic offsets).

No pairwise test is selected or omitted based on observed significance.

## Optimizer-quality indicators

Optimizer quality is assessed on validation-re-evaluated TRAIN-front candidates,
not on heterogeneous raw TRAIN estimates.

Within each optimizer seed:

1. pool all five methods' validation candidate objective vectors;
2. normalize each minimization objective using the pooled observed minimum and
   maximum; degenerate dimensions contribute zero;
3. form the nondominated union as the common reference front;
4. calculate for each method:
   - exact dominated hypervolume with normalized reference point (1.10, ..., 1.10);
   - IGD+ to the common nondominated union;
   - unary additive epsilon to the same union;
   - validation nondominated-front size as descriptive information.

Hypervolume is maximized; IGD+ and additive epsilon are minimized. The same
30-seed Friedman/Wilcoxon-Holm/effect-size framework is then applied to the
three quantitative quality indicators.

## Multiplicity boundary

Holm correction is applied separately within each predeclared metric/indicator
family across the ten method pairs. Results are reported with raw and adjusted
p-values; statistical significance alone is not treated as engineering
importance.

## Claim boundary

These are prelocked analysis procedures. Their implementation or unit tests do
not constitute confirmatory evidence.
