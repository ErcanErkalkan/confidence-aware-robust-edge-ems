# SITE_TEMPORAL_SENSITIVITY_STATISTICS_PRELOCK_v1

Date: 2026-09-19  
Status: FROZEN BEFORE SENSITIVITY OUTCOMES

Sensitivity robustness is analyzed with the optimizer seed as the inferential
replication unit.

For every frozen method and every frozen minimization objective, each of the six
predeclared sensitivity conditions is paired with that seed's primary one-shot
internal-test value.

The reported contrast is:

`sensitivity - primary`

For minimized objectives, positive differences mean degradation under the
sensitivity condition and negative differences mean a numerical improvement.

For each method × objective family:

- six two-sided paired Wilcoxon signed-rank tests are computed;
- Holm correction is applied across those six predeclared sensitivity tests;
- paired rank-biserial effect size is reported;
- median paired difference and deterministic 95% percentile-bootstrap CI are
  reported using 10,000 paired seed resamples.

No block-level row is treated as an independent replicate. No sensitivity
variant is selected or omitted based on observed outcomes.
