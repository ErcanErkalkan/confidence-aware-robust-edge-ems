# CRMT R24: R23 Koşullu Sertifikasından R19 B=10 Gerçek TRAIN Fizibilitesine

**Tarih:** 25 Ekim 2026  
**Araştırma sınıfı:** Doğrulanmış, geçmişte incelenmiş TRAIN kaynaklarının yeniden hesaplanması. **Yeni TEST, ön-kayıt, saha güvenliği veya yeni optimizer deneyi değildir.**

## 1. Tek bir bilimsel soru

R19 taslağında sabitlenen araştırma sorusu değişmiyor:

> C1/A1, aynı 12.600 DISCOVERY controller–block değerlendirme olayları ve B=K=10 doğal arşivden seçim altında, F1'in ayrı AUDIT-TRAIN sonlu referans Pareto kümesindeki kaçırma oranı F0'dan daha mı düşüktür?

Amaçlar (min): `cap_violation_pct_total`, `lfp_cycle_loss_pct`, `ramp95_kw_per_min`, `flip_per_day`. Risk `mean + 0.5 * empirical-top10%-tail-mean`. R23 risk ve kaynak dosyalarıyla aynı hesap yapılır. `R19_PRIMARY_PROTOCOL_UNCHANGED.json` orijinal **taslaktır**, zaman damgalı dış ön-kayıt değildir.

## 2. Orijinal R16 verilerinde üç gerçek TRAIN kaynak kontrolü

Dosyalar R16 paketinden çıkarılır. F0 ve F1 için ayrı özgün `run_summary.json` içindeki her `files_sha256` karşısında `candidate_metrics.csv`, `ledger.csv` ve `optimizer_front.csv` ham baytları doğrulanır. Her kol 256 kontrolcü, 12.600 benzersiz kontrolcü–blok çifti, dört amaç değeri içerir; F0 ve F1 aynı gözlem defterini ve kayıpları paylaşır. Kaynak kod `risk.py`, `dominance.py`, `archive.py` için Git blob SHA-1 değerleri doğrulanır; tarihsel F1 `seed1001` yürütme commit'i eksik olarak korunur.

| seed | doğal F0 arşivi | doğal F1 arşivi | B10 ortak aday | B10 her kola özgü aday | 256 adayda ortak **tam iki inverter** günü | ortak blok |
|---|---:|---:|---:|---:|---:|---:|
| 1001 | 18 | 236 | **6/10** | 4 | 9 | 18 |
| 1004 | 22 | 240 | **9/10** | 1 | 5 | 10 |
| 1005 | 17 | 237 | **7/10** | 3 | 5 | 10 |

**Yeni bulgu:** Tarihsel K20 seçimlerinin 20/20 aynı olması, R19'un bütün-256 DISCOVERY risklerini min–max normalize eden `L_inf`, sonra `L1`, sonra aday kimliği kuralıyla oluşturduğu **B10** kısa listelerin aynı olmasını gerektirmez. Bu üç C1/A1 seed'de B10 farklıdır. **B10 farkı, üstünlük veya daha güvenli fiziksel kontrolcü sonucu değildir.** Yeni AUDIT puanı hesaplanmadı, yeni test için p-değeri üretilmedi.

## 3. Gün eksikliğinin mühendislik anlamı

Ham `block_id` yapısı `opencem:invN:YYYY-MM-DD`. 256 kontrolcünün aynı gün her iki inverterde **birden** ölçülmesi şartıyla tüm adaylarda eksiksiz ortak gün sayısı **9, 5, 5**. Her bir kontrolcünün bireysel gün sayısının 106'ya ulaşması, 256 adaylı ortak panelde 106 gün olduğu anlamına gelmez. 12.600 eşit *toplam* değerlendirme, gün dağılımının kontrolcüler arasında dengeli olduğunu göstermiyor.

R19 taslağı önerilen AUDIT kapsamı: her adayda **60 ortak blok** yani her iki inverter kaydı bulunan **30 gün**, her seed için **256 × 60 = 15.360 yeni AUDIT controller–block değerlendirmesi**; 30 seed için **460.800** AUDIT değerlendirmesi. Bu sayı DISCOVERY bütçesinden ayrıdır (12.600 × 30 = 378.000/kol). F0/F1 için aynı adaylar ve aynı AUDIT blokları kullanılırsa AUDIT değerlendirmeleri aynı seed'de paylaşılabilir. Gözlenen eski TRAIN'deki 5–9 gün bu taslak minimumunu karşılamaz. 30 günün bağımsız veya kalibrasyon için yeterli olduğu da kanıtlanmış değildir.

## 4. R23 neyi çözmüştü, burada neden kullanılamıyor?

R23'ün amacı, havuzlanmış inverter–blok `mean+0.5×CVaR0.9` skorunun belirsizliği için aynı anda aday ve dört amaç güven aralıkları kurmaktır. Ancak teorem şu **önceden belirlenmiş** koşullara ihtiyaç duyar: sabit kontrolcüler; gerçek geçerli amaç destekleri; bütün adaylarda ortak eksiksiz günler; katı durağan bütün-gün vektörleri; bilinen sonlu m-bağımlılık; tek önceden belirlenmiş karar zamanı ve seçimden bağımsız AUDIT verisi.

