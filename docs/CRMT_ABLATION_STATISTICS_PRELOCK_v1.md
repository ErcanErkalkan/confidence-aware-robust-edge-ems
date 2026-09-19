# CRMT_ABLATION_STATISTICS_PRELOCK_v1

Date: 2026-09-19  
Status: FROZEN BEFORE ABLATION HELD-OUT RESULTS

The inferential replication unit is the optimizer seed. The comparison contains
four methods for each of the 30 paired seeds:

- full CRMT;
- NO_CVAR;
- NO_CONFIDENCE;
- NO_ADAPTIVE.

All four are evaluated on the same frozen 78 internal-test blocks using the
primary held-out risk functional q=0.90, tail_weight=0.50.

For each of the four frozen minimization objectives the report contains:

- descriptive mean/std/median/IQR/min/max;
- Friedman repeated-measures test across the four methods;
- all six paired two-sided Wilcoxon signed-rank comparisons;
- Holm correction across those six pairs;
- paired rank-biserial effect size;
- median paired difference with deterministic 95% percentile-bootstrap CI.

The bootstrap uses 10,000 draws and the frozen base statistical seed plus a
300,000 offset. Block-level observations are not treated as independent
replicates.

This analysis is prelocked before ablation held-out outcomes exist.
