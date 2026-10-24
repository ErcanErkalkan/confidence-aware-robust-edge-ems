# CRMT R19 — Birinci P0 adımının tam çözümü: Tek birincil bilimsel soru

**Tarih:** 24 Ekim 2026  
**Statü:** INTERNAL DESIGN FREEZE **TASLAĞI**; dış ön-kayıt DEĞİL; yeni deney sonucu DEĞİL; bağımsız TEST DEĞİL.  
**Çalışma:** Confidence-Aware Risk-Calibrated Multiobjective Tuning for Edge Microgrid Energy Management under Distribution Shift.  
**Temel kaynak:** GitHub `ErcanErkalkan/confidence-aware-robust-edge-ems` ve R18-v2'nin 40 özgün arşiv CSV kanıtı.

## 1. Neden bu soru?

R18-v2'deki 20 eşleştirilmiş F0/F1 TRAIN arşivi SHA doğrulamasından geçti. F0 doğal arşiv ortalaması 83,60, F1 ortalaması 226,95. Bu fark, confidence yaklaşımının faydasını kanıtlamaz: F1'in daha fazla aday saklaması tek başına recall'u yükseltir. 20 eşleştirilmiş tarihsel K20 kısa listesinin aynı olması da eski dağıtım seçimine özgü F etkisinin olmadığını gösterir. İki koşulda F0 üyesi `CRMT-c0089` F1 arşivinde yoktur; **F0 daima F1 altkümesidir** iddiası yanlıştır.

Bu nedenle birincil soru şu tek, yanlışlanabilir biçimde tanımlanmıştır:

> **C1/A1 koşulunda, aynı 12.600 DISCOVERY-TRAIN candidate×block olayını kullanan F0 ve F1 arşivleri, her kolda arşiv dışı backfill olmadan B=K=10 adaylık kısa listeye indirgendiğinde, ayrı AUDIT-TRAIN bloklarıyla oluşturulan ortak ampirik Pareto referansını kaçırma oranı bakımından farklı mı; fark F1 lehine mi?**

**Tek birincil uç:** Seed başına kaçırılan Pareto referans oranının F1 eksi F0 eşli farkı. Diğer bütün çıktılar ikincildir.

Bu seçim **mevcut tarihsel sonuçlar incelendikten sonra** yapılmıştır; tarihsel R9 için 'ön kayıtlı' değildir. Yeni tohumların tasarım kilidi deneyden önce zaman damgalı depo commit'i ve ayrı uygunluk denetimiyle kanıtlanmalıdır. Güncel dosya tek başına onaylı ön kayıt sayılmaz.

## 2. Tanımlar, H0/H1, ölçü birimi

Dört hedefin tamamı minimize edilir: (1) `cap_violation_pct_total`, (2) `lfp_cycle_loss_pct`, (3) `ramp95_kw_per_min`, (4) `flip_per_day`.

Her kontrolcü için risk vektörü `mean + 0.5 × top-k-tail mean`, q=0.90, k=ceil(0.1×n), minimum 1 bloktur. Bu, risk modülündeki **aynı ampirik tahmincidir**; parametrik gerçek CVaR ve gerçek popülasyon olasılığı olduğu iddia edilmez.

- *S_{F,s}*: seed `s` ve F∈{F0,F1} için, yalnız DISCOVERY-TRAIN risk skorlarıyla sıralanmış doğal arşivden ilk on kontrolcü. B=K=10. Arşiv üyesi olmayan kontrolcüyle backfill yasaktır.
- *P*_{s}: Aynı seed içindeki **256 kontrolcünün tamamı**, aynı ayrı AUDIT-TRAIN bloklarında yeniden değerlendirildiğinde dört ampirik risk hedefine göre baskılanmayanlar.
- *M_{F,s} = |P*_{s} \ S_{F,s}| / |P*_{s}|*: 0 iyi, 1 kötü; sadece ampirik AUDIT referansını ölçer.
- *D_s = M_{F1,s} − M_{F0,s}*: Negatif, F1 lehinedir. **Analiz birimi seed**, kontrolcü, blok veya yöntem-seed alt satırı değildir.

