# Gate3 F archive — seed1001 selected-54 historical VALIDATION diagnostic

**Exploratory selected-cohort analysis, not a full-pool archive accuracy benchmark or independent TEST. EAAI: NO-GO.**

## Frozen source and causal-design check

In frozen source snapshot `be5756321617087ca421a639d60a99513f29d889`, `src/crmt_edge_ems/study.py::CRMTStudy.run` completes all 12,600 TRAIN controller–block evaluations in a condition **before** applying `archive_mode`. F0 (`risk_pareto`) and F1 (`confidence`) therefore do not alter this loop's candidate evaluation allocation. The amended K20-v2 design ranks **all 256** TRAIN candidates instead of using original archive membership, so an independent F effect on the selected physical controllers is not identifiable by that design.

## Recomputed actual historical data, fixed risk q=0.90, λ=0.50

Source is historical seed1001 `C1_F1_A1`:
- TRAIN: 256 candidates, 12,600 controller–block records, frozen CSV SHA-256 `4e6e3975cbb6d52736ebf44de9d7c0d0e5e15641fbfdfdc66348f2e1d5e24c0d`.
- F1 stored TRAIN confidence front: **236/256** records, SHA-256 `01f3423e08e6c2c62df3e1253d3d3f72882b2c129b32de10625a514376b68d8d`.
- F0 reconstructed ordinary risk-Pareto front on the *same F1 TRAIN candidate metrics*: **18/256**, all 18 within the F1 set; 218 retained by F1 beyond ordinary full-pool TRAIN risk Pareto.
- Historical VALIDATION: **54 preselected candidates × 118 common blocks = 6,372 controller–block evaluations**, SHA-256 `01c38d32a2bec841b21a8b139ba0956ff9f9bfd94909b64295fca011f27b33c5`.
- Within **only those 54** historical-VALIDATION candidates, **38** are nondominated for the four objective risk vectors.

| Conditional metric among VAL-preselected 54 | Reconstructed TRAIN F0 | Stored TRAIN F1 |
|---|---:|---:|
| Total original archive (TRAIN 256) | 18 | 236 |
| Of VAL-preselected 54 retained | 18 | 54 |
| Within-selected54 VAL nondominated retained | 13 | 38 |
| Within-selected54 VAL nondominated excluded | 25 | 0 |
| Within-selected54 VAL dominated retained | 5 | 16 |
| Conditional recall | 13/38 = 34.21% | 38/38 = 100.00% |
| Conditional precision | 13/18 = 72.22% | 38/54 = 70.37% |

**Essential limitation:** The historical VAL set of 54/256 was selected using prior TRAIN/K20 criteria. It is not random and the other **202 candidate outcomes are missing**. The within-54 VALIDATION Pareto front is **not** an independent oracle for all 256; 100% F1 recall here is mechanically driven by retaining all 54 selected candidates, not demonstrated confidence calibration or statistical superiority. These metrics are **conditional descriptive statistics only**.

## Reproducibility and open gates

- Full read-only tool with six passing synthetic unit tests, per-candidate historical-VAL membership CSV, summary CSV and hash-locked status JSON: [Google Drive package](https://drive.google.com/file/d/1d0LDGKHt7ZrOpPqGtzFX9UZjYfSk1ETx/view).
- ZIP SHA-256: `50b2e6fe506c33b21cff6c3b018203323bc3798b929adc478575d6d3ba1cd133`.
- All source files remain unchanged; there was **no new evaluation or independent TEST**.
- Necessary next proof: freeze and fully rescore all **256** candidate controls on *the same* block set before comparing false elimination, retention, archive stability and time/memory costs; seed-level replication and independent new-data gate are still needed.
- Original OpenCEM internal 78 TEST blocks and prior OPSD are already exposed and cannot be called fresh blind TEST.

**Submission: NO-GO.**
