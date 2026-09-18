# GitHub CI Verification — 2026-09-18

## Verified repository state

- Repository: `ErcanErkalkan/confidence-aware-robust-edge-ems`
- Branch: `main`
- Verified commit: `c04651476e745833f4a61b9209b8a01efe668546`
- Workflow: `.github/workflows/tests.yml`
- Workflow run: `35326547580`
- Job: `pytest`

## Result

```text
52 passed in 6.71s
```

The GitHub-hosted runner used Python 3.11 and installed the package with the dependencies declared by the repository.

## Cross-version defect found and fixed

The first GitHub run exposed a pandas-version-dependent timestamp-unit assumption in
`tools/opencem_qa.py::select_train_cadence_minutes`.

The earlier implementation converted timezone-aware datetimes to integer storage and
implicitly assumed nanosecond units. Pandas 3 may use microsecond resolution for these
values, which caused a true five-minute acquisition cadence to be misread and selected
as one minute.

The implementation was changed to compute consecutive gaps using pandas Timedelta
arithmetic and `.dt.total_seconds()`, which is independent of the underlying datetime
storage unit. The existing tests were retained; they were not relaxed.

## Claim boundary

This CI result verifies software regression behavior only. It does not demonstrate:

- scientific superiority of CRMT,
- optimizer superiority,
- robustness on unseen operating conditions,
- real-world deployment performance, or
- completion of the confirmatory OpenCEM experiment.

Those claims remain blocked by the P0 protocol gates.
