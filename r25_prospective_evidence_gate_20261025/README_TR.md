# CRMT R25 — Prospektif veri ayrımı ve güvenilir kilit doğrulayıcısı

Bu sürüm **gerçek yeni TEST, yeni optimizer çalışması veya doğrulanmış haricî ön kayıt değildir.** R19'un C1/A1, B=K=10 birincil hipotezini koruyan bağımsız veri/ön kayıt hazırlık denetimidir.

## Kontroller

- `python tools/r25_cli.py status --out results/my_status.json`: 9/5/5 tarihsel ortak gün ve R19 kilit eksiklerini, R16 ham kaynakları yeniden analiz ederek raporlar. **Dosya varsa üzerine yazmaz**.
- `python tools/r25_cli.py reserve --input future_inventory_request.json --out reserved_plan.json`: veri *sonuçları değil* yalnız yeni kaynağa ait aday kimliği, tarih ve çift-inverter blok manifestini kabul eder. 7 tam gün embargo bir şema eşiğidir, istatistiksel bağımsızlık kanıtı değildir.
- `python tools/r25_cli.py request-receipt --plan reserved_plan.json --lock selection_lock.json --out attestation_request.json`: R19 seçimi ve R25 planı aynı kaynağa sabitler.
- `python tools/r25_cli.py verify-receipt --envelope attestation_request.json --input signed_receipt.json --pinned-public-key HEX --out signature_check.json`: test amaçlı imzayı bile doğrulasa kurumsal yetki/ön kayıt onayı vermez.
- `pytest -q tests/test_r25_protocol.py`: 30 otomatik test, sahte URL/boolean denetimi dahil.

**Bağımlılıklar:** Python 3.11+, NumPy, cryptography, pytest. Haricî ağa erişim gerekmez.

## Veri ve kod kökeni

`reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip`: SHA `15a1a6aff3ca4410ccad420b261f50480d89d5effb3038a461dab04fb44255bc` (eski görülen TRAIN).

`reference_snapshot/primary_hypothesis_R19.py`: orijinal R19 analiz kodunun değişmeyen salt-okunur kopyası.

`tools/r24_source_verifier.py`: orijinal R24 gerçek ham kaynak denetim kodunun kopyası; R25 eski rapora güvenmek yerine çalıştırır.

`config/R25_TRUST_ROOT_TEMPLATE.json`: **imzacı anahtarı ve dış ön kayıt onayı boş**. Pakette gerçek açık veya özel imzacı anahtarı yoktur.

Bilimsel gerekçeler ve henüz kapanmamış tüm gereksinimler için `docs/R25_TURKCE_BILIMSEL_VE_TEK_NIK_RAPOR.md` dosyasına bakın.