**H0 (iki taraflı test için):** Seed düzeyindeki eşli farkın işaret-değiştirme dağılımı bakımından sıfır konumlu olması; **H1:** Fark sıfır değildir. F1 lehine destek ancak `mean(D_s)<0` olduğunda, aşağıdaki işaretli test ve asgari önem eşiği birlikte sağlandığında yorumlanır. Kullanılan işaret değiştirme testinin sonlu örneklem exact anlamı, farkların işaret simetrisi/exchangeability varsayımına bağlıdır; bu varsayım doğrulanmadan genel ortalama-null hipotezine kesinlik garanti edilmez.

**Pratik önem eşiği (araştırmacı önerisi):** En az 0,05 mutlak kaçırma oranı azalması (5 yüzde puanı), final ön kayıt öncesi araştırma ekibi tarafından teknik/klinik/ekonomik gerekçeyle yeniden değerlendirilmesi gerekir. Taslak eşiği tarihsel gözlemlerden kazanılmış bir güvence değildir.

## 3. Tek faktörlü kıyas: neden C1/A1 sabit?

Ana hipotez **F** mekanizmasına aittir. Confounding'i önlemek için C=1 (λ=0,5), A=1 (adaptif blok tahsisi) sabit. F0/F1 için **tam aynı** 12.600 `(candidate_id, block_id)` değerlendirme olayı sağlanmalı. F1 bootstrap vs F0 archive inşası ayrı çalışır; algoritma maliyetini ölçmek için her ikisinin native arşiv CPU, duvar-zamanı, peak RSS ve karşılaştırma sayısı ayrıca kaydedilmelidir.

Yalnızca ortak simülatör izi eşitliği, **toplam CPU/memory eşitliği değildir**. B=10 burada **post-archive export / selection capacity** sınırıdır, native arşiv tutma kapasitesinin algoritma boyunca B ile sınırlanması değildir. Dolayısıyla deneyin ana estimand'ı *eşit çıktı kapasitesinde arşiv sadakati*; *eşit native bellek bütçesinde edge deployability* değil.

## 4. TRAIN split ve sızıntı yönetimi

Şu an dondurulmuş OpenCEM tarihsel manifesti 406 blok: 210 TRAIN, 118 VAL, 78 daha önce incelenmiş TEST. Eski OPSD OOD verileri de incelenmiştir. **Yeni AUDIT, yalnız 210 TRAIN içindeki yeniden bölme** olup bağımsız, kör veya yeni TEST sayılamaz.

Yeni seed çalışma protokolünde 210 TRAIN blok, aynı takvim gününün iki inverterinin farklı taraflara düşmemesini sağlayacak biçimde ortak `group_id` ile etiketlenir. Yaklaşık %70 DISCOVERY, %30 AUDIT (tavsiye edilen en az 60 AUDIT bloğu) hedeflenir, ancak grup bütünlüğü ve gerçek zaman pencerelerine göre nihai sayı seçilir. Zaman komşuluğu / look-ahead embargo penceresi yeni adaylar değerlendirilmeden kilitlenmelidir. Kod her blok ID'sinin tekil olduğunu, DISCOVERY ve AUDIT'in grup kimliklerinin kesişmediğini ve AUDIT bloğunun DISCOVERY ledger'ında kullanılamadığını denetler. **Kod tek başına fiziksel zaman aralığı çakışmasını, eksik OPSD maruziyetini ve veri haklarını bağımsız olarak ispatlamaz.** Bunlar ek dış denetim kapılarıdır.

Aday üretimi ve tüm 12.600 DISCOVERY değerlendirmesi yalnız DISCOVERY üzerinden yürür. 256 aday kümesi, aday parametreleri, eğitim-değerlendirme ledger'ı, F0/F1 doğal arşiv üyeleri, kullanılan risk fonksiyonu, seçilen B/K ve nihai onluk listeler AUDIT sonuçları açılmadan **immutable dış commit + zaman damgası** ile kilitlenir. Seçim aracı AUDIT skorlarını veya AUDIT satırlarını kabul etmez.

