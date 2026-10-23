# CRMT R9 — Tarihsel TRAIN kaynak eşlemesi ve bilimsel preflight

**23 Ekim 2026 — retrospektif kanıt denetimi; YENİ R9 DENEMESİ / yeni bağımsız TEST değildir.**

> **DÜZELTME / geçerli güncel kapsam:** [R9 kaynak commit engeli ve 8/20 bayt kontrolü](R9_TRAIN_PROVENANCE_BLOCKER_20261023.md). 40 koşulun 39'unda beklenen dondurulmuş commit bildirilmiştir; **seed1001/C1_F1_A1** summary'sinde `original_git_sha=UNRECORDED_LOCAL_SHA` vardır. Önceki "metaveri tutarsızlığı 0" ifadesi, bu alanı kontrol etmediği için genellenemez. Gerçek CSV baytlarından doğrulanan F0/F1 çift sayısı artık **8/20**. Yedi çift mevcut depo preflight aracıyla yeniden denetlendi; ayrıca ikinci yerel doğrulayıcı kullanıldı. Kalan 12 çift tamamlanmamıştır.

## Kaynak kapsamı

- Ana depo: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems
- Tek `main` envanteri: `reproducibility/r9_historical_train_sources_20261023/seed1001.csv` ... `seed1005.csv`.
- Google Drive 5 seed × 8 C/F/A koşulu = **40/40** koşul dosya seti.
- Her koşulda `run_summary.json`, `candidate_metrics.csv`, `ledger.csv`, `optimizer_front.csv` mevcut, boyutları sıfırdan büyük: **160/160 kaynak dosya envanterlendi**.
- 40 JSON run summary tekrar okundu; C/F/A, TRAIN rolü, aday/bütçe ve kaynak manifesti alanları beklenen değerlere uyumlu. **Ancak kaynak commit kimliğinde 1/40 açık sorun** vardır (`seed1001/C1_F1_A1`: `UNRECORDED_LOCAL_SHA`). Bkz. düzeltme eki.
- Aynı (seed,C,A) için F0/F1 **20/20 çiftte ledger.csv SHA-256 kimliği eşleşiyor** (run_summary'de beyan edilen hashler). Buna karşılık **20/20 çiftte candidate_metrics.csv ham SHA-256 farklı**. Sadece hash farkıyla dört amaç değişmiş sayılmaz; her çift gerçek byte düzeyinde denetlenmelidir.
- F0 toplam TRAIN arşiv üyesi **1672 / 20 = 83.60**, F1 **4539 / 20 = 226.95**, fark **+143.35**. Bu B kapasite eşlemesi yapılmadan gözlenen tarihsel sonuçtur; F1 üstünlüğünü göstermez.

## İlk kaynak-bayt pilotu — seed1001 C0 A0 (tarihsel ilk denetim; genel kapsam artık 8/20)

Aşağıdaki iki karşılıklı Drive klasörünün orijinal CSV'leri ve özetleri tek tek indirildi:

- F0: https://drive.google.com/drive/folders/1KfclofV-GJ8y0uYcTk_jbqsDWjrMlRkt
- F1: https://drive.google.com/drive/folders/1_koNld5Pmck3RPExqOaiKk7XHDR2LjXB

**Her iki koşulun 3 CSV dosyasının gerçek bayt SHA-256'sı, ilgili `run_summary.json` kayıtlarıyla eşleşti (6/6).**
Her birinde 12.600 ledger ve candidate_metrics satırı, 256 farklı aday ve 210 TRAIN blok kaynağı bağlamı doğrulandı.
F0 ve F1'in ledger sırası ve (aday,blok) çiftleri tamamen aynı; `candidate_metrics.csv`'de **bilimsel amaçlar ve diğer non-timing alanlar 12.600 satırda aynı**.

- Değişen `mean_cpu_ms` satır sayısı: **12600**.
- Değişen `max_cpu_ms` satır sayısı: **12599**.
- F0 doğal arşiv büyüklüğü **143**, F1 **250**; bu üyeliklerin aynı olması gerekmez.

**Önemli sınır:** Bu bölüm ilk seed1001/C0_A0 pilotunun özgün raporudur; sonradan aynı yöntemle yedi ek çift doğrulanarak güncel kapsam **8/20** olmuştur. **Kalan 12 çiftin** bilimsel alan eşitliği hâlâ doğrulanmamıştır. Güncel toplu kanıt için düzeltme ekine bakınız.

## Yeni araç

`tools/r9_equal_capacity_20261023/r9_train_pair_preflight.py`

- Dosya SHA-256, frozen kaynak/manifest, C/F/A koşul eşlemesi, 12.600 bütçe, CSV şemaları, TRAIN-only satırları, 256 aday ve archive membership sayısını kontrol eder.
- F0/F1 ledger olaylarını ve aynı aday–blok üzerindeki non-timing bilimsel alanları kıyaslar; `mean_cpu_ms` ve `max_cpu_ms` ölçüm dalgalanmalarını ayrı raporlar.
- Başarısızlık halinde `R9_PREFLIGHT_BLOCKED` durumu ve nonzero exit kodu verir. Hiçbir EMS simülasyonu veya VAL/TEST yapmaz.
- Sentetik testler genişletildi: **13 preflight + 22 R9 kapasite = 35/35 yerel test başarılı**. Tarihsel gerçek kaynak bayt pilotları: **8 çift** (beş tohumun hepsinden en az bir çift) geçti; ayrıntılar güncel [kaynak commit ve byte denetimi ekinde](R9_TRAIN_PROVENANCE_BLOCKER_20261023.md). Güncel GitHub CI kontrolü ayrıca raporlanır.

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
2. Henüz tüm 20 F0/F1 çiftinin gerçek CSV içerik eşitliği ve arşiv dosya kimlikleri teker teker doğrulanmadı (8/20 çiftin gerçek dosyaları kontrol edildi). Ayrıca seed1001/C1_F1_A1'in özgün kaynak commit'i belirsizdir.
3. Eşit efektif kapasite B, K20, backfill etkisi ve kontrolcü seçim sonlanımı hâlâ **taslak**.
4. Yeni bağımsız kör TEST veri kökeni, tarih/saha maruziyeti, prereg ve safety veto henüz kilitlenmedi.
5. Eski TRAIN/VAL/internal TEST verilerini yeni bağımsız TEST diye sunmak yasaktır.

**Kanıt statüsü:** INPUT DISCOVERY 40/40 COMPLETE; EXPECTED SOURCE-COMMIT DECLARED 39/40; JSON DECLARED-LEDGER PAIR SHA 20/20 MATCH; ACTUAL BYTE PAIR 8/20 VERIFIED; R9 NEW INDEPENDENT TEST: **NO-GO**.
