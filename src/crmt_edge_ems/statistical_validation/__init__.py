"""Seed-level inference sensitivity; no automatic confirmatory approval."""
from __future__ import annotations

from fractions import Fraction
import itertools
import math
import numbers

import numpy as np
from scipy import stats

from ..contracts import ContractError, finite_array, integer
from ..r19_feasibility import geometry


def _real(value, name):
    if (
        isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real)
        or not math.isfinite(value)
    ):
        raise ContractError(f"{name}: finite real value required")
    return float(value)


def paired_inference(
    differences, *, alpha=0.05, signflip_assumption=None, seed=20261027, draws=9999,
):
    d = finite_array(differences, "paired seed differences", ndim=1)
    if len(d) < 2 or np.any(np.abs(d) > 1):
        raise ContractError("at least two seed-level MissRate differences in [-1,1] required")
    alpha = _real(alpha, "alpha")
    if not 0 < alpha < 0.5:
        raise ContractError("alpha in (0,0.5) required")
    seed = integer(seed, "seed")
    draws = integer(draws, "draws", 1)
    if signflip_assumption is not None and (
        not isinstance(signflip_assumption, str)
        or signflip_assumption not in {
            "INDEPENDENT_SYMMETRIC_DIFFERENCES", "RANDOMIZED_PAIRED_ASSIGNMENT",
        }
    ):
        raise ContractError(
            "sign-flip validity assumption is required; zero mean alone is insufficient"
        )
    n = len(d)
    scale = float(np.max(np.abs(d)))
    scaled = d / scale if scale > 0 else d.copy()
    mean = math.fsum(float(x) for x in d) / n
    scaled_sd = float(scaled.std(ddof=1))
    sd = scaled_sd * scale
    # Range width 2; independent seed draws conditional on the common dataset.
    radius = math.sqrt(2 * math.log(2 / alpha) / n)
    result = {
        "schema_version": 1, "status": "EXPLORATORY_SENSITIVITY",
        "n_seeds": n, "mean_delta": mean, "paired_sd": sd,
        "bounded_mean_ci": [max(-1.0, mean-radius), min(1.0, mean+radius)],
        "bounded_ci_assumption": (
            "Independent seed draws conditional on the fixed dataset; "
            "each difference lies in [-1,1]"
        ),
        "t_test_pvalue": None, "t_mean_ci": None, "signflip_pvalue": None,
        "t_assumption": (
            "Exact only for iid Gaussian differences; otherwise an asymptotic "
            "sensitivity, not a guaranteed finite-sample test"
        ),
        "signflip_assumption": signflip_assumption,
        "signflip_reason": (
            "Blocked unless symmetry or randomized paired assignment is justified"
        ),
    }
    if scaled_sd > 0:
        # Scaling preserves the t statistic and avoids underflow for tiny values.
        t = stats.ttest_1samp(scaled, 0, nan_policy="raise")
        ci = t.confidence_interval(1-alpha)
        result.update(
            t_test_pvalue=float(t.pvalue),
            t_mean_ci=[float(ci.low*scale), float(ci.high*scale)],
        )
    if signflip_assumption is not None:
        # Work on a dimensionless scale, sum accurately, and include ties within
        # one representable step. An absolute 1e-14 tolerance on raw data would
        # turn a uniformly rescaled nonzero example into p=1.
        values = tuple(float(x) for x in scaled)
        observed = abs(math.fsum(values))
        cutoff = math.nextafter(observed, -math.inf)

        def is_extreme(signs):
            statistic = abs(math.fsum(s*x for s, x in zip(signs, values)))
            return statistic >= cutoff

        if n <= 16:
            extreme = sum(is_extreme(s) for s in itertools.product((-1, 1), repeat=n))
            p = extreme / (2**n)
            mode = "EXACT_UNDER_DECLARED_ASSUMPTION"
            mcse = None
        else:
            rng = np.random.default_rng(seed)
            extreme = 0
            for first in range(0, draws, 1024):
                signs = rng.choice((-1, 1), size=(min(1024, draws-first), n))
                extreme += sum(is_extreme(s) for s in signs)
            p = (extreme+1) / (draws+1)
            mode = "MONTE_CARLO_UNDER_DECLARED_ASSUMPTION"
            mcse = math.sqrt(p*(1-p)/draws)
        result.update(
            signflip_pvalue=p, signflip_mode=mode, signflip_mcse=mcse,
            signflip_reason="Assumption declared, not independently verified",
            signflip_numerical_policy="MAX_ABS_SCALE_FSUM_ONE_ULP_INCLUSIVE_TIES",
        )
    return result