AUDIT aşamasında 256 kontrolcünün *her biri* aynı, tam AUDIT blok kümesinde çalıştırılır. İncomplete/NaN/inf bloklar atılarak seçici biçimde sonuç üretilmez; bilimsel veri eksikliği ayrı neden koduyla fail-closed kalır. Tam AUDIT dört amaç ham verisinden risk yeniden hesaplanır. Ortak ampirik nondomination referansı hesaplanır. AUDIT datasetinin gerçek popülasyon Pareto etiketini verdiği iddia edilmez. Makalenin bu referans üzerinden yalnız diagnostik TR(AIN) sonuç ürettiği belirtilir.

## 5. Neden B=10 ve backfill yok?

40 orijinal R18 arşiv CSV'sinden elde edilmiş 20 eşleştirilmiş tarihsel hücrede **F0'ın en küçük arşiv büyüklüğü 15**; dolayısıyla her hücrede 10 doğal aday mevcut. C1/A1 tarihsel F0 büyüklükleri seed 1001..1005 sırasıyla **18,16,15,22,17**; aynı seed F1 büyüklükleri **236,238,234,240,237**.

B=20 için C1/A1 hücrelerinin dördü (1001,1002,1003,1005) en az 20 doğal F0 adayı sağlayamaz; ortak havuzdan backfill eklemek artık saf F0 değildir. B=10 seçimi böyle bir müdahale ihtiyacını **geçmiş 5 tohumda** ortadan kaldırır. Yeni gelecek tohumda doğal arşiv B'den küçük çıkarsa otomatik backfill/clip yapılmaz: ilgili seed **BLOCKED_CAPACITY**, protokol sapmasıyla kaydedilir; başarılı tohumlara göre seçici eleme yasaktır.

Sıralama DISCOVERY skorlarından bütün 256 aday için dört hedefin min–max normalizasyonu; birincil artan L∞, ikincil L1, üçüncül lexical ID. Arşiv dışı adaylar sıralama minimum-maksimum sınırlarında bulunabilir fakat kısa listeye giremez. VAL, internal TEST ve OPSD sonuçları sıralamaya girmez.

## 6. Ölçüm/istatistik ön planı

Önerilen ve kaynak JSON'unda sabitlenen **30 yeni optimizer tohumu (2001–2030)** (saha/site bağımsızlığı değil). Tohum manifesti kod tarafından 2001–2030 olarak doğrulanır; veri split kilidi, RNG bağımsızlığı, problem parametreleri, çalışma commit'i ve veri SHA değerleri deney başlamadan sabitlenmeli. Bugünkü tarihsel beş tohum yeni prospektif örnekleme dahil edilmez. 30 tohumu kullanmak için güç analizi / kaynak izinleri ayrıca yapılmalıdır; 30'un %80 güç veya belirli etki büyüklüğü sağlayacağı **iddia edilmiyor**.

- **Birincil istatistik:** 30 seed'in tekil `D_s` değerlerinin ortalaması.
- **Önerilen birincil test:** İki taraflı eşli sign-flip randomization (küçük n tam, n>16 için sabit RNG ile 99.999 Monte Carlo permütasyonu), α=0,05. İşaret simetrisi varsayımı açıkça raporlanır; normal/karma model ve seed-cluster bootstrap sonuçları duyarlılık olarak ayrıca incelenebilir.
- **Güven aralığı:** Seed düzeyinde çift koruyan %95 bootstrap (12.000 deterministik bootstrap replikasyonu); küçük/bağımlı örneklemde nominal kapsama garantisi değildir.
- **İlgili F lehine kriter:** n=30, `D_bar ≤ -0.05`, p<0,05, bootstrap CI üst sınırı <0. Bunlar sadece kendi TRAIN-AUDIT referansı için keşifsel destek demektir. Saha üstünlüğü veya yeni kör TEST başarısı DEĞİL.
- **Hata türü:** Bir tek birincil hipotez. Çoklu ikincil analiz için teyit edici p-değeri üretilmez; soru değiştirmek veya B seçimini TEST'e göre yapmak yasaktır.

