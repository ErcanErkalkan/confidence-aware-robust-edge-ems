# CRMT_ABLATION_HELDOUT_PROTOCOL_v1

Date: 2026-09-19  
Status: FROZEN BEFORE ABLATION RESULTS

TRAIN-only ablation archives are not treated as evidence of component
contribution. Every ablation must pass the same held-out discipline as the full
CRMT method.

For each seed and each of NO_CVAR / NO_CONFIDENCE / NO_ADAPTIVE:

1. optimize on the same frozen 210 TRAIN blocks and 12,600 controller-block
   budget;
2. evaluate every ablation TRAIN-front candidate on all 118 validation blocks;
3. evaluate validation objectives with the **primary** held-out risk functional
   q=0.90, tail_weight=0.50, including NO_CVAR;
4. normalize with the already frozen primary five-method validation reference
   for that seed; ablation candidates do not redefine the ideal/worst scaling;
5. select one candidate by the same Chebyshev → L1 → candidate-ID tie-break;
6. SHA-256 lock the selected ablation candidate;
7. evaluate that candidate exactly once on the 78 internal-test blocks, again
   under the primary held-out risk functional.

This design isolates the changed optimization mechanism from the held-out
evaluation criterion and prevents internal-test-driven ablation selection.
