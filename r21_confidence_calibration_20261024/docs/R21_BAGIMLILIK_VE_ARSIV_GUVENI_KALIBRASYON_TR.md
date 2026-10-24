# CRMT R21 — Üçüncü Adım: Confidence Arşivinin İstatistiksel Kalibrasyonu

**Tarih:** 24 Ekim 2026  
**İnceleme türü:** Keşifsel/sentetik yöntem stres testi + özgün, daha önce görülmüş OpenCEM TRAIN kaynak tanısı.  
**Makale için teyit edici bağımsız TEST:** **NO-GO.**

## 1. Sorun ve bilimsel hedef

R19 birincil karşılaştırmayı belirledi: C1/A1, F1−F0, gerçek gelecekteki 10 adaylık çıktı listesinde ayrı TRAIN-AUDIT Pareto adaylarını kaçırma oranı. R20 yalnızca controller–block değerlendirme izinin eşit olmasının **toplam CPU ve doğal arşiv belleği eşitliği olmadığını** gösterdi. R21'in amacı yeni bir saha üstünlük iddiası değil, F1'in kullandığı bootstrap baskınlık kararının istatistiksel hata davranışını *kalibre etmeye çalışmak* ve kalibrasyonun başarısız olduğu koşulları belirlemektir.

**Birinci tanısal olay:** en az bir gerçekte Pareto-optimal kontrolcünün arşiv dışına atılması (`false_removal`). **İkinci:** gerçekte doğru olmayan en az bir sıralı baskınlık iddiası (`false_pair_declaration`). **Üçüncü:** herhangi bir sıralı çift/amaç için tek taraflı güven üst sınırının popülasyon risk farkının altında kalması (`family_undercoverage`). **Dördüncü:** üç adaylık deneysel arşiv kapasitesinin aşılması (`overflow`). Bu dört sonuç birbirinin yerine geçemez. Güven sınırı ihlali belirlenen baskınlık kararından daha sık olabilir; yanlış eleme görülmemesi güven kapsamının doğru olduğunu göstermez.

## 2. Referans algoritma ve matematiksel hedef

Özgün CRMT GitHub `risk.py`, `dominance.py` ve `archive.py` modülleri byte düzeyinde ve Git blob SHA ile doğrulanmış, **değiştirilmeden** yüklenmiştir. F1 `ConfidenceArchive.confidently_nondominated_ids()` davranışı, yönlü çiftlerin tamamında aynı kaynak fonksiyon `confidence_risk_dominance()` ve orijinal `_pair_seed` ile hesaplanmıştır. Bir regresyon testi arşivin kendi son üyeleriyle bire bir eşitlik kontrolü yapar.

Dört kayıp için kullanılan risk fonksiyonu:

\[
 R_j=\overline L_j+0.5\,\operatorname{TopTailMean}_{0.9}(L_j).
\]

Sentetik oracle, sabit ortalama ve varyanslı *marjinal Gauss popülasyonu* içindir:

\[
 L_{c,t,j}=\mu_{c,j}+0.36H_{t,j}+0.28E_{c,t,j},\quad
 R^{\rm pop}_{c,j}=1.5\mu_{c,j}+0.5\sqrt{0.36^2+0.28^2}\,\frac{\varphi(\Phi^{-1}(0.9))}{0.1}.
\]

**Önemli:** Riskin kuyruk teriminde ortalama `μ` yine bulunduğundan popülasyon referansı `μ+...` değil **`1.5μ+...`** olarak hesaplanır. Sentetik risk referansı gerçek OpenCEM performansı veya fiziksel güvenlik gerçeği değildir. H ve E serileri durağan AR(1), \(\rho=0\) veya \(0.87\) olacak şekilde türetilir. Eksik gözlem senaryosunda her kontrolcü/gün için %28 bağımsız kayıp oluşturulur; değerler tamamlanmaz.

## 3. Tasarım ve yöntemler

- **Beş kontrolcü, dört amaç, 48 zaman bloğu, 80 tekrar/senaryo.** 5 senaryo × 4 yöntem × 80 = **1.600 yöntem-tekrar kaydı**. Veriler aynı tekrar içinde bütün yöntemler tarafından paylaşılır. Sonuçlar yeniden üretilebilir tohumlarla kilitlenmiştir; bunlar deney ön kaydı veya yeni optimizer tohumu değildir.
- **F0:** gerçek minimizasyon Pareto karşılaştırması, her kontrolcünün gözlenen risk vektöründen.
- **F1 — legacy:** bire bir özgün CRMT eşli iid bootstrap kodu, her sıralı çiftte bağımsız iki yönlü RNG, `alpha=.05`, `n_boot=350`, dört amaç içinde Bonferroni, arşiv çapında düzeltme yok.
- **Shared max-T iid:** bütün adaylar, tüm zaman blokları ve bütün sıralı aday/amaç risk farkları için eşzamanlı ortak bootstrap ve `max` studentize istatistikten yaklaşık %95 üst sınır. Bu, önerilen bir alternatif tanılamadır; kanıtlanmış FWER garantisi **değildir**.
- **Shared max-T circular moving block:** aynı yöntemin sürekliliği koruyan L=6 blokluk halkasal bootstrap versiyonu. Zaman sıralaması veya yeterli ortak blok yoksa **BLOCKED**; eksikleri doldurarak sahte yeterlilik sağlamaz.
- **Arşiv kapasitesi B=3 yalnızca stres testi parametresidir.** R19'un B=10 hipotezi değiştirilmemiştir. Flat-null senaryosunda **beş kontrolcünün tamamı gerçekte Pareto-optimal** olduğu için yanlış eleme yapmadan B=3 sağlamak matematiksel olarak imkânsızdır.