**İkincil ve karar koruma göstergeleri:**
1. `F0/F1_false_retained_fraction = |S_F \ P*| / B`; `1-precision` yorumunda.
2. Referans Pareto sayısı ve Pareto etiketlerinin yeniden örneklem duyarlılığı.
3. Native F0/F1 arşiv üyeliği, B=10 çıkışları ve `same_selected_k` oranı.
4. CPU, wall-clock, bootstrap çağrıları, maksimum bellek, p95 latency; native arşiv inşası ayrı.
5. Bağımlılık/eksik gözlem/fiziksel sınır kalite kapıları.

**Önemli karar sınırı:** Arşiv sadakatinde üstünlük bulunsa bile, toplam bellek ve CPU sınırı doğrulanmadan 'edge-ready' veya 'safety-certified' sonucu çıkarılamaz. Geçmiş 20/20 tarihsel K20 aynı olduğundan yeni B=10 testinde de aynı listeler çıkabilir. Böyle bir sıfır fark, F1 lehine iddiayı desteklemez; hipotez yanlışlanabilir olmalıdır.

### 6.1. Yeni güç duyarlılığı: 30 tohumun yeterli olduğu henüz gösterilmedi

Protokol taslak olarak 30 yeni tohum ayırıyor. Ancak paired seed-level delta farklarının gerçek standart sapması bilinmiyor. **İki taraflı α=0,05, varsayımsal mutlak 0,05 etki ve %80 güç için normal yaklaşım hesabı:** eşli farkların SD'si 0,05 ise 8; 0,075 ise 18; **0,10 ise 32**; 0,15 ise 71; 0,20 ise 126; 0,25 ise 197 tohum önerir. Bunlar sign-flip testinin tam gücü değildir; planlama duyarlılığıdır. `results/R19_APPROXIMATE_POWER_SENSITIVITY.csv` ve `tools/power_sensitivity.py` hesapları yeniden üretir.

Bu nedenle **30 seed yeterlilik onayı değildir** ve üçüncü kapıda önceden sonuçlar açılmadan ayrı güç analizini temel alan araştırmacı tasarımı gerekir. Yeni örneklem büyüklüğü seçilecekse JSON ve kod birlikte **yeni protokol sürümüne** geçirilmelidir; başlanan deneyden sonuç gördükçe tohum sayısını değiştirmek yasaktır.

## 7. Hesaplama maliyeti ve fizibilite

İki arşiv için ortak 12.600 farklı DISCOVERY controller×block olayının **tek kez** simüle edilip F0/F1 tarafından aynı kaynak üzerinde yeniden kullanılması mümkündür. Bu, bir seed'de **12.600 benzersiz simülatör değerlendirmesi**, iki kolda 12.600'er metrik kaydı demektir. 30 seed: **378.000** benzersiz DISCOVERY simülasyon çağrısı. Örnek AUDIT büyüklüğü 64 blok olursa 30×256×64=**491.520** ek simülatör değerlendirmesi, toplam **869.520** benzersiz değerlendirme. GERÇEK blok sayısı/seed sayısı nihai kilitte ölçülmelidir. Native F1 bootstrap CPU bunun dışındadır. Hiçbir AUDIT burada çalıştırılmadı.

## 8. Bilimsel GATE kriterleri

| GATE | Kapı | Şimdiki durum |
|---|---|---|
| R19-G1 | Tek birincil soru, hipotez, formül, sabit C/A, B/K, ranking, stats | **TASARIM TANIMLANDI** |
| R19-G2 | Kod, ham amaçtan skor, ledger eşitliği, anti-leakage, otomatik test | **PROTOTİP TAMAMLANDI** |
| R19-G3 | Gerçek TRAIN grup manifesti, temporal embargo, kaynak ve kod kilidi, dış zaman damgalı ön kayıt | **BLOCKED / gereken yeni kanıt** |
| R19-G4 | 30 yeni seed gerçek yeniden optimizasyonu + 256×AUDIT tam rescore + power | **YAPILMADI** |
| R19-G5 | Bağımsız, unexposed gerçek yeni TEST + fiziksel güvenlik | **BLOCKED / henüz yok** |

R19-G1 tasarım kararı insan araştırmacı tarafından ayrıca onaylanırsa daha sonra **ayrı imzalı sürümle** resmileştirilir. Bu dosyanın GitHub'a konması veya `locked=false` içeren JSON hazırlanması kayıtlı ön-kayıt anlamına gelmez. Tarihsel `seed1001/C1_F1_A1` için `UNRECORDED_LOCAL_SHA` source provenance engeli de kapanmış sayılmaz.

