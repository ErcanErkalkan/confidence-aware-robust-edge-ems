# CAL-v2 bounded-IID day-vector method — 28 October 2026

Status: CONDITIONAL_MATHEMATICAL_METHOD_AND_SYNTHETIC_STUDY_ONLY.
CALIBRATION_SCIENTIFICALLY_VALIDATED = false for CRMT operational data.
This amendment does not close A10, validate OpenCEM dependence assumptions,
authorize a prospective experiment, or establish a capacity-constrained utility.

## Assumptions and target

Input axes are day, candidate, inverter, objective, with exactly four objectives.
Every day is a complete vector over a fixed candidate/inverter/objective family.
Those day vectors must be independent and identically distributed. Candidates
must be fixed before observing this calibration panel, and deterministic support
bounds must be known independently before observing it. Observed minima/maxima
are not known support bounds.

Within a day, objectives, candidates and inverters may be arbitrarily dependent.
Different inverter marginals may have different distributions and different known
bounds. The target for each candidate/objective is the equal-weight MIXTURE of
its inverter marginal distributions:

    F_mix(x) = (1/I) sum_i F_i(x),
    T(F_mix) = E_Fmix[X] + lambda * upper-CVaR_q(F_mix), lambda >= 0.

This preserves the pooled-observation functional; it does not silently replace
it by the average of per-inverter CVaRs. The mixture is a statistical target,
not a claim of independent physical deployments.

The implementation requires explicit IID_DAY_VECTORS, FIXED_BEFORE_CALIBRATION
and PREDECLARED_KNOWN_SUPPORT declarations. Other flags, including dependent or
nonstationary days, are rejected. Passing strings does not independently prove
that real data satisfy them. Actual data admission remains externally blocked
until these conditions are justified. Missing/nonfinite/out-of-support values
are rejected without filtering, clipping, filling, or relabeling.

## Simultaneous CDF bound

For each of the M=C*I*4 marginals there are n independent days. The two-sided
Dvoretzky–Kiefer–Wolfowitz–Massart bound gives

    Pr(sup_x |Fhat_i(x)-F_i(x)| > epsilon) <= 2 exp(-2n epsilon^2).

A union bound with epsilon=sqrt(log(2M/delta)/(2n)) covers every marginal
simultaneously with probability at least 1-delta. Arbitrary dependence among
marginals does not invalidate this union bound. The implementation may cap
epsilon at 1, since a CDF distance cannot exceed 1.

The pooled observations contain n*I values but these are NOT n*I independent
samples. For the equal-weight mixture,

    ||Fhat_mix-F_mix||_infinity
        <= (1/I) sum_i ||Fhat_i-F_i||_infinity <= epsilon.

The effective DKW sample size remains n days. Adding copies of an inverter
never increases the claimed independent-day sample size.