## 4. Ana sonuçlar (her senaryoda n=80 tekrar)

| Senaryo | Yöntem | En az bir yanlış eleme | En az bir sınır ihlali | B=3 taşması |
|---|---|---:|---:|---:|
| Clear / iid | F0 point | 0/80 | ölçülmez | 0/80 |
| Clear / iid | F1 legacy | 0/80 | **54/80 (%67,5)** | 0/80 |
| Clear / iid | max-T iid | 0/80 | 8/80 (%10) | 0/80 |
| Clear / iid | max-T block L6 | 0/80 | 30/80 (%37,5) | 0/80 |
| Near / iid | F0 point | 0/80 | ölçülmez | 38/80 |
| Near / iid | F1 legacy | 0/80 | **62/80 (%77,5)** | 80/80 |
| Near / iid | max-T iid | 0/80 | **9/80 (%11,25)** | 80/80 |
| Near / iid | max-T block L6 | 0/80 | 29/80 (%36,25) | 80/80 |
| Near / temporal AR .87 | F0 point | 4/80 | ölçülmez | 80/80 |
| Near / temporal AR .87 | F1 legacy | 0/80 | **80/80** | 80/80 |
| Near / temporal AR .87 | max-T iid | 0/80 | **80/80** | 80/80 |
| Near / temporal AR .87 | max-T block L6 | 0/80 | **80/80** | 80/80 |
| Flat-null / temporal AR .87 | F0 point | **44/80** | ölçülmez | 63/80 |
| Flat-null / temporal AR .87 | F1 legacy | **4/80** | 80/80 | 80/80 |
| Flat-null / temporal AR .87 | max-T iid | **2/80** | 80/80 | 80/80 |
| Flat-null / temporal AR .87 | max-T block L6 | 0/80 | 79/80 | 80/80 |
| Near / serial / partial | F0 point | 8/80 | ölçülmez | 72/80 |
| Near / serial / partial | F1 legacy | 0/80 | 80/80 | 79/80 |
| Near / serial / partial | max-T iid | **80/80 BLOCKED** | değerlendirilmez | değerlendirilmez |
| Near / serial / partial | max-T block | **80/80 BLOCKED** | değerlendirilmez | değerlendirilmez |

**Yazım notu:** Tablo biçimindeki `8/80 (%10)` ifadesi keşifsel bir güven sınırı sıklığıdır, gerçek sistem garantisi değildir.

### Yorumu

1. **F1 legacy aynı aday çifti içindeki dört amacı düzeltir; tüm arşivin yaklaşık 20 sıralı çift × dört amaçlı güven sınırlarını simultane kapsamaz.** İid durumunda bile ölçülen arşiv çapı sınır ihlali %67,5–77,5'tir. Burada ihlal, yanlış kontrolcü elemesi ile **aynı olay değildir**.
2. **Eşzamanlı max-T iid deneysel olarak iyileşse de `%10–11,25` güven ihlali, hedeflenen %5'in üstündedir.** Bu yüzden yeni yöntemi kalibre edilmiş/güvenli ilan etmek mümkün değildir.
3. **Güçlü zaman bağımlılığında L3, L6 veya L12 circular moving-block bootstrap tanılaması da hiçbir koşulda hedeflenen simultane kapsamaya erişmedi.** Tek bir blok uzunluğu seçip sahte kesinlik üretmemek gerekir.
4. **Flat-null örneğinde beş doğru Pareto adayının tamamının korunması B=3 kapasiteyi zorunlu olarak aşar.** İstatistiksel koruma ile sabit bellek çatışabilir. F1 legacy 4/80 yanlış eleme üretmiştir. Moving-block 0/80 olsa dahi Wilson yaklaşık %95 üst sınır **%4,58**; sıfır hata garantisi yoktur.
5. **Eksik kronoloji koşulunda max-T yöntemleri veri uygunluk kapısından geçmez.** Engellenme yeni bir başarı veya güvenlik sertifikası sayılamaz.

## 5. Blok uzunluğu duyarlılığı