- Geçmişte gözlenen en küçük/büyük kayıp değerleri gerçek destek sınırı değildir. Örneğin `flip_per_day` maksimumu 146 görüldü diye ileride 146 üstünün imkânsız olduğu kanıtlanmış olmaz.
- Gözlem serisinden hesaplanan ACF'nin belli bir gecikmede sıfıra yaklaşması, tam sonlu m-bağımlılığı veya katı durağanlığı ispatlamaz. AR(1) böyle bir varsayıma zorla sokulamaz.
- `SyntheticDesign` benzeri bir kod nesnesinin `stationary=True` demesi dış güvence sayılmaz.
- Zorunlu B=10 bellek sınırı, zamanlama, CPU ve gerçek edge saha güvenliği henüz ispatlı değil.

**Karar:** R23'ten gelen bir gerçek OpenCEM güvenlik sertifikası yoktur. Ancak R23'ün sentetik koşullu yöntemi korunabilir, yeni veriler için dış araştırmacı değerlendirmesi sonrası çalıştırılabilir. Farklı bir dağılımsal varsayım gerekiyorsa önce yöntemin matematiksel geçerliliği yeniden kurulmalıdır.

## 5. Gelecek deneyin ön-kayıt ve kaynak kontrolü

Prospektif bir R19 testi başlamadan:

1. **Hipotez ve örneklem sayısı:** Tek birincil Δ=Miss(F1)−Miss(F0), B10 ve C1/A1 korunmalı; 30 seed'in %80 güç için yeterliliği pilotla belirlenip dış zaman damgasına bağlanmalı.
2. **Yeni kaynağın kökeni:** Gerçek zaman damgalı veri edinimi, lisans, versiyon SHA, aday kod SHA, cihaz/inverter eşlemesi ve orijinal fiziki amaç destekleri teknik dokümantasyondan gelmeli.
3. **Kaynak ayrıklığı:** DISCOVERY ve AUDIT gün/site kümeleri ayrık tutulmalı; uygulamaya uygun embargo ve veri maruziyet defteri önceden kilitlenmeli. R19'un yalnız `committed_before_audit=true` boole değeri veya HTTPS URL'si gerçek dış zaman kanıtı sağlamaz.
4. **Eşit metodoloji:** Her tohumda F0/F1 tam aynı 12.600 DISCOVERY olayı; 256 adaydan eşit B=10 çıktı seçimi ve gerekirse tüm AUDIT blokları üzerinde 256 adayın simülasyonu.
5. **Maliyet:** Yalnız simulator çağrısı değil R20 profilindeki native arşiv CPU, bellek, seçim süresi raporlanmalı. B10 sonradan kırpma, sert arşiv belleği B10 sınırı demek değildir.
6. **İstatistik:** Önceden belirlenmiş iki taraflı test, güven aralığı, 5 yüzde puan pratik fark ve güvenilir bağımsız örneklem birimi doğrulanmalı.
7. **Kapılar:** Bağımsız yeni kör TEST ayrıca edinilmeden yeni dış genelleme iddiası yapılmamalı. SOC, batarya ve şebeke emniyeti için HIL/saha doğrulaması ayrı gerektirir.

`tools/r24_preflight.py` yalnız gelecekteki **hipotetik** 256×60 AUDIT tablosunun satır, zaman ve eksik kayıt yapısını doğrular. Kolayca uydurulabilecek bir tabloyu gerçek ölçüm, dış ön-kayıt veya güvenlik sertifikası saymayı reddeder.

## 6. Gerçekten kapanan ve kapanmayan işler

| İş | Bilimsel durum |
|---|---|
| Üç geçmiş C1/A1 çifti için ham SHA + 4 amaç eşitliği | Tamamlandı |
| R19'un doğal arşiv B10 seçiminin yeniden hesaplanması | Tamamlandı, 3/3 farklı |
| 256 adaylı gerçek ortak gün paneli teşhisi | Tamamlandı, 9/5/5 gün |
| R19 AUDIT değerlendirme yükünün hesaplanması | Tamamlandı, 15.360/seed |
| R23 gerçek dünya m-bağımlılık/durağanlık ispatı | **Eksik** |
| Mühendislik destek sınırlarının ön kaydı | **Eksik** |
| Yeni 30-seed deney ve gerçek ayrı AUDIT | **NOT RUN** |
| Seed1001 F1 özgün Git SHA | **UNRECORDED_LOCAL_SHA** |
| Yeni bağımsız kör TEST | **NO-GO** |
| Fiziksel BESS/inverter güvenliği | **NO-GO** |

**Sonuç:** Bu aşama yeni sentetik yöntem eklemek yerine, R19'un hangi gerçek yeni ölçüm ve dış kanıtlarla sınanabileceğini ölçülebilir hâle getiriyor. Yanlış şekilde geriye dönük ön-kayıt ya da fiziksel güvence ilan etmiyor.
