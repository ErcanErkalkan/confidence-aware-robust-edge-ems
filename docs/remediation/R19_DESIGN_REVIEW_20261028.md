# R19 design review and strict contract amendment — 28 October 2026

Status: ENGINEERING_AMENDMENT_AND_PLANNING_REVIEW_ONLY.
R19_DESIGN_APPROVED = false. R19_PROSPECTIVE_READY = false.
The historical protocol remains locked=false. No AUDIT, prospective experiment,
independent TEST, or external approval is created by this amendment.

## Source reviewed and scope

The review started from GitHub main d7f772043dba5eda4c2ebfd734d052305e186eee.
Original blobs reviewed:

- src/crmt_edge_ems/r19_feasibility.py: da776de90e6084a91ae83995ac056cefad280bde
- src/crmt_edge_ems/r19_primary.py: cb4a37ff9704949c2bc25b482e493d4ba1b8df91
- src/crmt_edge_ems/statistical_validation/__init__.py: 6acfa485932164200a31349ce509320a3dcd2acc

The active selection receipt schema becomes version 2. The strict-draft protocol
identifier and its historical fixed C1/A1, N256, B=K10, DISCOVERY 12600,
no-backfill and unlocked design are preserved. Version 2 adds declared AUDIT IDs
and natural archive memberships to the selection digest. This is a reviewed
software amendment, not a replacement or external ratification of the R19 draft.

Historical r19_primary_hypothesis_20261024 files, R18–R30 packages, source data,
old execution SHA gaps, and the original protocol JSON are not modified.

## Sharp MissRate geometry: derivation

Let U be the fixed N-candidate universe, Q its empirical AUDIT Pareto set of
size P>0, and S an exact-K shortlist of distinct candidates, where 1<=K<=N.

Write h=|S intersection Q|. There are only N-P non-Pareto candidates, hence at
least K-(N-P) selected candidates must lie in Q whenever that quantity is
positive. At most K and at most P can lie in the intersection. Therefore

    L=max(0,K-(N-P)) <= h <= H=min(K,P).

Both endpoints are attainable as unconstrained subsets of the universe:
select Pareto candidates first for H, or non-Pareto candidates first for L.
Because MissRate(S)=1-h/P,

    DeltaMiss = MissRate(F1)-MissRate(F0) = (h0-h1)/P,
    max |DeltaMiss| = (H-L)/P.

This is an exact global upper bound for two arbitrary exact-K shortlists.
A shared DISCOVERY ranking and particular natural archives can restrict their
choices further. Global geometric possibility does not establish attainability
by the actual optimizer, a scientific guarantee, or statistical power.

For N256 and K10:

| P | L | H | Sharp maximum absolute DeltaMiss |
|---|---|---|---|
| 10 | 0 | 10 | 1 |
| 100 | 0 | 10 | 0.1 |
| 200 | 0 | 10 | 0.05 |
| 201 | 0 | 10 | 10/201 |
| 246 | 0 | 10 | 10/246 |
| 247 | 1 | 10 | 9/247 |
| 255 | 9 | 10 | 1/255 |
| 256 | 10 | 10 | 0 |

A 0.05 effect cannot occur on an individual seed with P>200.
For different hypothetical P_s, the bound on the mean difference is

    |mean_s DeltaMiss_s| <= mean_s b_s,  b_s=(H_s-L_s)/P_s.

One seed with P>200 does not by itself rule out an aggregate 0.05 effect.
All P=256 makes every paired difference identically zero.

The previous software used an absolute 1e-14 feasibility tolerance. It declared
a positive threshold such as 1e-15 feasible even when the sharp bound was zero.
The amended comparison uses exact integer fractions and interprets a supplied
threshold through its shortest decimal float representation: 0.05 means 1/20.
Reporting floats are still rounded representations of the exact rational bound.

## Effect geometry and power must be compatible

For a fixed hypothetical P, D lies in [-b,b]. Thus

    |E[D]| <= b,
    Var(D) = E[D^2]-E[D]^2 <= b^2-E[D]^2.

These are necessary support constraints. They do not establish a distribution,
independence, or the validity of a specific test.

At P200, b=.05. A population mean of -.05 is on the support boundary; positive
population SD is impossible. A planning table combining that mean with SD .05,
.1, or .2 is not an attainable R19 scenario at P200. At P>200, the mean effect
itself is impossible. For an observed finite sample, the analogous ddof=1
sample variance ceiling contains the factor n/(n-1); it must not be confused
with this population planning inequality.

The new geometry_aware_power API checks the mean and population variance
constraints before computing a paired-t model sensitivity. Impossible cases
return no model power and an explicit reason. Zero-variance cases also return
no paired-t power. Passing the checks is necessary, not sufficient.

