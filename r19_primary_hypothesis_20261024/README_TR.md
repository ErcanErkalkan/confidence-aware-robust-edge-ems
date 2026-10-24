# CRMT R19 — Birinci P0 araştırma adımı: Birincil hipotezin çözümlenmesi

**R19 bir yeni TEST veya retrospektif ön kayıt değildir.** Bu pakette, CRMT ana projedeki F0/F1 confidence archive araştırma sorusunun tek birincil karşılaştırması tasarlanmış ve ham TRAIN ölçümlerini kullanan fail-closed iki aşamalı doğrulama aracı geliştirilmiştir.

## İçerik

- `docs/R19_BIRINCIL_BILIMSEL_SORU_VE_PROTOKOL_TR.md`: Ayrıntılı Türkçe bilimsel hipotez, veri tasarımı, ölçüt, güç ve karışma kontrolü, kanıt sınırları.
- `config/R19_PRIMARY_PROTOCOL_DRAFT.json`: Makinece okunabilir **henüz onaylanmamış** tasarım.
- `tools/primary_hypothesis.py`: Ham DISCOVERY skorları + iki eşit ledger üzerinden aday seçimini mühürler; ayrı AUDIT ham skorlarıyla ref-Pareto oluşturur; 30 seed düzeyinde eşli istatistik hesaplar.
- `tests/test_primary_hypothesis.py`: 25 otomatik test; ayrıca doğal kapasite, kaynak SHA ve sonuç sızıntısı retleri.
- `results/R19_HISTORICAL_B10_FEASIBILITY.csv` ve `.json`: R18-v2'nin tarihsel 20 arşiv çifti üzerinden B=10 fizibilitesi; üstünlük testi değil.
- `tools/power_sensitivity.py` ve `results/R19_APPROXIMATE_POWER_SENSITIVITY.csv`: 30 seed için %80 güç **garanti edilmediğini** gösteren duyarlılık hesabı.
- `SHA256_MANIFEST.json`: ZIP'te bulunan dosyalar için SHA-256.

## Yerel çalıştırma

```bash
cd crmt_r19_primary
python -m pip install numpy pytest
python -m pytest -q tests
python tools/primary_hypothesis.py --help
```

**Dikkat:** `select` yalnız DISCOVERY verisini açar; `audit` dış commit ile saklanmış lock SHA ve bütün adaylar için tam AUDIT ham amaç kayıtları olmadan bilimsel kullanıma uygun değildir. JSON makbuzunun içindeki dış commit beyanı otomatik haricî kanıt değildir. Tarihsel 1001–1005 seed'leri yeni bağımsız tekrar değildir.

**Sınır:** Yalnız 1. P0 adımı (hipotez ve ölçüm protokolü + uygulama doğrulaması) tamamlandı. Yeni 30-seed deney, gerçek kaynak onaylı ön kayıt, CPU ve bağımsız kör TEST hâlâ açık. R18 özgün kaynakları ve GitHub `src/` değiştirilmedi.
