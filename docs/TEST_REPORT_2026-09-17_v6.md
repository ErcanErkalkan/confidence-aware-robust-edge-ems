# TEST REPORT — 2026-09-17 v6

Project: `02_CONFIDENCE_AWARE_ROBUST_EDGE_EMS`

## Existing canonical regression

The immediately preceding canonical regression report (`TEST_REPORT_2026-09-17_v5.md`) records **36/36 PASS** for the controller, CRMT core, budget/replay/site-model layer, data adapters, baseline optimizers, and baseline-to-microgrid common-ledger integration. No core optimizer/controller source was changed by the ingest/QA work in this v6 step.

## New immutable-ingest / QA regression

Command executed in the frozen local tool snapshot:

`PYTHONPATH=/mnt/data/opencem_repro_v6 python -m pytest -q tests/test_opencem_ingest_qa.py`

Result: **10 passed in 0.65 s**.

The 10 tests cover:

- Git blob SHA-1 calculation against Git object semantics;
- mixed-commit manifest rejection;
- SHA-256 + Git blob verification;
- resumable HTTP Range download behavior;
- verified-existing-file short circuit;
- train-only cadence selection;
- missing expected inverter fail-closed behavior;
- unverified partition fail-closed behavior;
- per-inverter availability/missingness QA fields;
- unexpected inverter ID rejection.

## Correction made during v6

The Windows wrapper previously pointed to `02_DATA\01_RAW\OpenCEM`, but the canonical Drive folder is `02_DATA\01_RAW_EXTERNAL`. The wrapper was corrected to use `02_DATA\01_RAW_EXTERNAL\OpenCEM`.

The QA report was also extended with per-inverter raw availability, missingness, duplicate timestamp counts, timestamp range, and gap statistics.

## Gate status

Engineering regression evidence now consists of the prior **36/36 canonical suite** plus the independently rerun **10/10 ingest/QA suite**. This is not a scientific performance result. Real-data confirmatory experiments remain blocked until all 19 immutable OpenCEM partitions are locally downloaded and verified, the generated QA report is reviewed, real-data site assumptions are frozen, real-data runtime is measured and the common budget is frozen, and the external OOD artifact is locked.
