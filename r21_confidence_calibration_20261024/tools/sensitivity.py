"""Exploratory moving-block-length sensitivity; not a tuned confirmatory method."""
from __future__ import annotations
import csv,json
from pathlib import Path
from calibrate import generate,assess,wilson
ROOT=Path(__file__).resolve().parents[1]

def main():
 rows=[]
 for scenario in ('near_serial','flat_serial'):
  for length in (3,6,12):
   results=[]
   for r in range(80):
    seed=20261024+10000*(2 if scenario=='near_serial' else 3)+r
    panel=generate(scenario,seed)
    results.append(assess(panel,'maxT_shared_moving_block',seed+187,n_boot=350,block_len=length))
   for metric in ('family_undercoverage','false_removal','overflow'):
    k=sum(bool(x[metric]) for x in results)
    rows.append({'scenario':scenario,'block_length':length,'metric':metric,'n':len(results),
     'events':k,'rate':k/len(results),'wilson_95_upper':wilson(k,len(results))[1]})
 with (ROOT/'results/R21_BLOCKLEN_SENSITIVITY.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 for row in rows:print(row)
if __name__=='__main__':main()
