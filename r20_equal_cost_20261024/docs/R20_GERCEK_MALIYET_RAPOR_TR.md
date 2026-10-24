# CRMT R20 — İkinci P0 adımı: Eşit bütçe, gerçek arşiv maliyeti ve ölçüm protokolü

**24 Ekim 2026 — Tarihsel TRAIN yeniden denetimi ve küçük altkümeli gerçek kod mikro-benchmark'ı.**  
**Statü:** `E1_RESOURCE_ACCOUNTING_DESIGN_COMPLETE_HISTORICAL_EXPLORATORY`; `E2_EQUAL_TOTAL_CPU_EXPERIMENT_NOT_RUN`; **yeni bağımsız TEST: NO-GO.**

## 1. Araştırma hedefi ve bilimsel estimand

R19'un asıl sorusu değişmez: C1/A1 koşulunda F1 ve F0, aynı DISCOVERY-TRAIN 12.600 kontrolcü×blok olayını ve **B=K=10 çıktı kısa listesi** kısıtını kullanırken, ayrıca ayrılmış AUDIT-TRAIN ampirik Pareto cephesindeki kayıp payını farklılaştırıyor mu? Birincil uç: tohum başına `MissRate(F1) - MissRate(F0)`.

R20, **performans sonucunu değil kaynak kullanımını ölçen bağımsız bir yardımcı protokoldür**. Aşağıdaki eşitlikler birbirinin yerine geçmez:

1. **Eşit simülatör budgetı:** `Nsim(F0)=Nsim(F1)=12.600`, hatta aynı `(candidate_id,block_id)` kümesi.
2. **Eşit çıktı kısa listesi:** `K(F0)=K(F1)=10`; B=10 post-selection export. Bu **algoritma çalışırken aynı arşiv belleği** değildir.
3. **Eşit native arşiv kapasitesi:** İki yöntemin *her ara adımda* saklayabildiği aday sayısına B=10 sert limit; kaynakta henüz uygulanmıyor. Sonradan budama bu testi karşılamaz.
4. **Eşit toplam hesaplama maliyeti:** `sim + optimizer + archive/bootstrap + selection (+ ortak AUDIT)` CPU; eşitlik veya kabul edilecek eşdeğerlik marjı önceden yazılmalı. R19/R20 birinci karşılaştırma için bunu iddia etmiyor.
5. **Eşit gerçek-zaman donanım kapasitesi:** P99 karar süresi, peak native RSS ve edge donanımda zaman sınırı; ayrıca test edilmesi gerekiyor.

