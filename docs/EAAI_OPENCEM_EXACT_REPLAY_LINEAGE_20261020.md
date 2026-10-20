# EAAI — Frozen OpenCEM historical input lineage (2026-10-20)

**Status: HISTORICAL INPUT RECONSTRUCTION VERIFIED; NO NEW INDEPENDENT TEST; EAAI NO-GO.**

This extension uses the **original 19 sha256-verified OpenCEM CSV partitions** and frozen 406-row source manifest to reproduce the two-minute exogenous PV/load input bins. All 406 daily blocks were matched against the canonical block's **n_ticks and first/last UTC timestamps**.

Verified quantities: 4,021,635 raw records; 2,734,345 distinct (read_ts,inverter) keys; 292,256 eligible two-minute bins across all 406 historical day blocks; 3,853,508 source CSV logical-record to accepted-bin associations. The associated trace records list the original source CSV name, 1-based logical data record number, source timestamp, inverter and bin. Secondary source SHA and row-count audit passed; 4 tests passed.

The independent audit emulates the historical data transformation: duplicate (read_ts,inverter) signals are averaged independently; load prefers outsumw (phase sums are a fallback); PV uses the phase powers; invalid/negative signals are excluded; load and PV are resampled independently to 2-minute bins; complete per-inverter local day grouping uses Asia/Shanghai. No controller performance metrics were recomputed.

- Frozen OpenCEM manifest SHA-256: `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.
- Source commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- **Complete 16 MB reproducibility package**: [Google Drive](https://drive.google.com/file/d/1_DFkvXdHMPROrfid3G8DRrztcwxg0E_J/view).
- ZIP SHA-256: `bc8809c811c8538bde363dccd83f1096a01eb95e41daae3205bdbee1ace3be99`.
- [Drive folder with individual verification code and summary](https://drive.google.com/drive/folders/1EaxvwIDatKfZ9uqrw3eDvmpQ4GmWN5y4).
- Derived status JSON SHA-256: `1d41437e3655acd89f54164535be9f7313e9bc0ebf6618ff5855a948d5cafb6a`.

**Claim boundary:** This is a reconstructed *historical input* and lineage, not proof of byte equality to any earlier serialized controller-side tensor or end-to-end simulator run. A raw record associated with a bin may lack a valid channel. Logical CSV record indices are not physical byte/line offsets. The historic 78 internal-test blocks were already exposed and are not a new blinded test. This extension does not prove F0/F1 confidence value or authorize prospectively independent TEST.

**Synchronization status:** Evidence ZIP and source files are in Drive. GitHub contains this provenance summary; do not infer that the entire ZIP or original 883 MB raw partitions are mirrored into this public GitHub repository.
