# EAAI manuscript patch notes — evidence-safe working text (2026-10-11)

**Editorial notes only. Not a frozen scientific experiment and not a submitted manuscript.**
Use with the independent English Introduction/Related Work working draft prepared 2026-10-11. Old ASOC v12 PDF, figures, code, results, citations and release hashes must remain immutable.

## Verified corrections for the existing manuscript

| Frozen ASOC v12 locus | Required editorial action | Proof / outstanding gate |
|---|---|---|
| Abstract and Introduction, Results §7.1, Table 5, Fig. 2, Discussion and Conclusion | Replace unqualified "TRAIN optimizer-quality" with "validation-evaluated approximation-set quality of TRAIN-generated archives" | Archived indicator code path evaluated on validation; retain numerical metrics as historical only |
| §6.1 and all equal-budget wording | Specify exact 12,600 **TRAIN** controller–block evaluations per method/seed; report differing original full-archive VAL costs separately | The 30×5 original TRAIN budget does not establish equal end-to-end effort |
| §3.3 finite-sample risk score | State empirical tail estimator: arithmetic mean of largest ceiling of 10% of sampled TRAIN block losses | Must confirm implementation details for ties/missing values before finalizing |
| §4.4 confidence archive | Scope Bonferroni to four objectives *within one candidate pair*, not all possible archive comparisons | Archive-level error coverage is not thereby proven |
| §8.1 one-factor ablations | Disclose original 30/30 identical selected controller for CRMT versus NO_ADAPTIVE; interpret component contribution cautiously | Existing held-out one-factor differences not Holm-significant |
| §5 / §7 / §10 claim boundaries | Mark old internal-test and OPSD results historical; no new blind test currently exists for EAAI reanalysis | New independent TEST required |
| Related Work/novelty | Recognize earlier accepted EJT benchmark/edge controller as previous shared infrastructure; identify CRMT's additional offline risk/confidence/allocation question | Full accepted EJT citation pending formal bibliographic metadata |
| New Gate2/Gate3 status | Explain 3,000 K20 TRAIN-only candidate slots; 2,193 historical cache / 807 unresolved, no validated new clean replay. Five pilot seed1001 TRAIN conditions have uploaded summaries only | Gate2 VAL, Gate3 VAL and TEST not yet validated |

## Evidence-safe English paragraphs for manuscript integration

### Indicator provenance (replace the original §6.2 title/definition)

"Approximation-set quality is evaluated for TRAIN-generated candidate archives using a common VALIDATION evaluation protocol. Hypervolume is maximized, whereas IGD+ and additive epsilon are minimized. These measurements characterize the approximation sets under the chosen validation reference and normalization; they are neither TRAIN-evaluated objective scores nor direct measures of the operational benefit of a single controller. The historical values are retained for transparency, with the unequal validation candidate counts and associated computational expenditure disclosed separately."

### TRAIN and end-to-end computational fairness (add to §6.1)

"Each method received an exact budget of 12,600 controller–block evaluations per optimizer seed during training. This budget condition controls training-stage simulation evaluations only. Under the historical all-front validation procedure, the number of transferred candidates and therefore the total validation effort differed across methods. Subsequent archive construction, bootstrap sampling, controller selection and any implementation overhead may also contribute to practical resource demand. Claims of comparable end-to-end cost therefore require separate measurement rather than inference from the common training ledger."

### Archive-level confidence boundary (add to §4.4)

"One-sided paired-bootstrap confidence bounds are formed after aligning candidates on common operating block identifiers. The multiplicity adjustment associated with the four operational objectives applies to each evaluated candidate-pair decision. No simultaneous error-rate guarantee over every possible candidate-pair comparison in the archive is inferred solely from this adjustment. The minimum paired sample size, treatment of identical candidate vectors and zero-variance comparisons remain implementation-specific conditions to be documented from the frozen code."

### Factorial follow-up state (new §8 exploratory follow-up note only)

"To investigate the identification of the risk, confidence and adaptive-allocation contributions, an exploratory two-level, three-factor follow-up protocol was specified. Its TRAIN-only candidate-generation and allocation stages must not be conflated with validation-evaluated final controller performance. On 11 October 2026, five condition-specific TRAIN artifact groups from seed 1001 were visible in the linked Drive store. Those records do not constitute a completed five-seed factorial pilot, a 30-seed follow-up, or a new independent test. No factorial contribution estimate is reported pending complete and independently verified outcome evidence."

### Earlier work contribution boundary (add to §1 and §2)

"The underlying edge EMS and reproducible replay infrastructure have also been studied in earlier work on a compliance-oriented battery-supported microgrid benchmark. The present study reuses that fixed controller family as an evaluation substrate. Its additional research question concerns decision reliability in finite-block offline multi-objective parameter tuning. Accordingly, reproducibility of the controller and the feasibility of its simulated execution are not presented as newly established innovations of CRMT; experimental support for the proposed risk/confidence/allocation decision protocol must instead be assessed through controlled optimization and post-selection comparisons."

## References and formatting — editorial, not experimental

- Independently check original numbered references [1]–[24], not merely title/DOI parity; verify published author formatting and journal metadata.
- Correct [2] Vela Morales and [3] De Santis source-name segmentation if the publisher metadata confirms it; [13] name formatting needs final crosscheck.
- Preserve provisional accepted-EJT [25] status until a publisher record provides a confirmed DOI and full bibliographic details.
- Review dense source Tables 6–9 for readable single-column EAAI production, with no changes in numeric values.
- The final abstract, highlights and EAAI claim of novelty remain **pending** actual verified Gate2 and Gate3 evidence.

## Reproducibility and immutability

- `main` is the 2026-09-21 manuscript v12 archive, not the October EAAI experiment source.
- The Oct-09 audit branch is a historical/code-integrity research record, not a replacement frozen controller implementation.
- All experimental runs must reference their exact source commit, original SHA locks, manifests, seeds and dataset split.
- `C1_F1_A1` seed1001 summary currently records `UNRECORDED_LOCAL_SHA`; no overwrite, invented commit or inferred equality is allowed.

For synchronized status, see [STATUS_AND_EVIDENCE_BOUNDARY_2026-10-11.md](STATUS_AND_EVIDENCE_BOUNDARY_2026-10-11.md).
