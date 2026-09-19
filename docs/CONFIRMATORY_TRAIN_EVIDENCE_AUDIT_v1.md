# CONFIRMATORY_TRAIN_EVIDENCE_AUDIT_v1

Status: IMPLEMENTED BEFORE VALIDATION EXECUTION.

Validation is not allowed to rely only on GitHub workflow conclusions. The
combined original TRAIN artifacts and MODE recovery artifacts must first form an
exact 150-run evidence design:

- 5 frozen methods × 30 frozen seeds;
- one unique directory per method/seed;
- protocol version match;
- exact 12,600 controller-block ledger use;
- 12,600 ledger rows with contiguous ordinals;
- correct method/unit labels;
- exact frozen OpenCEM block-manifest SHA-256;
- 210 TRAIN blocks in every run context;
- optimizer-front, ledger and candidate-evidence SHA-256 verification;
- candidate count = 60 for full-TRAIN baselines and 256 for CRMT.

The audit emits a canonical sorted `train_evidence_index.csv` and its SHA-256.
No validation, internal-test or OOD metric is computed by this gate.
