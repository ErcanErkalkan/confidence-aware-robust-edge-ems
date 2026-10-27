# CRMT P1 + P2 ileri mühendislik doğrulaması — 27 Ekim 2026

## Doğrulanan sonuç

- P1: Dinamik dönemsel şebeke sınırları, mode-flip sayacı ile `flip_per_day` uyumu, site limit tutarlılığı ve sahte kaynak kabulüne karşı koruma.
- P2: Kaynak `ReplayBlock` ve `risk_calibrated_score` kodu **tarihsel davranışı korumak için değiştirilmedi**. Bunun yerine `StrictReplayBlock` ve `StrictReplayEvaluator` adlı **opt-in** doğrulama katmanı eklendi.
- Kaynak karşı örnekleri: Eski `ReplayBlock` sonsuz `base_kw` ve kesirli `peak_flag=.5` değerlerini kabul eder; eski `aggregate_objectives` NaN risk gözlemlerini sessizce atar. P2 katmanı bunları reddeder. Bunlar sentetik, doğrudan kodla tekrarlanan örneklerdir.
- V2 denetimi saat dilimini, blok süresini, beklenen adım sayısını, kesin 0/1 peak_flag değerlerini, tüm satırların sonlu olmasını ve dört amaçta eksiksiz desteği zorunlu tutar. `StrictReplayEvaluator` sonraki hatalı blokları da kaynak bütçe rezervasyonundan önce denetler.
- **68 / 68 hedefli test geçti**, sıfır hata; iki sentetik FutureWarning testi temizlendikten sonra `-W error` ile çalıştırıldı. Kod `compileall` ile denetlendi. P2 yamasının `git apply --check` ve izole uygulaması geçti.
- Önceden kayda geçmiş **297 testlik tam paket yeniden çalıştırılmadı**. Bu paket yayın onayı, prospektif R19, kaynak lisansı veya independent TEST kanıtı değildir.

## Uygulama sırası (yalnızca 27 Ekim remediation checkout/özgün sürümü üzerinde)

```bash
# Düzgün, izole Git çalışma kopyasında; önce değişiklikleri kontrol edin.
git status --short
git apply --check CRMT_P1_GUVENLIK_VE_R19.patch
git apply CRMT_P1_GUVENLIK_VE_R19.patch
git apply --check CRMT_P2_KATI_REPLAY.patch
git apply CRMT_P2_KATI_REPLAY.patch
python -m pytest -q -W error tests/test_crmt_p1_regressions.py tests/test_p2_strict_replay.py
python -m pytest -q tests
```

**Önemli:** İlk yama P0-öncesi, 27 Ekim 2026 Codex remediation çalışma kopyasındaki `safety` ve `external_source_gate` kaynak baytlarını temel alır; GitHub `main` için tasarlanmamıştır. Eğer P1 yaması zaten uygulanmışsa **bir daha uygulamayın**, yalnız P2 yamasını deneyin. Bazı eski modül testleri `tests/test_crmt_p1_regressions.py` dışında hedefli P1 yerel altkümeye aittir. Tam 297 testi koşturmadan yeni toplam testi başarı sayısı vermeyin.

P2 yalnız yeni modül ve test dosyaları ekler; gerçek data ingest pipeline henüz `StrictReplayBlock` sınıfına bağlanmış değildir. Sonraki entegrasyonda bu katman **yeni ve açık deney protokolü sürümüyle** kullanılmalı; tarihsel donmuş sonuçlar sessizce yeniden etiketlenmemelidir.

## R19 önemli matematiksel sonuç

256 adaydan iki bağımsız K=10 shortlist seçilirken, AUDIT Pareto kümesi P için en fazla mutlak MissRate farkı `(min(10,P) - max(0,10-(256-P))) / P` olur. P>200 durumunda 0,05 mutlak etki eşiği imkânsızdır. Bu sonuçlar tasarım hassasiyet analizidir; henüz P'nin dağılımı bilinmez ve prospektif R19 koşulmamıştır.

## Açık kapılar

`SOFTWARE_READY=PARTIAL`, `REPRODUCIBILITY_READY=PARTIAL`, `R19_PROSPECTIVE_READY=NO`, `INDEPENDENT_TEST_READY=NO`, `MANUSCRIPT_V13_READY=PARTIAL`. Linux/Windows/Python matrisi, full-day replay, veri hakları, bağımsız ön kayıt, SCIENTIFIC TEST ve fiziksel güvenlik yetkilendirmesi açık kalır.