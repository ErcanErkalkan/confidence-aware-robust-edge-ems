# CRMT — Google Drive + GitHub Synchronization Record

Date: 2026-10-27 (Europe/Istanbul)

## Authoritative locations

- Google Drive project root: https://drive.google.com/drive/folders/1g8afkrJCfF4fFSNxS1kJo9aQISGOlBne
- Google Drive synced P1/P2 folder: https://drive.google.com/drive/folders/1DQtczFNSeueZ8E2pr2tuWMnzgzNEtn-V
- Original unmodified remediation worktree: https://drive.google.com/drive/folders/1gk2vUbrdkk31z_tjeFjyja8MlEpsEX4Z
- GitHub main: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/tree/main
- GitHub PR #3 (merged): https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/pull/3
- GitHub feature branch: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/tree/remediation/p1-p2-sync-20261027

## Completed writes and verification

- Uploaded canonical P1/P2 verification ZIP, individual candidate patches, 68-target-test XML, R19 feasibility CSV, SHA manifest, code snapshots, and supplemental CI-fix bundle to Drive.
- Carried the Oct 27 A01–A32 engineering remediation worktree's 38-file source changes plus P1/P2 scientific input validation and source corrections into a reviewed GitHub PR.
- The PR's final reviewed head, `7e71886b3bbbc87669cfbc393758fd7cae1f4116`, passed all 14 GitHub Actions checks across default pytest and the Python/Linux/Windows remediation matrix.
- PR #3 was squash-merged into GitHub `main` as commit `6dc2962269bb7232bc399eea0279a6a2ee2ce05c`.
- GitHub main was read back at the merge SHA, and `src/crmt_edge_ems/strict_replay_v2.py` was verified as the expected Git blob.
- Source endings and byte identity were restored during transfer; six source files plus R19 CSV matched the locally computed Git blob IDs.

## Engineering scope and limits

- P1: scenario-specific grid caps, mode-transition count matching `flip_per_day`, conservative site limit checks, and fail-closed data admission.
- P2: explicit strict replay/cadence and finite/binary-profile validation; no silent NaN deletion in new strict risk aggregation.
- R19: mathematical bound / feasibility diagnostic for K=B=10 shortlist MissRate effects.
- Previous target-test evidence: 68/68; reviewed PR head GitHub Actions: 14/14 checks successful. Neither proves scientific confirmation.

## Critical scientific NO-GO statements

- Prospective R19 protocol still `locked=false`, with no independently authorized new R19 experiment.
- Independent external data TEST remains absent and blocked on provider-verified complete data, licensing, exposure review, and model/hardware semantics.
- Calibration simulations do not justify a family-wide 95% coverage claim.
- Adaptive allocation benefit is not independently established; original validation evidence remains unchanged.
- No physical/hardware certification, independent HIL proof, lifetime claim, or journal-submission clearance.
- Old research datasets and frozen manuscripts were not modified.

Status: `CODE_AND_DOCUMENTATION_SYNCED_TO_MAIN__SCIENTIFIC_CONFIRMATION_NO_GO`

A successful software CI pipeline is not evidence that external authority, prospective experiments, or Q1 publication readiness have been achieved.