An exactly Gaussian nondegenerate variable has unbounded support, whereas
DeltaMiss is bounded and discrete. Therefore paired-t power remains an
approximate model sensitivity for R19; it is never a distribution-free
finite-sample guarantee. The generic gaussian_paired_power API is preserved
for generic model sensitivities and does not silently imply a geometry check.

P values supplied to planning are hypothetical. AUDIT outcomes must not be
inspected to revise the primary metric, practical effect, sample size, or
decision rule. A different primary metric requires a separately reviewed
protocol before exposure. The software does not replace DeltaMiss.

## Selection receipt invariants and missing-run policy

A matching SHA-256 digest protects byte identity, not scientific validity,
authorization, or external temporal ordering. The AUDIT entry point now
revalidates the selection schema even after its digest matches:

- Exactly 256 distinct known candidate IDs.
- Exactly F0 and F1, each with exactly 10 distinct known selected IDs.
- Fixed B10, backfill=false, locked=false and the strict-draft protocol ID.
- Finite four-objective normalization metadata and nonnegative spans.
- Well-formed source-input and ledger digests.
- Version 2 natural archive memberships, exact reported counts, and selected
  IDs belonging to their corresponding natural archive.
- A declared AUDIT manifest of distinct IDs, at least eight as a technical
  lower limit, with no DISCOVERY ID overlap.

The technical eight-block minimum is not a prospective sample-size approval.
A real approved schedule may require 60 or more; exact declared IDs always
control acceptance. The backend must validate that schedule against its
approved protocol and source registry.

Compatible APIs:

    select_shortlists(..., audit_block_ids=planned_ids,
                      require_declared_audit=True)
    audit_fidelity(selection, observations, require_declared_audit=True)

When declared, every one of the 256 candidates must have exactly the sealed
AUDIT block support. Removing one block from every candidate, swapping one
planned block for another, or adding an unplanned block fails. An incomplete
seed manifest and duplicate or failed seed results fail aggregation.

Older version 1 receipts and calls without declared IDs remain available for
explicit exploratory mathematics only. They report
UNDECLARED_EXPLORATORY_SUPPORT_ONLY and are rejected by strict mode. They lack
a sealed natural membership list and an exact prospective AUDIT schedule;
they cannot authorize or substantiate prospective execution.

The hash-bound manifest does not establish physical interval separation,
site independence, embargo compliance, data rights, or exposure history by
itself. Those require the separate validated data registry and external gates.

## Inference numerical policy and independent unit

Independent optimizer seed draws condition on the same fixed dataset. They
are not independent physical sites or operational deployments.

Sign-flip remains disabled unless the caller explicitly declares independent
symmetric differences or randomized paired assignment. A string declaration
does not independently establish that assumption.

The previous raw absolute comparison tolerance changed exact sign-flip
p-values when differences were uniformly rescaled to tiny nonzero values.
The new numerical policy normalizes by the maximum absolute difference, uses
accurate signed sums, and includes ties within one representable step.
The t statistic is also evaluated on scaled data to avoid variance underflow.
Neither change makes sign-flip valid under an unjustified symmetry assumption.

## Verification evidence and limits

New active tests cover:

- Exhaustive small-universe hit ranges and attainable endpoints for N1..10.
- Seeded geometry properties, full-pool shortlists, and exact threshold edges.
- Hash-valid but malformed selections, K10, unknown/duplicate IDs, and no-backfill.
- Complete declared AUDIT support, missing/extra/replaced blocks and legacy-mode
  rejection by strict callers.
- Complete planned seed accounting and failed-run rejection.
- Exact and Monte Carlo sign-flip scale behavior.
- Geometry-incompatible effect/variance assumptions and finite extreme inputs.

No new testing dependency is required. Run these tests together with the full
repository suite and retain JUnit XML. The code-writing session could not run
local Python; test success must be taken from the later actual CI/JUnit result,
not inferred from this document.

An independent JavaScript enumeration during the read-only mathematical
review checked 385 (N,K,P) configurations and 18,379 subset hit counts for
N1..10 without a formula discrepancy. That is a mathematical cross-check,
not execution of the repository Python tests or a scientific experiment.

## Open decisions and blockers

- Independent source/provenance review and original execution receipt gaps.
- Calibration and archive-capacity adequacy under dependence and shift.
- A feasible pre-exposure effect and justified independent-unit/power plan.
- Genuine external preregistration and authority verification.
- Rights-verified, exposure-audited, physically suitable new data.
- Approved prospective DISCOVERY/AUDIT execution.
- Independent operational TEST, HIL, field, lifetime and author-release evidence.

No blocked scientific gate is closed by this engineering amendment.
