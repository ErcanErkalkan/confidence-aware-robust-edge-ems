# CRMT R9 eşit kapasite ve bütçe ön-prototipi

**DRAFT — Confirmatory TEST koşma izni vermez.** Bu dizin tek `main` projesi için çalıştırılabilir TRAIN-sonrası kapasite prototipidir. Orijinal F0/F1 kontrolcüsünü, tarihi K20 sıralamalarını veya dondurulmuş deneyleri değiştirmez.

`r9_capacity.py` tam JSON giriş ister. Alanlar: `source_role="TRAIN"`, pozitif tamsayı `capacity`, `k`, `expected_evaluations`, bütün havuzu kapsayan 4 minimizasyon amaçlı `train_scores` sözlüğü, farklı `f0_archive` / `f1_archive` aday listeleri ve aynı candidate/block çiftlerini taşıması gereken `f0_evaluations`, `f1_evaluations`. Ek TEST/VAL veri alanları reddedilir. Arşiv boşsa, bilinmeyen ID varsa, amaç sonsuz/NaN ise, loglarda tekrar veya eşitsizlik varsa işlem durur.

Kod kapasiteye kadar TRAIN ağırlıklı Chebyshev/L1/ID sırasıyla budar; eksik kapasiteyi arşiv dışı ortak TRAIN adaylarından *aynı sıralama ile* tamamlar. **Backfill F0/F1'in doğal arşivini dönüştürür**: bu nedenle sonuç yalnız yeni post-processing politikasına aittir. K, kapasitenin altında/aynı; nihai K sırası deterministik. Kaynak ve risk hücresi bağımsızca doğrulanmadan gerçek çalışma sonuçları teyit edici değildir.

Örnek:

```bash
python tools/r9_equal_capacity_20261023/r9_capacity.py --input-json tools/r9_equal_capacity_20261023/example_synthetic_pair.json --output-json synthetic_output.json
python -m pytest -q tests/test_r9_capacity_policy.py
```

`example_synthetic_pair.json` tamamen **sentetik** veridir (8 aday, B4, K2). Bu örnekten herhangi bir yayın sonucu çıkarılmaz. Bilimsel sınırlar: `docs/R9_EQUAL_CAPACITY_POLICY_DRAFT_20261023.md`.
