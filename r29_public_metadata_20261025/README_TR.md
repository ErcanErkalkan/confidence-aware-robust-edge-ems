# CRMT R29 — Public Pecan Street cohort metadata / Brazil STAR record-specific license

Kapsam: **PUBLIC_METADATA_ONLY**, R19–R28 değişmedi. Veri kaynağı: https://dataport.pecanstreet.org/static/metadata.csv (kaynağın *text-extracted normalized* görünümü, özgün baytlar değil). Gerçek 2072 satır ×130 sütun, 385 PV/grid/solar metadata adayı ve 308 en az %90 bildirilmiş erişilebilirlik. Altı `battery1=yes`, bir `energy_storage_system=yes` aday; hiçbiri SOC kanıtı değildir.

Zenodo Brazil STAR kayıt-özel API: https://zenodo.org/api/records/3959739 , çıkarılan `metadata.license.id` = `cc-by-4.0`. Ham ZIP hâlâ alınamadı. Tam dört amaç eşdeğerliği **NO-GO**.

`tools/public_cohort_audit.py`: özgün kamu CSV veya satır sonları çıkarılmış normalize kamu metnini **yalnız anonim toplam sayım** halinde işler. Gerçek veri lisansı onaylama, istatistiksel kaynak bağımsızlığı ve kontrolcü değerlendirmesi yapmaz. `results/*.json`: sayım ve kanıt düzeyi/NO-GO. `tests/`: sentetik ve kanıt-mantığı testleri. `docs/`: Türkçe rapor.

```bash
pip install pytest
pytest -q tests
python tools/verify_release.py
```

Kanonik proje: `ErcanErkalkan/confidence-aware-robust-edge-ems`, ayrı `r29_public_metadata_20261025/` klasörü. Özgün `src/` kodu değiştirilmedi.
