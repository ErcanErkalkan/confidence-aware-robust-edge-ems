# CRMT R21 — İstatistiksel Kalibrasyon ve Zaman Bağımlılığı

**Statü:** Gerçek CRMT Git blob koduyla sentetik stres testi + özgün, daha önce incelenmiş TRAIN için kronoloji ve ortak blok tanısı. **Yeni bağımsız TEST değildir.**

## Ana sonuç

Bütün aday çiftleri ve amaçlar için eşzamanlı güven kapsaması, özgün F1 bootstrap yönteminde nominal %95 seviyesine ulaşmamıştır. Aynı bloklardan yeniden örneklemeli max-T tanılaması bağımsız bloklarda iyileşme gösterse de hedeflenen kalibrasyonu henüz sağlamamıştır. Güçlü AR(1) bağımlılığı altında üç, altı, on iki bloklu circular moving-block bootstrap testleri de başarısızdır. Güvenli baskınlık ve sınırlı arşiv belleği birbirinden bağımsız mekanizmalardır.

## Yeniden çalıştırma

```bash
pip install numpy pandas pytest
python tools/calibrate.py --repetitions 80 --n-boot 350 --block-len 6 --output-dir results
python tools/sensitivity.py
python tools/real_train_diagnostic.py
PYTHONPATH=reference_snapshot pytest -q tests
```

İçeriğin kaynağı `reference_snapshot/crmt_edge_ems/{risk,dominance,archive}.py` — bire bir orijinal CRMT Git blob SHA doğrulanır. Gerçek TRAIN ham kaynak `reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip` içinde bulunur. R16 içindeki `seed1001` özgün çalışma commit kaydındaki `UNRECORDED_LOCAL_SHA` bu paket tarafından düzeltilmez.

## Çıktılar

- `config/R21_CALIBRATION_CONFIG.json`: keşifsel deney koşulları
- `results/R21_EXPERIMENT.json`, `R21_SUMMARY.csv`, `R21_PER_REPETITION.csv`: 1600 kayıt ve özet
- `results/R21_BLOCKLEN_SENSITIVITY.csv`: L=3/6/12, n=80 duyarlılığı
- `results/R21_REAL_TRAIN_PAIRING_DIAGNOSTIC.json`: üç gerçek C1/A1 TRAIN kaynağının ortak blok/gün denetimi
- `docs/R21_BAGIMLILIK_VE_ARSIV_GUVENI_KALIBRASYON_TR.md`: ayrıntılı bilimsel rapor
- `tools/`: özgün modülü kullanan kalibrasyon ve kaynak denetleyicileri
- `tests/`: regresyon testleri
- `SHA256_MANIFEST.json`: ZIP içine alınan bütün dosyaların hash kayıtları

## Bilimsel engeller

R19 C1/A1 B10 prospektif birincil deney, R20 eşit toplam CPU hesabı, gün/tesis seviyesinde güvenilir hata kalibrasyonu ve daha önce kullanılmamış yeni bağımsız TEST **henüz yapılmadı**. Asıl GitHub `src/` ve tarihsel kayıtlar değişmemiştir.
