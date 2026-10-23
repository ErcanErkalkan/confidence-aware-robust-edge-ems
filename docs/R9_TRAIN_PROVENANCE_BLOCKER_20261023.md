# CRMT R9 — Historical TRAIN source provenance correction and byte-audit gate

**23 October 2026. Status: historical evidence audit only; prospective R9 TEST: NO-GO.** This is a correction of a *derived audit document*, not a modification of any original frozen experiment record.

## 40-condition review

The five historical TRAIN seeds (1001–1005) each have eight conditions (C0/C1 × F0/F1 × A0/A1). All 40 run_summary.json files were directly re-read from their indexed Google Drive source URLs.

- Exactly **39/40** summaries declare the expected original code commit `be5756321617087ca421a639d60a99513f29d889`.
- **1/40** reports `original_git_sha: "UNRECORDED_LOCAL_SHA"` rather than an immutable code commit: **seed1001 / C1_F1_A1**. Source summary: https://drive.google.com/file/d/1_KqvDoiiu0s_1bexxoMhBd9I3kqDwNFc/view
- All 40 summaries declare 256 candidates and 12,600 controller–block TRAIN evaluations. They declare the same OpenCEM source manifest `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.
- For every (seed,C,A) F0/F1 pair, **20/20** run summaries declare the same raw `ledger.csv` SHA-256, but different `candidate_metrics.csv` SHA-256. These are *declarations* in the source summaries, not independent byte verification of all 40 source CSVs.
- F0 native archive counts total 1,672 (mean 83.60); F1 counts total 4,539 (mean 226.95). Their different natural sizes are NOT a matched B-capacity test.

The earlier audit `docs/R9_HISTORICAL_TRAIN_INPUT_AUDIT_TR_20261023.md` said "metadata discrepancies 0", which omitted the source-code provenance check. This assertion **must not be interpreted as 40/40 frozen-commit confirmation**. The present file supersedes that overly broad reading. The historical summary itself stays unchanged.

## Independent source-byte paired pilots: 8 / 20

The existing fail-closed `r9_train_pair_preflight.py` has now been applied to **eight historical F0/F1 pairs** (16 conditions) using original Drive-downloaded TRAIN artifacts, verifying SHA-256 for each of the three CSV source files against each condition's `run_summary.json`, 12,600 unique TRAIN controller–block ledger rows, 256 distinct controllers, archive membership and F0/F1 non-timing science equality. The first pair was verified earlier; the seven subsequent pairs were rechecked with the repository preflight and an additional independent local verifier:

| Pilot pair | Original byte SHA vs source manifest | Ledger identities and order | Four science objectives and all non-CPU fields | Measurement CSV hash | Timing differences |
|---|---|---|---|---|---|
| seed1001/C0_A0 F0 versus F1 | 6/6 CSV PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600 rows; max_cpu_ms: 12,599 rows |
| seed1002/C0_A0 F0 versus F1 | 6/6 CSV PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600 rows; max_cpu_ms: 12,600 rows |
| seed1002/C0_A1 F0 versus F1 (**adaptive allocation**) | 6/6 CSV PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600 rows; max_cpu_ms: 12,600 rows |
| seed1002/C1_A0 | 6/6 PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600; max_cpu_ms: 12,600 |
| seed1002/C1_A1 (**adaptive**) | 6/6 PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600; max_cpu_ms: 12,600 |
| seed1003/C1_A1 (**adaptive**) | 6/6 PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600; max_cpu_ms: 12,600 |
| seed1004/C0_A0 | 6/6 PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600; max_cpu_ms: 12,599 |
| seed1005/C0_A1 (**adaptive**) | 6/6 PASS | PASS | PASS, 12,600 rows | Different | mean_cpu_ms: 12,600; max_cpu_ms: 12,600 |

Non-CPU fields including `cap_violation_pct_total`, `lfp_cycle_loss_pct`, `ramp95_kw_per_min`, and `flip_per_day` are equal for **these eight byte-verified matched pairs**. It is incorrect to infer the same for the **12 unverified pairs**.

Timing columns vary; equality of controller–block simulation budget is **not equality of elapsed time, CPU cost, memory or bootstrap computation**. No inferential F0/F1 performance superiority is established.

## Reproducibility and hard gate

1. `original_git_sha` is required to equal the actual frozen 40-character code SHA. The marker `UNRECORDED_LOCAL_SHA` is rejected. This is exercised explicitly by a new fail-closed unit test in `tests/test_r9_train_pair_preflight.py`. Do **not** silently edit the original historical run_summary to replace the marker with a guessed SHA.
2. Resolve `seed1001/C1_F1_A1` from verifiable independent provenance (execution logs, launch manifest, source snapshot with matching integrity receipts). Otherwise label the historical cell *unresolved* or re-run as a clearly **new** TRAIN result with a locked commit and unmodified prior output.
3. The new equal-B/K/backfill policy remains a draft. Directly trimming or padding old natural archives is not evidence of native F0/F1 equivalence.
4. A scientifically usable new prospective R9 TEST still requires chosen primary hypothesis, prelocked B/K, blinded independent source, non-leakage check, statistical unit, safety veto, and approved protocol before exposure. **G3/G4/G5: NO-GO**.

## Inspectable records

- Full metadata gate (40 conditions, 20 pairs): [GLOBAL_SOURCE_PROVENANCE_GATE_20261023.json](../reproducibility/r9_historical_train_sources_20261023/GLOBAL_SOURCE_PROVENANCE_GATE_20261023.json).
- Exact source summary metadata per seed: `reproducibility/r9_historical_train_sources_20261023/seed100{1..5}_provenance_review.json`.
- Source file URL manifests: `reproducibility/r9_historical_train_sources_20261023/seed100{1..5}.csv`.
- F0/F1 pair summary: [R9_TRAIN_PAIR_SUMMARY_20.csv](../reproducibility/r9_historical_train_sources_20261023/R9_TRAIN_PAIR_SUMMARY_20.csv).
- The eight-pair consolidated receipt: [R9_EIGHT_PAIR_BYTE_AUDIT_RECEIPT.json](../reproducibility/r9_historical_train_sources_20261023/R9_EIGHT_PAIR_BYTE_AUDIT_RECEIPT.json); the seven new repository-preflight JSON receipts are in the same folder. An automated pytest manifest-consistency check independently enforces the declared 8/20 coverage, but does not itself re-download Drive CSV bytes.
- Frozen experiments untouched: `src/crmt_edge_ems`, old 30-seed evidence, R6/R7/R8 historical data.
