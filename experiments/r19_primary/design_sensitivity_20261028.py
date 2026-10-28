"""Unlocked R19 design alternatives; no AUDIT outcome is opened."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
from scipy.stats import binom
from crmt_edge_ems.contracts import ContractError, file_hash, integer
from crmt_edge_ems.r19_feasibility import geometry
from crmt_edge_ems.statistical_validation import gaussian_paired_power, geometry_aware_power


def exact_extreme_two_point_power(n, *, bound, effect=.05, alpha=.05):
    """Analytic two-point planning law D in {-bound,+bound}; no empirical claim.

    pi=(1+effect/bound)/2 gives E[D]=-effect if improvement has value -bound.
    Null pi=.5; one-sided exact binomial test is conservative on its lattice.
    Variance is bound**2-effect**2, fixed by this particular hypothetical law.
    """
    n = integer(n, "n", 2)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) for v in (bound, effect, alpha)):
        raise ContractError("finite two-point parameters required")
    if not 0 < alpha < .5 or effect <= 0 or bound < effect:
        return None
    cutoff = next((h for h in range(n+1) if binom.sf(h-1, n, .5) <= alpha), n+1)
    pi = (1+effect/bound)/2
    return dict(power=float(binom.sf(cutoff-1, n, pi)), success_count_cutoff=cutoff,
                realized_null_alpha=float(binom.sf(cutoff-1, n, .5)),
                improvement_probability=pi,
                paired_sd=math.sqrt(max(0., bound*bound-effect*effect)))


def bounded_mean_sufficient_n(*, bound, effect=.05, alpha=.05, target_power=.8):
    """Hoeffding sufficient planning size for independent differences in [-b,b]."""
    if bound < effect or bound <= 0:
        return None
    beta = 1-target_power
    return math.ceil(2*bound*bound/effect**2*(math.sqrt(math.log(1/alpha))+
                    math.sqrt(math.log(1/beta)))**2)


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        writer.writeheader()
        writer.writerows(rows)


def run(out, *, frozen_plan=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    plan = dict(version="R19-DESIGN-SENSITIVITY-20261028-v2", pool_size=256,
                effect=.05, shortlist_sizes=[10, 20, 32, 64, 128],
                hypothetical_pareto_sizes=[20, 50, 100, 150, 200, 220, 240, 244, 250, 256],
                independent_unit_counts=[10, 20, 30, 50, 100, 200],
                paired_sd_assumptions=[.025, .05, .1, .2],
                alpha_values=[.05, .025, .0125], locked=False,
                R19_DESIGN_APPROVED=False, R19_PROSPECTIVE_EXECUTED=False,
                actual_audit_outcomes_accessed=False, execution_commit=None,
                base_git_reference=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                source_sha256={str(p.relative_to(ROOT)):file_hash(p) for p in [Path(__file__), ROOT/"src/crmt_edge_ems/r19_feasibility.py", ROOT/"src/crmt_edge_ems/statistical_validation/__init__.py"]})
    frozen_plan_sha256 = None
    if frozen_plan is not None:
        frozen_plan = Path(frozen_plan)
        frozen = json.loads(frozen_plan.read_text(encoding="utf-8-sig"))
        design_keys = ("pool_size", "effect", "shortlist_sizes",
                       "hypothetical_pareto_sizes", "independent_unit_counts",
                       "paired_sd_assumptions", "alpha_values")
        if any(frozen.get(key) != plan[key] for key in design_keys):
            raise ContractError("frozen R19 design differs from the sensitivity runner")
        if (frozen.get("locked") is not False
                or frozen.get("R19_DESIGN_APPROVED") is not False
                or frozen.get("R19_PROSPECTIVE_EXECUTED") is not False
                or frozen.get("actual_audit_outcomes_accessed") is not False):
            raise ContractError("frozen R19 plan has an unsafe approval or exposure flag")
        frozen_plan_sha256 = file_hash(frozen_plan)
        plan["frozen_plan_sha256"] = frozen_plan_sha256
    (out/"R19_DESIGN_SENSITIVITY_PLAN.json").write_text(json.dumps(plan, indent=2)+"\n", encoding="utf-8")
    geometry_rows, power_rows = [], []
    for k in plan["shortlist_sizes"]:
        for p in range(1, 257):
            g = geometry(p, shortlist_size=k).to_dict()
            g["minimum_hit_gain_to_reach_effect"] = math.ceil(p*.05-1e-12)
            g["sharp_precision_gain_bound"] = (g["max_true_pareto_hits"]-g["min_true_pareto_hits"])/k
            geometry_rows.append(g)
        for p in plan["hypothetical_pareto_sizes"]:
            g = geometry(p, shortlist_size=k)
            for n in plan["independent_unit_counts"]:
                for alpha in plan["alpha_values"]:
                    exact = exact_extreme_two_point_power(n, bound=g.sharp_max_abs_delta_miss, alpha=alpha)
                    for sd in plan["paired_sd_assumptions"]:
                        row = geometry_aware_power(n, pareto_size=p, effect=-.05,
                                                   paired_sd=sd, shortlist_size=k, alpha=alpha)
                        row["reason_codes"] = ";".join(row["reason_codes"])
                        row["assumptions"] = " | ".join(row["assumptions"])
                        row.update(locked=False, independently_approved=False,
                                   independent_unit_scope="Independent hypothetical dataset/campaign units; optimizer seed replication alone is conditional on one dataset",
                                   exact_two_point_power=exact["power"] if exact else None,
                                   exact_two_point_sd=exact["paired_sd"] if exact else None,
                                   exact_two_point_null_alpha=exact["realized_null_alpha"] if exact else None,
                                   exact_two_point_law="D in {-b,+b}; separate hypothetical law, not the Gaussian-SD row law",
                                   bounded_hoeffding_sufficient_n80=bounded_mean_sufficient_n(bound=g.sharp_max_abs_delta_miss, alpha=alpha))
                        power_rows.append(row)
    write_csv(out/"R19_EFFECT_GEOMETRY.csv", geometry_rows)
    write_csv(out/"R19_POWER_ANALYSIS.csv", power_rows)
    # Generic n sensitivity is provided separately; each number needs compatible
    # effect/variance geometry before use in a particular R19 planning scenario.
    minimum_sizes=[]
    for alpha in plan["alpha_values"]:
        for sd in plan["paired_sd_assumptions"]:
            for target in (.8, .9):
                minimum = next((n for n in range(2, 5001) if gaussian_paired_power(n, effect=.05, paired_sd=sd, alpha=alpha)>=target), None)
                minimum_sizes.append(dict(alpha=alpha, paired_sd=sd, effect=.05,
                                          target_power=target, minimum_n_gaussian=minimum,
                                          status="MODEL_SENSITIVITY_REQUIRES_INDEPENDENT_UNITS_AND_GEOMETRY"))
    write_csv(out/"R19_MINIMUM_SAMPLE_SENSITIVITY.csv", minimum_sizes)
    impossible = [row for row in geometry_rows if not row["effect_geometrically_possible"]]
    receipt=dict(plan_sha256=file_hash(out/"R19_DESIGN_SENSITIVITY_PLAN.json"),
                 frozen_plan_sha256=frozen_plan_sha256,
                 geometry_rows=len(geometry_rows), power_rows=len(power_rows),
                 minimum_sample_rows=len(minimum_sizes), execution_commit=None,
                 source_sha256=plan["source_sha256"],
                 locked=False, R19_DESIGN_APPROVED=False, R19_PROSPECTIVE_EXECUTED=False,
                 actual_audit_outcomes_accessed=False,
                 geometrically_impossible_geometry_rows=len(impossible),
                 no_go_reasons=["Independent authority approval absent", "New independent dataset units and sealed exposure inventory absent", "Practical effect and primary endpoint not independently selected"])
    (out/"R19_DESIGN_VALIDATION_RECEIPT.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
    write_design_reports(out, plan, geometry_rows, power_rows, minimum_sizes, receipt)
    return receipt


def write_design_reports(out, plan, geometry_rows, power_rows, minimum_sizes, receipt):
    out = Path(out)
    geometry = {(row["shortlist_size"], row["pareto_size"]): row
                for row in geometry_rows}
    impossible = [row for row in geometry_rows
                  if not row["effect_geometrically_possible"]]
    impossible_by_k = {
        k: sorted({row["pareto_size"] for row in impossible
                   if row["shortlist_size"] == k})
        for k in plan["shortlist_sizes"]
    }

    def show(value, digits=3):
        return "—" if value is None else f"{float(value):.{digits}f}"

    geometry_lines = [
        "| K | P=20 bound | P=100 bound | P=200 bound | P=240 bound | P=256 bound | P values where 0.05 is impossible |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for k in plan["shortlist_sizes"]:
        values = [geometry[(k, p)]["sharp_max_abs_delta_miss"]
                  for p in (20, 100, 200, 240, 256)]
        geometry_lines.append(
            f"| {k} | " + " | ".join(show(value) for value in values)
            + f" | {', '.join(map(str, impossible_by_k[k])) or 'none'} |")

    representative = [
        row for row in power_rows
        if row["shortlist_size"] == 32 and row["pareto_size_scenario"] == 100
        and row["paired_sd_assumption"] == .05 and row["alpha"] == .05
    ]
    representative.sort(key=lambda row: row["n"])
    power_lines = [
        "| Independent units n | Gaussian paired-t power sensitivity | Geometrically possible | Status |",
        "|---:|---:|---|---|",
    ]
    for row in representative:
        power_lines.append(
            f"| {row['n']} | {show(row['gaussian_t_power_sensitivity'])} | "
            f"{row['variance_geometrically_possible']} | {row['status']} |")

    report = [
        "# R19 design sensitivity — current results",
        "",
        f"Frozen design SHA-256: `{receipt['frozen_plan_sha256']}`. "
        f"Pool={plan['pool_size']}; target effect={plan['effect']}; "
        f"K={', '.join(map(str, plan['shortlist_sizes']))}; "
        f"{len(plan['hypothetical_pareto_sizes'])} hypothetical Pareto sizes; "
        f"n={', '.join(map(str, plan['independent_unit_counts']))}; "
        f"{len(plan['paired_sd_assumptions'])} paired SD assumptions; "
        f"alpha={', '.join(map(str, plan['alpha_values']))}.",
        "",
        f"Computed {len(geometry_rows)} exact hit-count geometry cells and "
        f"{len(power_rows)} geometry-constrained model-power sensitivities. "
        f"{len(impossible)} geometry cells cannot express an absolute 0.05 "
        "MissRate difference.",
        "",
        "## MissRate geometry",
        "",
        "For fixed P and K, the maximum absolute difference is "
        "(max feasible Pareto hits − min feasible Pareto hits) / P. "
        "If that sharp bound is below 0.05, no increase in independent sample "
        "size can make the requested effect geometrically observable under "
        "that design.",
        "",
        *geometry_lines,
        "",
        "When P=256, every candidate is Pareto and each exact-K shortlist "
        "contains exactly K true Pareto candidates; both MissRates are "
        "identical. The 0.05 difference is therefore impossible for every K. "
        "Increasing n or reducing paired SD cannot repair this zero geometric "
        "range. Other impossible P/K cells are enumerated in "
        "`R19_EFFECT_GEOMETRY.csv`.",
        "",
        "## Illustrative power sensitivity",
        "",
        "The table fixes P=100, K=32, paired SD=0.05 and alpha=0.05. These "
        "Gaussian paired-t values are conditional model sensitivities after "
        "necessary bounded-support checks; they are not approved sample sizes "
        "or finite-sample guarantees.",
        "",
        *power_lines,
        "",
        "`R19_POWER_ANALYSIS.csv` retains the full grid over n, SD, alpha, P, "
        "and K. Geometrically impossible rows have no reported power. The "
        "separate exact two-point and Hoeffding calculations are planning "
        "sensitivities under their explicitly stated hypothetical laws.",
        "",
        "## Protocol options before any AUDIT exposure",
        "",
        "1. Freeze the population definition and plausible Pareto-size range "
        "using only prior/external evidence; calculate the exact K/P geometry "
        "before choosing the primary endpoint.",
        "2. If the bound is below 0.05, change K, pool size, or the predeclared "
        "endpoint in a new blinded protocol, then recompute the full geometry "
        "and sample-size sensitivity. Do not select among these options from "
        "AUDIT outcomes.",
        "3. If the all-Pareto or near-all-Pareto regime is plausible, do not "
        "use MissRate difference as a 0.05 confirmatory effect; preselect a "
        "different estimand only with independent scientific approval.",
        "4. Define independent units as genuinely independent datasets/sites "
        "or campaigns. Optimizer seeds alone provide only conditional "
        "within-dataset uncertainty.",
        "5. Lock alpha, paired analysis, missingness/exclusion rules, minimum "
        "independent-unit count, and a sealed AUDIT exposure gate before "
        "execution.",
        "",
        "## Gate",
        "",
        "`R19_DESIGN_APPROVED=false`; `R19_PROSPECTIVE_EXECUTED=false`; "
        "`locked=false`. This is a design-time sensitivity only. Independent "
        "approval and a prospective dataset/exposure inventory remain absent.",
        "",
    ]
    with (out/"R19_DESIGN_COMPARISON_TR.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(report))

    draft = [
        "# R19 preregistration — revised draft (NOT LOCKED)",
        "",
        "> Draft for independent review only. No approval, registration, AUDIT "
        "exposure, or prospective execution is asserted.",
        "",
        "## Objective and estimand",
        "",
        "Compare two prespecified selection procedures on the same eligible "
        "pool using paired MissRate differences, with sign and practical "
        "threshold fixed by the independent protocol authority. The estimand, "
        "population, objective directions, Pareto definition, pool construction, "
        "and handling of ties must be stated before any AUDIT outcome is read.",
        "",
        "## Geometry feasibility gate",
        "",
        f"Pool size N={plan['pool_size']}; candidate shortlist sizes under "
        f"consideration: {plan['shortlist_sizes']}; proposed absolute effect "
        f"threshold: {plan['effect']}. Before locking, specify a plausible "
        "Pareto-size range from independent evidence and verify for every "
        "planned P/K that the sharp attainable MissRate-difference bound is "
        "at least the proposed threshold. If not, stop or revise the endpoint "
        "while outcomes remain sealed. In particular P=N makes the difference "
        "identically zero for exact-K shortlists.",
        "",
        "## Sampling and analysis",
        "",
        f"Planning grid only: independent-unit counts "
        f"{plan['independent_unit_counts']}; paired-SD sensitivities "
        f"{plan['paired_sd_assumptions']}; alpha values {plan['alpha_values']}. "
        "These values do not identify the required sample size. Select one "
        "alpha and one independent-unit count after reviewing geometry and "
        "variance assumptions. Distinguish units across datasets/sites from "
        "optimizer-seed replications on one fixed dataset.",
        "",
        "Primary paired analysis, confidence interval, multiplicity handling, "
        "seed schedule, stopping rule, missingness policy, and sensitivity "
        "analyses must be frozen by the authority. Gaussian paired-t power is "
        "only a model sensitivity for bounded MissRate differences; include "
        "a bounded or exact sensitivity and state all assumptions.",
        "",
        "## Evidence and governance",
        "",
        "Use training/development evidence for design. Keep the AUDIT set sealed "
        "until the design, source/data hashes, independent-unit inventory, and "
        "analysis code are reviewed and approved. Any change after exposure "
        "requires a new prospective protocol and dataset.",
        "",
        "## Approval state",
        "",
        "`locked=false`; `R19_DESIGN_APPROVED=false`; "
        "`R19_PROSPECTIVE_EXECUTED=false`. Required before execution: "
        "independent authority approval, independent dataset/campaign unit "
        "inventory, endpoint and practical-effect sign-off, feasibility gate "
        "pass, and sealed exposure controls.",
        "",
    ]
    with (out/"R19_REVISED_PREREG_DRAFT.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(draft))

    gate = {
        "status": "NO_GO_NOT_APPROVED",
        "plan_sha256": receipt["plan_sha256"],
        "frozen_plan_sha256": receipt["frozen_plan_sha256"],
        "geometry_rows": len(geometry_rows),
        "power_rows": len(power_rows),
        "geometrically_impossible_geometry_rows": len(impossible),
        "R19_DESIGN_APPROVED": False,
        "R19_PROSPECTIVE_EXECUTED": False,
        "locked": False,
        "actual_audit_outcomes_accessed": False,
        "independent_approval_received": False,
        "independent_unit_inventory_present": False,
        "required_before_execution": [
            "Independent scientific approval",
            "Independent dataset/site/campaign unit inventory",
            "Primary endpoint and practical-effect sign-off",
            "Pass geometry feasibility gate without AUDIT access",
            "Seal AUDIT outcomes until protocol and code are frozen",
        ],
        "outputs": {
            name: file_hash(out/name) for name in (
                "R19_EFFECT_GEOMETRY.csv", "R19_POWER_ANALYSIS.csv",
                "R19_MINIMUM_SAMPLE_SENSITIVITY.csv",
                "R19_DESIGN_COMPARISON_TR.md", "R19_REVISED_PREREG_DRAFT.md",
            )
        },
    }
    with (out/"R19_EXECUTION_GATE.json").open("x", encoding="utf-8") as stream:
        json.dump(gate, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frozen-plan", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.out, frozen_plan=args.frozen_plan), indent=2))