## 9. Kullanım / reprodüksiyon

Paket içinde `config/R19_PRIMARY_PROTOCOL_DRAFT.json`, `tools/primary_hypothesis.py`, `tests/test_primary_hypothesis.py` ve gerçek tarihsel arşivden türetilen `results/R19_HISTORICAL_FEASIBILITY.json` bulunur.

```bash
python -m pip install numpy pytest
python -m pytest -q tests
python tools/primary_hypothesis.py select --config config/R19_PRIMARY_PROTOCOL_DRAFT.json --input NEW_SEED_DISCOVERY_ONLY.json --output locked_seed_selection.json
# Kilit SHA'sı ve dosya hash'i AUDIT açılmadan dış, immutable Git commit'ine alınmalı.
python tools/primary_hypothesis.py audit --config config/R19_PRIMARY_PROTOCOL_DRAFT.json --lock locked_seed_selection.json --input NEW_SEED_AUDIT.json --output seed_audit_result.json
python tools/primary_hypothesis.py summary --config config/R19_PRIMARY_PROTOCOL_DRAFT.json --input thirty_seed_results.json --output summary.json
```

`select` girdisi: tek seed, 40-karakter gerçek çalıştırma Git SHA, 64-karakter kaynak manifest SHA, 256 benzersiz aday, her blok için `{block_id,group_id,split}`, F0/F1 doğal arşiv listeleri, tamamı DISCOVERY içinde 12.600 eşsiz aday-blok çifti olarak **her iki eşit evaluation_pairs ledger'ı**, ve her adayın kendi gerçekleşen bloklarındaki dört ham ölçümü `discovery_objectives[cid][block_id]=[4 hedef]`.

`audit` girdisi: aynı seed ve tamamı AUDIT'te **her bir** 256 aday × AUDIT bloğu için dört ham amaç + `independent_lock_receipt`. Bu receipt'in JSON içinde beyan edilmesi **gerçek zamansal bağımsızlık ispatı değildir**. Dış commit URL, commit zaman damgası ve kaynak nesne referansı insan/bağımsız denetçi tarafından gerçekten kontrol edilmelidir. Bu yüzden otomatik `score_audit` geçse bile EAAI-GATE otomatik açılamaz.

`summary` girdisi: 30 adet `audit` çıktısı. Kod beklenen deney sayısı eksikse 'desteklendi' ifadesi vermez. Tüm sonuçları `open(x)` ile yazar, önceki çıktı dosyasını yeniden yazmaz; tarihsel kaynakları değiştirmez.

## 10. Bilinen sınırlılıklar

- Gözlem blokları için `group_id` dizgesi yanlış hazırlanırsa zaman bağımlılığı sistem tarafından güvenilir biçimde algılanmayabilir; manuel zaman penceresi ve halo/embargo gereklidir.
- Dış kilit makbuzu doğrulaması otomatik üçüncü-taraf imza kontrolü değildir; kayıt zinciri harici kanıt gerektirir.
- Paylaşılan 210 tarihsel TRAIN bloğu daha önce çeşitli analizlerde kullanıldı; yeni TRAIN-AUDIT yerel deney, genel dağılım dışına bağımsız kör TEST değildir.
- Ampirik Pareto referansı 256 kontrolcü ve sonlu AUDIT verisine göre tanımlıdır; gerçek sonsuz dağılım ve fiziksel güvenlik için altın standart değildir.
- Program belirli bir CPU zamanını / wall-clock / peak RSS bütçesini enforce etmez. Bunlar ayrı ölçülecek guardrail'lerdir.
- Yeni seed sayısı 30 ve en az 5 yüzde puanı etki önemi öneridir; **gerçek güç analizi olmadan kesinleşmiş yeterlilik** anlamına gelmez.
- F0/F1 farklı tahsis ledger'ları, kaynak SHA bilinmeyen, NaN / AUDIT sızıntılı örnekler otomatik reddedilir.
- Orijinal GitHub `src/` algoritması, veri ve R6–R18 tarihsel çıktıları R19 ile değiştirilmemiştir.