İki güçlü zaman-bağımlı senaryoda L=3,6,12 ile 80 eşleştirilmiş tekrar yeniden ölçüldü. Near-serial tümünde 80/80 sınır ihlali; flat-serial her uzunlukta 79/80 sınır ihlali görüldü. `R21_BLOCKLEN_SENSITIVITY.csv` denetlenebilir kanıttır. Bu üç uzunluk, zaman bağımlılığını bu sonlu örneklemde çözmedi; sistematik optimal uzunluk arama prosedürü veya genellenebilir hata kontrolü değildir.

## 6. Gerçek OpenCEM TRAIN kaynak tanısı (SEEN DATA)

R16 özgün paketinden `seed1001`, `seed1004`, `seed1005` C1/A1 F0/F1 **candidate_metrics.csv** SHA'ları orijinal `run_summary.json` ile kontrol edilmiştir. Her kolda 12.600 olay, 256 kontrolcü ve F0/F1 bilimsel verilerinin eşitliği doğrulanır.

| Tohum | Kontrolcü başına blok min–medyan–maks | Takvim günü min–maks | İlk 10 kontrolcü çiftinin ortak blok min–medyan–maks |
|---|---|---|---|
| 1001 | 18–40–210 | 9–106 | 20–20–40 |
| 1004 | 10–40–210 | 5–106 | 40–40–40 |
| 1005 | 10–40–210 | 5–106 | 18–40–40 |

Özgün blok kimlikleri `opencem:invN:YYYY-MM-DD` biçimindedir: bir takvim gününde iki inverterin ölçümleri bağımsız eşit-kayıp bloklar sayılamaz. Ortak blok sayısı ve kronoloji kontrolcü çiftine göre değişir. Gerçek seri için aynı takvim günü kümeleri, olası ardışık gün bağımlılığı, eksik bloklar ve *saha/gün bağımlı ortak şoklar* araştırılmadan iid bootstrap'ın teorik kalibrasyonu savunulamaz.

## 7. Bilimsel sınırlar ve kapanış kararı

**R21 tanısal kod ve ölçüm tamamlandı, confidence kalibrasyonunun başarısı kanıtlanmadı.** Dondurulmuş asıl CRMT kaynak koduna dokunulmadı; bu ZIP, özgün `risk/dominance/archive` Git blob dosyalarını ve gerçek TRAIN R16 kaynaklarını içerir. 80 tekrar/senaryo, model varsayımları altında Monte Carlo örneklemidir. Wilson aralıkları bu model-tekrar oranını belirsizlikle ifade eder; genel matematiksel FWER garantisi sağlamaz. Seri bağımlılığı veya müşteri/tesis çeşitliliği gerçekte farklı olabilir. Bootstrap sayısı 350, orijinal kodun bazı çalışma ayarlarından daha küçüktür; sonuçlar tarihi sonuçların yeniden üretimi değildir. Gerçek R19 prospektif 30 tohum, yeni AUDIT-TRAIN ve bağımsız yeni TEST **yapılmadı**.

### Kesin bilimsel karar

- R21 istatistiksel risk tanısı: **GELİŞTİRME VE STRES TESTİ KAPANDI**.
- F1 archive-wide %5 yanlış karar/kapsama garantisi: **BAŞARISIZ/DOĞRULANMADI**.
- Sert B=3 ve gerçek Pareto adaylarını kayıpsız koruma: null senaryoda **MATEMATİKSEL OLARAK BİRLİKTE SAĞLANAMAZ**.
- Eşit toplam CPU ve gerçek edge güvenliği: R20'den beri **AÇIK**.
- Gerçek R19 birincil sonuç ve yeni bağımsız TEST: **NO-GO**.

### Sıradaki teknik çözümün gerektirdiği koşullar

(1) gerçek TRAIN için takvim-günü/site temelli ve olası gap içeren resampling birimi; (2) bootstrap %5 simultane kapsama için etkili blok sayısı ve parametre kalibrasyonu; (3) *güven aralığı* ile *yanlış Pareto eleme olayı* için ayrı kabul kriterleri; (4) önceden kararlaştırılmış kapasite aşımı/abstention kararı; (5) R19 prospektif C1/A1 B10 birincil hipotezinin deneysel protokolünün ayrıca kilitlenmesi.

## 8. Çalıştırma

```bash
pip install numpy pytest
python tools/calibrate.py --repetitions 80 --n-boot 350 --block-len 6 --output-dir results
python tools/sensitivity.py
python tools/real_train_diagnostic.py
PYTHONPATH=reference_snapshot pytest -q tests
```

**Dış makalede yer verilebilecek güvenilir sonuç türü:** özgün kaynak kontrolü, senaryoya özgü açık Monte Carlo oranları, veri bağımlılığı açığı ve fail-closed prototip kararları. **Verilemeyecek sonuç:** yeni kör TEST üstünlüğü, kalibre edilmiş %5 arşiv-geneli güvenlik garantisi veya otomatik saha dağıtım onayı.
