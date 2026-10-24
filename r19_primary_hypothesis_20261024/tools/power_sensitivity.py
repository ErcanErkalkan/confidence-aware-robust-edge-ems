"""Two-sided paired normal-approximation sensitivity only (NOT sign-flip power)."""
import csv
import math
from pathlib import Path
from statistics import NormalDist


def approximate_required_seeds(sd: float, mean_effect: float = 0.05,
                               alpha: float = 0.05, power: float = 0.80) -> int:
    if sd <= 0 or mean_effect <= 0 or not (0 < alpha < 1) or not (0 < power < 1):
        raise ValueError('positive SD/effect and probability levels in (0,1) required')
    norm = NormalDist()
    z = norm.inv_cdf(1 - alpha/2) + norm.inv_cdf(power)
    return max(2,math.ceil((z * sd / mean_effect)**2))


def main():
    out = Path(__file__).resolve().parents[1] / 'results/R19_APPROXIMATE_POWER_SENSITIVITY.csv'
    with out.open('x', encoding='utf-8', newline='') as f:
        w=csv.writer(f)
        w.writerow(['paired_seed_sd_assumption','absolute_effect','alpha_two_sided','target_power','normal_approx_required_seeds','note'])
        for sd in (0.05,0.075,0.10,0.15,0.20,0.25):
            w.writerow([sd,0.05,0.05,0.8,approximate_required_seeds(sd),
                        'planning approximation; not a validated paired signflip power calculation'])
    print(out)

if __name__=='__main__':main()
