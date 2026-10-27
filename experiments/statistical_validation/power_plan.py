"""Generate power sensitivity, never an approved sample-size declaration."""
from pathlib import Path
import sys
import json
import csv
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from crmt_edge_ems.statistical_validation import power_sensitivity,gaussian_paired_power
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    out=ROOT/'reports/statistical_validation';out.mkdir(parents=True,exist_ok=True)
    rows=power_sensitivity()
    with (out/'power_sensitivity.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    fig,ax=plt.subplots(figsize=(8,5.2))
    fig.subplots_adjust(bottom=.22,top=.88,left=.12,right=.98)
    for sd in (.05,.1,.2):
        sizes=list(range(5,201,5))
        ax.plot(sizes,[gaussian_paired_power(n,effect=.05,paired_sd=sd) for n in sizes],label=f'Paired SD = {sd:g}')
    ax.axhline(.8,color='gray',linestyle='--',label='80% planning reference')
    ax.axvline(30,color='black',linestyle=':',label='Draft n = 30')
    ax.set(xlabel='Independent optimizer seeds (conditional on dataset)',ylabel='Model power',ylim=(0,1.02),
        title='Paired t-test sensitivity: |DeltaMiss| = 0.05, two-sided alpha = 0.05')
    ax.legend(loc='lower right');ax.grid(alpha=.2)
    fig.text(.01,.025,'IID Gaussian difference model only. No external approval or site-level power claim.',fontsize=8)
    fig.savefig(out/'power_curves.png',dpi=180);plt.close(fig)
    (out/'status.json').write_text(json.dumps({'status':'MODEL_SENSITIVITY_NOT_APPROVED_SAMPLE_SIZE',
        'n30_effect05_power':{str(sd):gaussian_paired_power(30,effect=.05,paired_sd=sd) for sd in (.05,.1,.2)},
        'pending':['Minimum important difference','Independent unit and dependence justification','Paired SD uncertainty','Failed-run policy','Multiplicity','External preregistration']},indent=2),encoding='utf-8')

if __name__=='__main__':main()