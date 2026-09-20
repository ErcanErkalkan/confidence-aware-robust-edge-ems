# Confirmatory Evidence Roots — 2026-09-20

This file records the frozen identities of the completed confirmatory evidence chain. It is a provenance index, not a substitute for the stage-specific manifests and statistical reports.

## Status

**Experimental evidence chain: CLOSED**

No new result may be presented as part of the frozen confirmatory chain if it changes the locked data identity, seed registry, evaluation budget, objective definitions, selection rule, or held-out protocol.

## Primary chain

| Stage | Frozen identity |
|---|---|
| Validation selection | `6481b5a363fa747a0f193b016105a806cd75827b03b43163715984f9a410610b` |
| One-shot internal test | `e39b4a1de6cfaff859ac54b3aa9c5a3388f89542367d1c2cb2b3b492d3f47100` |

## Ablation chain

| Stage | Frozen identity |
|---|---|
| Ablation TRAIN | `4ef8b3dc4058232c26ab6bf9199fcfc58181e50e97cd157e851735288e47f74b` |
| Ablation validation | `377021e8627bd733411794e24c5f47bd58686e44143ffbe71c3354d9aabda32a` |
| Ablation internal test | `7bdc251e57fd37c4eafe053406771991b3c102cacf68dbd04227bd35dd5f11a3` |

## Sensitivity chain

- Source execution run: `35490232146`
- Paired report run: `35492572956`
- Frozen root: `7f530634a027e5c6647e93bd7b1cabcfebe34b5d8d3a000b0b359e8801111377`

## OPSD external-OOD chain

- Source execution run: `35492713949`
- Statistical report run: `35495277533`
- OPSD package SHA-256: `17c41c778bf8ce9a6e483c179664afc66af2e5eddda869e359c719fc037013b3`
- Replay manifest rows: `1656`
- Seeds: `1001–1030`
- Frozen OOD root: `4e080b1957f13617f17a91949a553c9ccdc46a32879954bbe0a84f4f58cc808c`

## Claim boundary

These evidence roots support only the claims established by their frozen statistical reports.

Supported at the appropriate boundary:

- protocol-specific TRAIN approximation-quality comparisons;
- objective-specific held-out internal comparisons;
- objective-specific external-OOD comparisons;
- provenance and deterministic evidence-root verification.

Not established by the frozen chain:

- universal operational superiority;
- universal OOD robustness;
- independent held-out improvement from confidence, CVaR, or adaptive allocation;
- certified hard-real-time behavior;
- physical battery-lifetime extension;
- arbitrary cross-hardware bitwise reproducibility.

## Reproduction rule

A reproduction attempt should be considered a reproduction of the frozen chain only when the stage-specific source/data locks, seed registry, budget, selection rules, and evidence-root checks match the corresponding frozen manifests. New experiments are welcome, but must be labeled as extensions rather than silently merged into the confirmatory evidence chain.