**E1 (R19'un yardımcısı):** Eşit simülatör olayları ve B10 son çıktı için arşiv sadakati; gerçek arşiv maliyeti ayrı kovaryant/guardrail olarak raporlanır. **E2 (başka estimand):** Aynı toplam CPU/duvar-bütçesinde her F için mümkün olan performans; F1 daha fazla bootstrap harcarsa gerçek simülatör bütçeleri farklılaşabilir. E2 ayrı protokol gerektirir. İki estimand aynı makale tablosunda karıştırılmaz.

## 2. Kaynak doğruluğu ve metrik anlamı

Kaynak: özgün `CRMT_R16_Tum_Kalan_Ciftler_Gercek_Veri_Kanit_Paketi.zip` yeniden arşivlenmeden **aynen** 
`reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip` olarak paketlendi. İçindeki `run_summary.json` SHA-256 kayıtlarından her gerçek `candidate_metrics.csv`, `ledger.csv`, `optimizer_front.csv` yeniden kontrol edilir. Ek olarak 12.600 satırlı ledger ile ölçüm çifti **set düzeyinde** ve dört orijinal amaç **değer düzeyinde** karşılaştırılır.

Ölçüm satırındaki `n_ticks`, `mean_cpu_ms` ve `max_cpu_ms` kullanılabilir; `sum(n_ticks × mean_cpu_ms)` her simülasyon koşusundaki **kaydedilmiş tick CPU süreleri üzerinden inşa edilen toplam işlem yükü vekilidir**. Historik F0/F1 *archive/bootstrap CPU*, *end-to-end wall*, toplam enerji veya gerçek cihaz RAM'i hakkında bilgi vermez. `mean_cpu_ms` değerlerinde F0/F1 farklılıkları olabilir; bu benchmark donanım yükü eşitliğinin kanıtı değildir.

## 3. Gerçek TRAIN kaynakları: 10 çift, C1/A1 için 3 çift

R16'da ham 4 dosyalı F0/F1 koşulları eksiksiz bulunan **10 eşli koşulda** her kolun SHA, 12.600 farklı controller-block olayı ve dört amaç değeri kontrol edildi. On çiftin tamamı eşleşti; rapor `results/R20_ALL10_HISTORICAL_COST_AUDIT.json` içinde. Bunlar **yeni bağımsız tohum** değildir.

R19'un birincil C1/A1 sorusuna uyan kaynakları yerelde tam bulunan üç tohum:

| Tohum | F0 doğal arşiv | F1 doğal arşiv | F0 tick CPU proxy (ms) | F1 tick CPU proxy (ms) |
|---:|---:|---:|---:|---:|
| 1001 | 18 | 236 | 1.116.747,77 | 1.106.361,70 |
| 1004 | 22 | 240 | 1.130.218,33 | 1.006.628,78 |
| 1005 | 17 | 237 | 1.116.486,15 | 1.113.537,95 |

Her F kolunda 12.600 `candidate_metrics.csv` satırı ve ledger olayı bulunmaktadır; C1/A1 için 9 milyonun üzerinde tick kaydı vardır. F0/F1 aynı controller–block olaylarına ve aynı bilimsel amaçlara sahiptir. CPU vekillerinin farklı çıkması, çalışma zamanı gürültüsü, kod yolu, cihaz koşulları veya ölçüm mekanizması gibi nedenleri ayrıştırmadan F1'in daha hızlı simülasyon yaptığını söylemeye **izin vermez**.

**Önemli SHA istisnası:** `seed1001/C1_F1_A1` orijinal `run_summary.json` içinde `UNRECORDED_LOCAL_SHA` taşır. Ham dosya bütünlüğü doğrulandı, çalıştırmanın özgün kod commit'i hâlâ `UNRESOLVED`. Sonradan HEAD kanıtıyla değiştirilmedi.

## 4. Orijinal GitHub arşiv kodu mikro-benchmark'ı

R20'nin `reference_snapshot/crmt_edge_ems/{risk,dominance,archive}.py` dosyaları **GitHub'daki asıl modüllerin bire bir Git blob kopyalarıdır**; SHA-1 git-blob kimlikleri:

- `risk.py`: `edee0d3361691535330419d0203757d0b3624638`.
- `dominance.py`: `c0fa644839407aaf1ac388a5082435a3a446be29`.
- `archive.py`: `bb644663febea3990ebeb23f47e403ab0c8070f3`.

Tüm üç SHA bağımsız çalışma dizininde kod tarafından tekrar doğrulanır. CRMT ana deposunun `src/` kodu ve 2026-10 tarihli tarihsel TRAIN çıktıları değiştirilmedi. Instrumentation, F1'in kaynak fonksiyonuna yalnız dışarıdan sayım sarmalı ekler ve bunu geri alır.

İki özgün C1/A1 TRAIN koşulundan (1004,1005) deterministik ilk 8, 16, 32 kontrolcü alındı; **orijinal 256 tam kontrollü optimizasyon koşusu değil**. F0 ve F1 aynı blok kayıtlarından hesaplanan `mean + 0.5 × top-k-tail` risklerini kullanır. F1'in Bootstrap sayısı *bilerek 200* tutulmuştur (tarihsel n_boot=1000/2000 ile aynı ölçüm sayısı değildir). Ölçülen arşiv hesabı için `process_time_ns`, `perf_counter_ns`; Python tahsis tepesi ayrı ve ikinci `tracemalloc` koşusunda ölçülür; tracemalloc CPU overhead'i zaman tablosuna katılmaz. Bu basit laboratuvar mikro-benchmark'ı tek geçişlidir; güven aralığı yoktur ve donanım standardizasyonu yoktur.

| Replay altkümesi | F0 CPU süreleri (ms) | F1 CPU süreleri (ms) | F1 bootstrap pair çağrısı |
|---:|---:|---:|---:|
| 8 kontrolcü | 0,25 / 0,21 | 105,06 / 98,46 | 56 / 56 |
| 16 kontrolcü | 0,75 / 0,76 | 447,52 / 434,57 | 240 / 240 |
| 32 kontrolcü | 2,97 / 2,23 | 1.680,52 / 1.636,47 | 986 / 982 |

Değerler tek makine, tek tekrar ve iki tohumdan gelir. Bu gözlemlerle **F1'in arşiv maliyetinin çok daha yüksek olabileceği** görülür; bu sonuç gerçek 256-adaylık geçmiş CPU maliyetinin sayısal tahmini veya genellenebilir hız oranı değildir. Bellek ölçümü `tracemalloc` Python izlenebilir tahsisleriyle sınırlıdır; gerçek peak RSS arşiv bazında ayrı ölçülmemiştir.

## 5. Yeni koşular için somut ve fail-closed ölçüm sözleşmesi

`tools/live_profiler.py` daha sonra çalıştırılacak *yeni* kontrollü deney için additif instrumentation sağlar. Bir CPU/wall fazını ölçmek için `with profiler.measure('archive'):`; simülatör olayını kaynak defterine eklemek için `profiler.reserve_actual_evaluation(candidate_id,block_id)`; karşılaştırmalar için `record_pair_test(...)`; doğal arşiv işgalini kaydetmek için `record_archive_candidate_count(...)` çağrılır. Fazlar *iç içe geçemez*, böylece aynı CPU süresi iki kez raporlanmaz.

Beş faz vardır: `sim`, `optimizer`, `archive`, `selection`, `audit`. Her faz hem monotonic wall hem process CPU ns üretir. Her koşu Git commit'i, ortak ledger SHA, ortam SHA, n=12.600, peak native arşiv büyüklüğü, B10 çıktısı, bootstrap ayarı, karşılaştırma sayısı ve kaynak kullanımı profilini **zorunlu** tutar. Özgün kaynakları değiştirmeden wrapper ile çalışabilir, ancak tam `CRMTStudy` değerlendirme/optimizer hatlarına entegrasyonu henüz yapılmadı; dolayısıyla şimdiki tarihsel kayıtlar o yeni alanların var olduğunu iddia etmez.

`tools/cost_audit.py:paired_cost_check` F0/F1 için tek tohum, aynı gerçek Git SHA, aynı ledger SHA, aynı donanım fingerprint'i, aynı 12.600 olay ve tam B10 koşulunu kontrol eder. Eksik faz zamanlaması (`sim` ve `archive`) veya CPU/RSS kaydı olan çiftler **engellenir**. Fazların CPU toplamı sıralı tek süreç yorumudur; thread/process havuzu veya eşzamanlı CPU/duvar için ayrı process tree toplama gereklidir.

### Replikasyon komutları

```bash
python tools/cost_audit.py --r16-zip reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip --all-available --out results/verify_all_10.json
python tools/reference_benchmark.py --r16-zip reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip --out results/replicate_microbenchmark.json
python -m pytest tests -q
```

## 6. Güvenlik, istatistik ve bilimsel iddia kapıları

- **P0 / gerçek CPU ve bellek eşitliği:** Tarihsel çalıştırmalarda native archive wall/CPU/peak RSS kaydı yok. Dolayısıyla eşit toplam maliyet sonucu **NOT ESTABLISHED**.
- **P0 / B=10 native kapasite:** R19 yalnız çıktı B10 uyguluyor; F1 kendi doğal arşivinde 200+ üye saklamaya devam edebilir. Native B10 altında yöntem performansı test edilmedi. Bundan ayrı bir yeni algoritma/estimand gerekli.
- **P0 / yeni 30 tohum:** R19'daki 2001–2030 seed planı güç açısından kesin onaylı değil, gerçek koşular yapılmadı. Deneyin kaynağı/embargosu dışarıdan kilitlenmeden çalıştırılmamalı.
- **P0 / yeni bağımsız TEST:** Mevcut 78 iç TEST ve OPSD maruziyetli. R20 hiçbir TEST değerlendirmesi yapmıyor. **NO-GO**.
- **P1 / tarihsel missing SHA:** `seed1001/C1_F1_A1` çalıştırma anındaki kod SHA eksik. Analiz kayıt düzeyinde raporlanıyor; gerçek commit bilinmiyor.
- **P1 / donanım:** Aynı edge hedefinde P99 gecikme, ısı/bellek, fail-safe SOC/şebeke fiziksel sınır ve elektriksel doğrulama yok.
- **İstatistiksel etki:** R20 zamanlarındaki farklılıklar performans *p-değeri*, generalizable CPU ratio veya R19'un birincil fayda testini kanıtlamaz.

### Nihai karar

**R20 E1 maliyet muhasebesi tasarımı ve gerçek TRAIN'de kısmi yeniden denetimi TAMAMLANDI.** R19'un birincil hipotezini *sınayan* yeni gerçek denetim yapılmadı. E2 eşit toplam CPU ve native B10-sert-limit deneyleri **ayrı, prospektif ve yürütülmemiştir**. Dondurulmuş GitHub `main/src/` ve tarihsel deney ham dosyalarına dokunulmadı. EAAI için yeni üstünlük / fiziksel saha güvenliği **NO-GO**.
