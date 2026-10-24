# CRMT R20 — Eşit kaynak maliyetinin bilimsel denetimi (24 Ekim 2026)

**Kapsam:** R19'un birincil *TRAIN-only* hipotezine yardımcı E1 maliyet muhasebesi, 10 gerçek tarihsel F0/F1 çiftinin SHA/eşli olay/amaç kontrolü, GitHub'ın bire bir kaynak kodu ile iki gerçek TRAIN seed'i üzerinde küçük altküme CPU mikro-benchmark'ı, prospektif faz ölçüm sözleşmesi ve otomatik testler.

**Değildir:** Yeni bağımsız TEST, tam 256 aday için hesaplama benchmark'ı, gerçek donanım kalibrasyonu, orijinal source code değişikliği, R19 hipotezi kabulü, eşit toplam CPU kanıtı veya gerçek zaman güvenlik sertifikası.

## Çalıştırma

```bash
python -m pip install numpy pandas pytest
python tools/cost_audit.py --r16-zip reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip --all-available --out results/replication_10_pairs.json
python tools/reference_benchmark.py --r16-zip reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip --out results/replication_microbench.json
python -m pytest -q tests
```

- `reference_inputs/` içindeki R16 ZIP özgün kaynakların değiştirilmemiş byte kopyasıdır.
- `tools/` denetim, `reference_snapshot/` GitHub exact-code kaynak kopyaları, `tests/` regresyon testleri, `results/` yeniden çalıştırılmış sonuçlar, `docs/` ayrıntılı bilimsel rapor ve `config/` henüz kilitlenmemiş E1/E2 tasarımı.
- `results/R20_REPLAYED_ARCHIVE_CPU_MICROBENCHMARK.json` CPU sonuçları ortam gürültüsü ve n_boot=200 altküme kısıtlarına bağlıdır.
- R20'nin bilimsel kararını önce `docs/R20_ESIT_BUTCEK_VE_GERCEK_MALIYET_DENETIMI_TR.md` dosyasından okuyun.
