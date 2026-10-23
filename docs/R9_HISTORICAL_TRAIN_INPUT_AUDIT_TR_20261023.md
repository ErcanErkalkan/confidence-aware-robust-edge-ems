# CRMT R9 — Tarihsel TRAIN kaynak eşlemesi ve bilimsel preflight

**23 Ekim 2026 — retrospektif kanıt denetimi; YENİ R9 DENEMESİ / yeni bağımsız TEST değildir.**

## Kaynak kapsamı

- Ana depo: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems
- Tek `main` envanteri: `reproducibility/r9_historical_train_sources_20261023/seed1001.csv` ... `seed1005.csv`.
- Google Drive 5 seed × 8 C/F/A koşulu = **40/40** koşul dosya seti.
- Her koşulda `run_summary.json`, `candidate_metrics.csv`, `ledger.csv`, `optimizer_front.csv` mevcut, boyutları sıfırdan büyük: **160/160 kaynak dosya envanterlendi**.
- 40 JSON run summary okundu ve `condition_id`, seed, `TRAIN`, `candidate_count=256`, `train_budget_used=12600`, C risk ağırlığı ve F/A mod etiketleri denetlendi; metaveri tutarsızlığı **0**.
- Aynı (seed,C,A) için F0/F1 **20/20 çiftte ledger.csv SHA-256 kimliği eşleşiyor** (run_summary'de beyan edilen hashler). Buna karşılık **20/20 çiftte candidate_metrics.csv ham SHA-256 farklı**. Sadece hash farkıyla dört amaç değişmiş sayılmaz; her çift gerçek byte düzeyinde denetlenmelidir.
- F0 toplam TRAIN arşiv üyesi **1672 / 20 = 83.60**, F1 **4539 / 20 = 226.95**, fark **+143.35**. Bu B kapasite eşlemesi yapılmadan gözlenen tarihsel sonuçtur; F1 üstünlüğünü göstermez.

## Gerçek byte düzeyi pilot doğrulama — yalnız seed1001 C0 A0

Aşağıdaki iki karşılıklı Drive klasörünün orijinal CSV'leri ve özetleri tek tek indirildi:

- F0: https://drive.google.com/drive/folders/1KfclofV-GJ8y0uYcTk_jbqsDWjrMlRkt
- F1: https://drive.google.com/drive/folders/1_koNld5Pmck3RPExqOaiKk7XHDR2LjXB

**Her iki koşulun 3 CSV dosyasının gerçek bayt SHA-256'sı, ilgili `run_summary.json` kayıtlarıyla eşleşti (6/6).**
Her birinde 12.600 ledger ve candidate_metrics satırı, 256 farklı aday ve 210 TRAIN blok kaynağı bağlamı doğrulandı.
F0 ve F1'in ledger sırası ve (aday,blok) çiftleri tamamen aynı; `candidate_metrics.csv`'de **bilimsel amaçlar ve diğer non-timing alanlar 12.600 satırda aynı**.

- Değişen `mean_cpu_ms` satır sayısı: **12600**.
- Değişen `max_cpu_ms` satır sayısı: **12599**.
- F0 doğal arşiv büyüklüğü **143**, F1 **250**; bu üyeliklerin aynı olması gerekmez.

**Önemli sınır:** Yukarıdaki bilimsel alanların satır-satır birebir eşit olduğu bulgusu **yalnız 1/20 gerçek çift** için bağımsız byte denetimidir. Diğer 19 çifte genellenmez. Diğer 19 çiftin SHA'ları özet manifestlerde uyuşmaktadır, henüz tüm gerçek CSV baytları yeniden denetlenmedi.

## Yeni araç

`tools/r9_equal_capacity_20261023/r9_train_pair_preflight.py`

- Dosya SHA-256, frozen kaynak/manifest, C/F/A koşul eşlemesi, 12.600 bütçe, CSV şemaları, TRAIN-only satırları, 256 aday ve archive membership sayısını kontrol eder.
- F0/F1 ledger olaylarını ve aynı aday–blok üzerindeki non-timing bilimsel alanları kıyaslar; `mean_cpu_ms` ve `max_cpu_ms` ölçüm dalgalanmalarını ayrı raporlar.
- Başarısızlık halinde `R9_PREFLIGHT_BLOCKED` durumu ve nonzero exit kodu verir. Hiçbir EMS simülasyonu veya VAL/TEST yapmaz.
- Sentetik test: **12/12 geçti**; gerçek tarihsel pilot: **1 çift (seed1001/C0_A0) geçti**. Tam GitHub CI sonucu GitHub Actions üzerinden ayrıca doğrulanmalıdır.

Çalıştırma:

```bash
python tools/r9_equal_capacity_20261023/r9_train_pair_preflight.py \
  --f0-dir /local/historical/seed1001/C0_F0_A0 \
  --f1-dir /local/historical/seed1001/C0_F1_A0 \
  --seed 1001 --c 0 --a 0 --output-json /local/output/preflight.json
python -m pytest -q tests/test_r9_train_pair_preflight.py
```

## Neden R9 gerçek yürütmesi hâlâ kapalı?

1. TRAIN candidate_metrics içindeki dört blok amacı, R9 policy modülünün beklediği aday başına dört bileşik TRAIN skoruna dönüştürülmeli; C0/C1 risk fonksiyonu, quantile, normalization ve seleksiyon tasarımı nihai kilit olmadan bu dönüştürme doğrulayıcı sonuç diye kullanılamaz.
2. Henüz tüm 20 F0/F1 çiftinin gerçek CSV içerik eşitliği ve arşiv dosya kimlikleri teker teker doğrulanmadı.
3. Eşit efektif kapasite B, K20, backfill etkisi ve kontrolcü seçim sonlanımı hâlâ **taslak**.
4. Yeni bağımsız kör TEST veri kökeni, tarih/saha maruziyeti, prereg ve safety veto henüz kilitlenmedi.
5. Eski TRAIN/VAL/internal TEST verilerini yeni bağımsız TEST diye sunmak yasaktır.

**Kanıt statüsü:** INPUT DISCOVERY 40/40 COMPLETE; JSON DECLARED-LEDGER PAIR SHA 20/20 MATCH; ACTUAL BYTE PAIR 1/20 VERIFIED; R9 NEW INDEPENDENT TEST: **NO-GO**.