Primary mathematical reference:
Pascal Massart (1990), The Tight Constant in the Dvoretzky-Kiefer-Wolfowitz
Inequality, Annals of Probability 18(3), 1269–1283,
[DOI](https://doi.org/10.1214/aop/1176990746).
The theorem and constant 2 were also checked in
[MIT mathematical research notes](https://math.mit.edu/~rmd/Research/semtalk.pdf).
The publisher page's automated access was blocked during this session; no
publisher full-text read is claimed.

## Transfer from CDF error to mean plus upper-CVaR

For a candidate/objective let all inverter support lie within [L,U] and R=U-L.
The mixture has the same known support envelope. By integrating CDF differences,

    |E_F[X]-E_G[X]| <= R * ||F-G||_infinity.

Use the upper-CVaR representation, with a=1-q>0:

    CVaR_q(F) = min_{t in [L,U]} (t + E_F[(X-t)_+]/a).

For every fixed t, the hinge expectation difference is at most R*epsilon,
because E[(X-t)_+] is the integral of the survival function from t to U.
Taking infima preserves the uniform difference bound, hence

    |CVaR_q(F)-CVaR_q(G)| <= R*epsilon/a,
    |T(F)-T(G)| <= R*epsilon*(1+lambda/a).

The known support also bounds T in [(1+lambda)L,(1+lambda)U]; intervals are
intersected with that envelope. These arguments are conditional mathematical
bounds, not empirical proof that day independence or the support assumptions
hold in CRMT data.

## Ceil-tail estimator correction

CRMT's point functional uses the mean of the largest k=ceil(a*N) pooled
observations, N=n*I. At noninteger tail mass t=a*N, that ceil-tail mean is
generally LOWER than the fractional empirical upper-CVaR. They are distinct
estimands at finite sample size.

Writing k=ceil(t), m=k-1, and A for the sum of the largest m observations,
with y the next-largest value, the difference is

    CVaR_fractional - mean_top_k
       = (k-t)*(A-m*y)/(t*k)
       <= R*(k-t)*(k-1)/(t*k)
       <= R/t.

It is zero for integer t and for k=1. The implementation adds lambda times
this known bound on the UPPER side of the risk interval. A simpler
lambda*R/((1-q)*n*I) upper bound is recorded separately for inspection.
It is not omitted merely because q=.9 looks familiar.

CAL-v2 uses exact decimal q semantics to compute the ceil tail count. Thus
q=.7 and N10 uses k3 rather than a floating artifact k4. This is a separate
new method; historical strict_risk and historical results remain unchanged.

On the simultaneous CDF event, every true candidate/objective risk lies in
its reported interval. Upper difference bounds are U_candidate-L_comparator.
A dominance declaration requires nonpositive upper differences in all four
objectives and a strictly negative bound in at least one. Therefore false
dominance and false removal cannot occur on that same simultaneous event,
under all stated assumptions. This conditional result is not a guarantee
under autocorrelation, distribution shift, adaptive candidate construction,
or estimated/violated support bounds.

Numerical arithmetic uses finite-value checks, accurate sums and outward
one-step floating rounding. It is ordinary floating point, not a formal
arbitrary-precision proof assistant or hardware safety certificate.

## Capacity and utility

Retained candidates are not silently clipped or backfilled to K10. Overflow is
reported and all retained candidates are preserved. Conservative bounds can be
wide and uninformative, especially under small n, high family size or small
tail probability. Abstaining/no-elimination has vacuous coverage and perfect
retention but can overflow. Neither is automatically a solved optimizer.

The module exposes separate metrics for family risk undercoverage, family
difference undercoverage, false dominance, false Pareto removal, true Pareto
retention, and archive overflow. No K-shortlist selection policy is invented;
selection fidelity is explicitly null.

## Predeclared synthetic driver

Command:

    python experiments/calibration/run_conservative_v2.py --out NEW_OUTPUT_DIR --repetitions 80

The output directory must be new. PREDECLARED_CONFIG.json is written before
any samples are generated. Seeds, methods, support bounds, q, lambda, capacity,
scenario definitions, and rejection policies are fixed before outcomes.

Four accepted known-truth bounded scenarios:

1. IID uniform day vectors with common known support.
2. IID days with perfect within-day dependence across all marginals.
3. Small-sample IID Bernoulli outcomes with analytic population tail risk.
4. Small-sample bounded IID tradeoff front, including capacity overflow.

Two additional generated regimes are rejected by CAL-v2: stationary Markov
days with serial dependence, and a nonstationary probability shift. They do not
receive intervals or empirical coverage outcomes from this method. A separate
no-elimination comparator remains explicitly vacuous.

Population truth is analytic for the synthetic marginal distributions.
For uniform(a,a+w), mean=a+w/2 and CVaR_q=a+w*(1+q)/2.
For a+w*Bernoulli(p), mean=a+w*p and CVaR_q=a+w*min(1,p/(1-q)).
The Markov process has Bernoulli(.3) stationary marginals; the shifted scenario
labels its target as the post-shift distribution, not an IID calibration law.

Files include PREDECLARED_CONFIG.json, synthetic_records.csv, RESULTS.csv,
CALIBRATION_VALIDATION.json, SUMMARY.json and an actual-file SHA-256 manifest.
Per-attempt CPU/wall time and peak Python traced allocation are measured.
RSS is explicitly unmeasured; traced allocation is not RSS, joules or watts.
These are calibration/retention-call measurements with tracing overhead,
not a complete optimizer equal-compute comparison.

At 80 repetitions the driver plans 960 method-attempt records (6 scenarios
times 80 repetitions times 2 methods), including 160 expected CAL-v2 rejections.
These are planned counts until the actual driver receipt exists. No synthetic
record is a physical experiment, prospective R19 event, or independent TEST.

## Verification and remaining limitations

New tests cover known constant support, true dominance, complete support,
out-of-range rejection, unsupported assumptions, fixed candidates, pooled
cluster accounting, fractional/ceil-tail correction across small geometries,
overflow retention, and writing the plan before sampling.

The coding session could not execute local Python. Only subsequent actual
pytest/CI/JUnit and driver outputs establish that these new implementations
ran successfully. The method does not retroactively validate legacy F1 or
CAL-MAXT-v1. No operational or manuscript guarantee is approved here.
