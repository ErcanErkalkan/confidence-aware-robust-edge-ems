# CRMT P1/P2 sync package — 27 Oct 2026

Repository: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems
Canonical Drive: https://drive.google.com/drive/folders/1g8afkrJCfF4fFSNxS1kJo9aQISGOlBne

## Scope
- P1 candidate safety patch: time-dependent caps, mode-change counting, model-bound validation, conservative source admission.
- P2 versioned strict replay and scientific input validation.
- R19 effect-feasibility grid, engineering regression evidence, unit tests, SHA-256 package manifest.

## Evidence limits
- 68 targeted tests from the prior local assembled test environment passed. The full original 297-test remediation suite has NOT been rerun on the final integrated repository branch.
- New source code patches are *not* scientific verification; R19 prospective protocol remains unlocked, independent external TEST not run, bootstrap family-wide coverage claim not proven.
- Historical datasets, raw results, frozen manuscript, and original experimental provenance remain unchanged. Do NOT classify as a validated confirmatory release.
- This package is intended for feature-branch review and integration, not unconditional publication or field deployment.

## Files
- CRMT_P1_GUVENLIK_VE_R19.patch
- CRMT_P2_KATI_REPLAY.patch
- src/crmt_edge_ems/strict_replay_v2.py
- tests/test_p2_strict_replay.py
- evidence/P2_FINAL_68.xml
- evidence/R19_EFFECT_FEASIBILITY_GRID.csv
- README_TR.md and SHA256_MANIFEST.json

Status: ENGINEERING_PATCHES_TARGET_TESTED__FULL_INTEGRATION_NOT_VERIFIED
