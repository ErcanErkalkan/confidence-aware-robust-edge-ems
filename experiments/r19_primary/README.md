# R19 strict engineering path

Implementation: `src/crmt_edge_ems/r19_primary.py`, protocol `CRMT-R19-STRICT-v1-DRAFT`.

Preserved: C1/A1, B=K10, 256 candidates, 12,600 identical DISCOVERY events per arm, empirical mean+0.5 top-10%-tail risk, natural-archive selection, no backfill, discovery-only min–max, L-infinity/L1/lexical tie-break, paired seed-level DeltaMiss = F1−F0. `locked=false`.

`experiments/runner/run.py dry-run` uses artificial loss observations and supplied identical tradeoff archives. It does **not** execute the original F1 algorithm or EMS simulator and is not an R19 experiment. All scientific CLI modes fail closed pending genuine external evidence. Use `select_shortlists` for engineering regression of supplied historical or synthetic inputs only; `audit_fidelity` is explicitly exploratory mathematical scoring.

The historical R19 configuration remains unchanged in the original replay package. The original mean-null/sign-flip assumptions require independent protocol review. Numerical Pareto comparisons in the strict v1 implementation are exact; the historical comparator's 1e-12 tolerance remains in legacy code. Near-machine-precision cases must be settled in the approved protocol before prospective execution.