def gaussian_paired_power(n, *, effect, paired_sd, alpha=0.05):
    """Two-sided paired t power under iid Gaussian seed differences only.

    This generic sensitivity does not check R19's bounded shortlist geometry.
    Use geometry_aware_power for a fixed-P R19 planning scenario.
    """
    n = integer(n, "n", 2)
    effect = _real(effect, "effect")
    paired_sd = _real(paired_sd, "paired_sd")
    alpha = _real(alpha, "alpha")
    if paired_sd <= 0 or not 0 < alpha < 0.5:
        raise ContractError("positive paired SD and valid alpha required")
    threshold = stats.t.ppf(1-alpha/2, n-1)
    ratio = abs(effect) / paired_sd
    noncentrality = ratio * math.sqrt(n)
    if not math.isfinite(noncentrality):
        # Finite inputs can overflow their ratio. The limiting model power is 1.
        return 1.0
    # Reflect the lower tail instead of evaluating nct.cdf(-threshold, +ncp),
    # which can return NaN in SciPy for valid moderate noncentralities.
    power = float(
        stats.nct.sf(threshold, n-1, noncentrality)
        + stats.nct.sf(threshold, n-1, -noncentrality)
    )
    if not math.isfinite(power):
        raise ContractError("Gaussian power calculation did not produce a finite result")
    return min(1.0, max(0.0, power))


def geometry_aware_power(
    n, *, pareto_size, effect, paired_sd, pool_size=256, shortlist_size=10,
    alpha=0.05,
):
    """Check necessary fixed-P effect/variance constraints before model power.

    For D in [-b,b], |E[D]| <= b and Var(D) <= b*b - E[D]*E[D].
    These are necessary constraints, not proof of a data-generating model.
    A Gaussian model has unbounded support, so any returned t-power remains
    an approximate sensitivity, never a finite-sample bounded-data guarantee.
    pareto_size is a hypothetical planning scenario; do not inspect held-out
    AUDIT outcomes to select or revise the primary metric or effect threshold.
    """
    n = integer(n, "n", 2)
    effect = _real(effect, "effect")
    paired_sd = _real(paired_sd, "paired_sd")
    alpha = _real(alpha, "alpha")
    if paired_sd < 0 or not 0 < alpha < 0.5:
        raise ContractError("nonnegative paired SD and valid alpha required")
    g = geometry(pareto_size, pool_size=pool_size, shortlist_size=shortlist_size)
    b = Fraction(g.max_true_pareto_hits-g.min_true_pareto_hits, g.pareto_size)
    mu = Fraction(str(effect))
    sigma = Fraction(str(paired_sd))
    effect_possible = abs(mu) <= b
    variance_ceiling = b*b-mu*mu
    variance_possible = effect_possible and sigma*sigma <= variance_ceiling
    reasons = []
    if not effect_possible:
        reasons.append("MEAN_EFFECT_EXCEEDS_SHARP_GEOMETRIC_BOUND")
    if effect_possible and not variance_possible:
        reasons.append("PAIRED_VARIANCE_EXCEEDS_BOUNDED_SUPPORT_CEILING")
    if effect_possible and variance_possible and paired_sd == 0:
        reasons.append("ZERO_VARIANCE_DOES_NOT_DEFINE_PAIRED_T_POWER")
    power = None
    if effect_possible and variance_possible and paired_sd > 0:
        power = gaussian_paired_power(
            n, effect=effect, paired_sd=paired_sd, alpha=alpha,
        )
    return {
        "schema_version": 1,
        "status": (
            "GEOMETRICALLY_INFEASIBLE_PLANNING_ASSUMPTIONS"
            if not (effect_possible and variance_possible)
            else "MODEL_SENSITIVITY_NOT_APPROVED_SAMPLE_SIZE"
        ),
        "n": n, "pool_size": g.pool_size, "shortlist_size": g.shortlist_size,
        "pareto_size_scenario": g.pareto_size,
        "effect_assumption": effect, "paired_sd_assumption": paired_sd,
        "alpha": alpha, "sharp_max_abs_delta_miss": float(b),
        "mean_effect_geometrically_possible": effect_possible,
        "variance_geometrically_possible": variance_possible,
        "maximum_population_variance_at_effect": (
            float(variance_ceiling) if effect_possible else None
        ),
        "gaussian_t_power_sensitivity": power, "reason_codes": reasons,
        "assumptions": [
            "Fixed P planning scenario shared across independent optimizer seeds",
            "Independence is conditional on the fixed dataset, not independent sites",
            "Bounded effect/variance checks are necessary, not sufficient",
            "Gaussian paired-t power is an approximate sensitivity for bounded data",
        ],
        "not_design_approval": True,
    }


def power_sensitivity(
    *, sizes=(10,20,30,50,100,200), effects=(0.02,0.05,0.1),
    paired_sds=(0.05,0.1,0.2),
):
    return [
        {
            "n": n, "minimum_difference": e, "paired_sd_assumption": s,
            "power": gaussian_paired_power(n, effect=e, paired_sd=s),
            "status": "MODEL_SENSITIVITY_NOT_APPROVED_SAMPLE_SIZE",
            "geometry_checked": False,
        }
        for n, e, s in itertools.product(sizes, effects, paired_sds)
    ]
