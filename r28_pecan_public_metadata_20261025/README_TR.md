# CRMT R28 — Public Pecan metadata / provider licensing gate

R28 adds the **first public per-household telemetry metadata field confirmation**, not raw time-series admission. Fields: `grid`, `solar`, `pv`, 1-minute availability start/end/pct. It makes **no assertion** about household battery SOC, LFP, controller flip actions, contractual grid caps or true independent data.

To check a lawfully obtained **public metadata-only CSV**, run:

```bash
python tools/metadata_gate.py path/to/public_metadata.csv --out results/metadata_screen_NEW.json
python -m pytest -q tests/test_metadata_gate.py
```

Do not use customer raw data, signed-in Dataport records, or restricted exports unless the provider's signed license allows the specified processing. Provider emails are drafts and are not sent by this release. The web page's own metadata shows one-minute fields, but the full metadata CSV was **not** downloaded in R28. All new synthetic samples are for code testing only.

Primary R19 C1/A1 B=K10 hypothesis, prospective data source, external preregistration, R23 real conditional proof and blind new TEST are all unchanged / blocked.
