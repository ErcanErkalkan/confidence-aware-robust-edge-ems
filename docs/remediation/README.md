# CRMT remediation v1

This is a local engineering feature branch based on upstream commit
`353b5710da298c6d51fb96452294ff117a31603e`. Historical F0/F1 source modules
remain unchanged. New strict interfaces are opt-in; they are not a completed
production migration or independent scientific validation.

The canonical deliverable index is `CRMT_RESEARCH_PROJECT/CRMT_REMEDIATION_INDEX.md`.
The complete Turkish report, A01–A32 matrix, 22-question acceptance audit,
exact source changes and artifact hashes are under that root's `docs/remediation/`.
Original data and v12 remain outside this checkout and unchanged.

From this checkout:

```powershell
python -m pip install -r reproducibility/requirements-remediation-full-lock.txt
python -m pytest -p no:cacheprovider --override-ini addopts= -q tests
python experiments/runner/run.py verify
python experiments/runner/run.py gate-check
python experiments/runner/run.py dry-run --out reports/runner/engineering_NEW
```

Current and clean Windows environments each passed 297 tests. The separate
historical package rerun passed 419 tests while original R20 retained its Windows
`resource` import collection error. Linux CI is defined but has not run locally.

The new 3600-record synthetic calibration fails the draft coverage criterion for
every elimination method in at least one required scenario. Abstention does not
provide elimination utility or solve archive overflow. No archive-wide 95%
claim, adaptive superiority, new external TEST or independent preregistration
is established.

Scientific CLI commands fail closed. A verified independent authority registry,
eligible measurement data, rights/exposure evidence, an approved power/split plan
and prospective execution integration are still required. Source-manifest
creation, a local signature or passing tests never provides those authorizations.