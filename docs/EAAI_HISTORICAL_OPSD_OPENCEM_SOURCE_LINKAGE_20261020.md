# EAAI Gate3 — Historical OPSD/OpenCEM provenance extension (2026-10-20)

> **Historical-source audit, not a new blind TEST. EAAI remains NO-GO.** This file is additive. It does not modify the earlier Zenodo releases, the EAAI historical VALIDATION, fixed source snapshots, or the 78 previously inspected internal TEST blocks.

## Verified source artifacts

- Frozen OpenCEM source commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- Frozen 406-row canonical day/block manifest SHA-256: `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.
- All **19 original raw OpenCEM CSV partition files** (`data/measurements/YYYY-MM-[a,b].csv`) were byte-verified to the preexisting 19/19 acquisition verification record. The combined 19-partition set has two inverter streams per file, so a daily block cannot be assumed to belong to exactly one monthly partition.
- Frozen OPSD QA inventory Actions artifact **10559764058** (run 35376222952), ZIP SHA-256 `621df950a9de904ca83c90f88e6993cbdc72a8829964a03f1d4b97228b4947d3`, included manifest SHA-256 `740028dbc0be6ec1c9dca1c1e44541c4380044ac86108c8e819e31f24a363ced`.
- Frozen OPSD 720-bin/day replay inventory Actions artifact **10559814800** (run 35376830942), ZIP SHA-256 `0be8f053855dc9e144974b2504d1cd9359c15877986bd0b4b47a02b59013d2ef`, included manifest SHA-256 `7e6137adf98a4b5c604fd047891297458b0a2dc606e32f2e8b9e3dba562bea1d`.
- Locked OPSD source package SHA-256 `17c41c778bf8ce9a6e483c179664afc66af2e5eddda869e359c719fc037013b3`, version `2020-04-15`. This *existing source package hash* was read from the frozen manifests, not recomputed from the 156 MB ZIP in this audit.

## Measured evidence (2026-10-20 source-level run)

| Scope | Verified result |
|---|---|
| OpenCEM 406 historical daily blocks | 210 TRAIN + 118 historical VALIDATION + 78 previously inspected internal TEST |
| OpenCEM input partitions rehashed | 19/19 |
| Blocks with observed raw `read_ts`/inverter records in same UTC interval | **406/406** |
| Raw partition–block temporal overlap edges | **434** |
| Block linked to one source CSV | 378 |
| Block linked to two source CSVs | 28 |
| Source partitions in the frozen set but unused by the 406 UTC blocks | 2025-07-a.csv and 2025-07-b.csv |
| OPSD QA household-days | **1,786** |
| Full 720-bin OPSD replay-eligible household-days | **1,656** |
| Other QA-eligible household-days not in replay subset | 130 |
| OPSD households | residential3 (458 replay days), residential4 (505), residential6 (693) |
| OPSD historical QA window coverage range | 2015-10-28T00:00:00Z to 2018-04-08T00:00:00Z (exclusive upper bound; coverage need not be continuous) |
| Synthetic regression tests for audit package | **7/7 passed** |
| Independent new TEST outcome | **NOT RUN** |

## Locked derived CSV identities

- `OPENCEM_406_BLOCK_PARTITION_TEMPORAL_LINKS.csv`: `9d8402aff85579c61d1f98309c039ae6fe948e42cfdfb24a387c4bc593c762a1`
- `OPENCEM_RAW_PARTITION_LINKAGE_EDGES.csv`: `9e6c78e90a381b026295a2d854c1bbca1e942b770709e85f569113e2d3adbca5`
- `OPENCEM_19_RAW_PARTITIONS_VERIFIED.csv`: `20ef265740197e0f7cf92d6fc9a3153dc4ff8dc226d0824589146016003129ae`
- `OPSD_1786_PRIOR_EXPOSURE_WINDOWS.csv`: `da82858abbed8c69413c870046d41d72aa7adee97c7da4d44a16f7ce21fc108e`

Published immutable evidence package ZIP SHA-256:
`0ca0f3ae3cd3f777cde38b8666999a9918d867767de88f1c5866712aee2aea6e`.

Google Drive original evidence bundle: [OpenCEM-OPSD historical source linkage](https://drive.google.com/file/d/1gLhUviFTFeguHNnyyxKXT0YhBHGiCIfj/view). The ZIP contains the Python source mapping implementation, source frozen manifests and Actions inventory ZIP files, CSVs, tests, SHA-256 manifest, and Turkish operating instructions. It deliberately excludes ~883 MB of raw OpenCEM CSVs.

## Critical interpretation

1. The raw-to-block output **does not prove exact source-row to replay-bin lineage**. It verifies original file bytes, source inverter IDs, timestamps and associations only. The frozen processing path averages duplicate `read_ts`/inverter records, resamples and drops incomplete signals; proving exact per-bin lineage requires explicitly traced re-execution of that original preprocessing. Never call partition SHA-256 values independent per-block hashes.
2. The recovered OPSD inventories establish known historical eligibility and previous external replay scope. They are **not new independent TEST data** and do not prove completeness of *all* possible previously viewed external datasets.
3. Historic OPSD exposures (2015–2018) and this OpenCEM partitioned run (2025–2026) are chronologically disjoint. A future proposal still requires full duplicate/site/simulator suitability auditing against **all** prior external exposures and frozen prospective decisions.
4. **F0/F1 selection remains exactly degenerate** in the Gate3 K20 results. Separate equal-budget archive fidelity reference is still required before independent confidence mechanism claims.

**Research state:** Historical source lineage audit completed at file/time-window granularity. New external test eligibility **BLOCKED**; EAAI submission **NO-GO**.
