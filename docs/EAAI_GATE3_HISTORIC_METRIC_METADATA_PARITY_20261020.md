# EAAI Gate3 historical metric ↔ OpenCEM replay input audit (2026-10-20)

**Historical audit only, seed1001 TRAIN/VAL — NO NEW INDEPENDENT TEST, EAAI NO-GO.**

## Verified source inputs

Canonical OpenCEM 406 block CSV SHA-256: `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.

Reconstructed 292,256 two-minute load/PV bins SHA-256: `4ec69e827fedcbb78f9094f02c8f64a267529c423bc34166185840af86e010c3`.

Eight historical seed1001 Gate3 TRAIN metric files and the seed1001 54-controller historical VALIDATION metric file were rechecked against those source blocks. Each input file was re-hashed; hashes are recorded inside the `HISTORICAL_METRIC_PARITY_STATUS.json` manifest, not improvised here.

## Direct measured evidence

- TRAIN: 8 conditions × 12,600 stored controller–block rows = **100,800** rows; 256 controller proposals per condition.
- Historical VAL (seed1001): 54 × 118 = **6,372** rows, same 118 canonical validation blocks for each selected controller.
- Total historic metric rows audited: **107,172**; **0** unmatched block IDs, n_ticks, site/inverter IDs, split tags, duplicate controller–block keys.
- Reconstructed source bins: **292,256**. `base_kw = load_kw - pv_kw` residual max `8.881784197001252e-16`.
- Four seed1001 paired F0/F1 conditions, 4×12,600 = **50,400 paired rows**, are **identical for all non-CPU metric fields**. CPU timings are not a valid stand-in for confidence archive algorithm overhead.

| C | F | A | Unique TRAIN blocks used across candidates | TRAIN blocks per candidate |
|---|---|---|---:|---|
| 0 | 0/1 | 0 | 50 | 49–50 |
| 0 | 0/1 | 1 | 210 | 24–210 |
| 1 | 0/1 | 0 | 50 | 49–50 |
| 1 | 0/1 | 1 | 210 | 18–210 |

**Important correction:** Although the pool has **210** eligible TRAIN blocks, *each controller was not evaluated on all 210*. There were **12,600**, not 53,760, stored candidate–block evaluations per condition. Variable candidate exposure arises from the stored sampling/allocation design; the 210 blocks are only the eligible pool. Do not treat these records as 256 independent full-train replicates.

The reconstructed bins are numerically finite and follow `base_kw == load_kw-pv_kw` at floating-point precision. The previous controller simulation input tensors were not retained/available for byte or elementwise comparison: **this is a metadata/input-shape audit, not an old simulator tensor equality proof**. The original 78 internal TEST blocks are not touched, and F0/F1 superiority remains unidentifiable.

- [Google Drive archive (Python auditor, 8 synthetic regression tests, CSV/JSON evidence, source hashes)](https://drive.google.com/file/d/1mN-vDyup_qlyaOzbb79piVKHyVZUnQOe/view)
- Archive SHA-256: `9f06824c16ca38ee07422f99217574ad5b6d68e15926a4bdedd21e1520645632`.
- [Original exact-bin lineage experiment](EAAI_OPENCEM_EXACT_REPLAY_LINEAGE_20261020.md).
- [Gate3 common-score historical VAL results](EAAI_GATE3_2026_10_19_STATUS.md).

**Remaining gates:** retrieve serialized historic per-block controller inputs if they exist; complete equal-budget F0/F1 archive fidelity validation with a fixed common rescoring reference; qualify and freeze an independent external data source before new blind TEST. **EAAI NO-GO.**
