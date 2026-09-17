# RAW_INGEST_BLOCKER_NOTE_v1

Date: 2026-09-17
Project: 02_CONFIDENCE_AWARE_ROBUST_EDGE_EMS
Status: OPEN BLOCKER — transfer/materialization only

## What is already frozen and verified

The OpenCEM source identity is frozen independently of local download:

- Repository: `OpenCEM-platform/opencem-dataset`
- Immutable commit: `5884d253a5267fb240b7a8df6fa9e4d49a905167`
- Immutable tree: `5471f4cf87c3d4bcf0fe590c6cad69433cb5535b`
- Measurement partitions: 19 CSV files
- Frozen total measurement bytes: 883,382,698
- Each manifest row includes repository path, immutable Git blob SHA-1 and expected byte size.

Smallest frozen partition used for transfer smoke attempts:

- path: `data/measurements/2025-12-b.csv`
- expected byte size: `429723`
- expected Git blob SHA-1: `390213df12696e95604be5ea98a7ef1359bc7525`

## What remains blocked

The connected GitHub tool can expose the raw/blob content for inspection, but the current connector/runtime path has not produced a local byte-perfect file that can be independently checked with the frozen byte size and Git blob SHA-1. Display truncation or connector-returned text is **not** accepted as a substitute for a verified local file.

Therefore, as of this note:

- no OpenCEM measurement partition is declared locally verified solely from connector display output;
- no full real-data QA run is declared complete;
- no real-data cadence result is declared;
- no scientific performance, superiority, robustness or deployment claim is authorized.

This is a transfer/materialization limitation, not evidence that the public source file is absent.

## Fail-closed release condition

The blocker closes only after all selected partitions exist under:

`02_DATA/01_RAW_EXTERNAL/OpenCEM/data/measurements/`

and the frozen ingest verifier confirms for every file:

1. exact expected byte size,
2. exact Git blob SHA-1,
3. locally computed SHA-256 recorded in the checksum outputs,
4. `verified=True` in the verification manifest.

Only then may `opencem_qa.py` execute on the complete verified set.

## Canonical Windows entry point

Use:

`08_REPRODUCIBILITY/05_TOOLS/run_opencem_ingest_windows.ps1`

The wrapper points to the canonical Drive structure:

- manifest: `02_DATA/04_PROVENANCE/opencem_git_tree_manifest_v2.csv`
- raw data: `02_DATA/01_RAW_EXTERNAL/OpenCEM`
- verification outputs: `02_DATA/05_CHECKSUMS`
- QA output: `02_DATA/06_QA`

A smoke download may use `-Limit 1`; full QA is intentionally skipped in limited mode. Confirmatory work must use the complete frozen partition set.
