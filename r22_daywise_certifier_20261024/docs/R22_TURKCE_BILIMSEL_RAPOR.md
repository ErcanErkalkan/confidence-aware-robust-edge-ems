# CRMT R22 — Gün düzeyinde koşullu eşzamanlı güven bandı ve Pareto seçim kapısı

**Tarih:** 24 Ekim 2026  
**Kanıt sınıfı:** Sentetik metodolojik stres testi + daha önce incelenmiş OpenCEM TRAIN kaynak denetimi. **Yeni bağımsız TEST değildir.**  
**Proje:** `ErcanErkalkan/confidence-aware-robust-edge-ems`  
**Frozen kod:** `risk.py`, `dominance.py`, `archive.py` orijinal Git blob SHA ile doğrulanmıştır; değişiklik yapılmamıştır.

## 1. Çözülmeye çalışılan açık problem

R21, per-objective Bonferroni-düzeltilmiş iid bootstrap'ın arşiv kapsamındaki yanlış güven bandı kararlarını kontrol etmediğini; güçlü zamansal bağımlılıkta shared max-T ve kısa moving-block yaklaşımlarının da çalışmadığını göstermişti. R22 yeni bir **koşullu matematiksel hata sınırı** oluşturur, ancak bunu fiziksel sisteme ya da zamansal bağımlılığı doğrulanmamış verilere atfetmez.

Hedef: Beş önceden belirlenmiş kontrolcü × dört amaç için, **bütün aday-amaç popülasyon risklerinin eşzamanlı güven aralıklarında bulunmasını** olasılık en az 1−δ olacak biçimde sınırlandırmak. Bütün adaylar için aralıkların ayrılması dışında **hiçbir Pareto eleme ilan edilmez**. Arşiv büyüklüğü B'yi geçerse durum `ABSTAIN_CAPACITY_UNCERTAINTY` olur.

## 2. İspatlanabilir sınırın varsayımları

1. Gün kümeleri aralarında *bağımsız ve özdeş dağılımlı* (IID) olmalı. Gün içindeki iki inverter ve farklı aday/amaç gözlemleri keyfi bağımlı olabilir.
2. Her aday ve her amaç için **önceden sabitlenmiş ve gerçek dağılımı kapsayan sonlu** `[a_j,b_j]` sınırları bulunmalı. Bu deneyin `[0,4]` sınırı yalnızca sentetik simülatör içindir; OpenCEM için kullanılmaz.
3. Aday kimlikleri, amaçlar, α ve destek sınırları verileri görmeden tanımlanmış olmalı. Bu araştırma prototipi gerçek veriye bağımsızlık garantisi *üretemez*.
4. İki inverterin **her gün her aday için ikisi birden** gözlenmeli. Eksik günler veya ölçümler doldurulmaz ve sessizce çıkarılmaz.
5. Gün sayısı 10'un katı olmalı (en az 20): böylece CRMT'nin `top-k` ampirik %90 kuyruğu, ampirik CVaR hesaplamasıyla **tam eşleşir**.

ÖNEMLİ: İki inverterin gün ortalamasından oluşan günlük kayıp yeni bir **gün-toplulaştırılmış estimand** oluşturur. Dondurulmuş makaledeki ayrı controller–block kayıplarının havuzlandığı dağılımın riskinden farklıdır. Dolayısıyla R22 mevcut F1'in geriye dönük performans kanıtı değildir.

## 3. Matematiksel yapı ve kısa ispat

Her kontrolcü `c`, amaç `j`, gün `t` için aynı günün iki inverter ölçümünün ortalaması `Y_cjt` olsun; `a_j ≤ Y_cjt ≤ b_j`. Sabit `q=0.9` ve `λ=0.5` ile

\[
 R_{cj}=\mathbb{E}[Y_{cj}]+\lambda\,\mathrm{CVaR}_{q}(Y_{cj}).
\]

Gün-toplulaştırılmış ampirik karşılık (n, 10'un katıdır):

\[
 \widehat R_{cj}=\overline Y_{cj}+\lambda\,\mathrm{mean}\left(\mathrm{top}\ (0.1n)\ \mathrm{daily\ losses}\right).
\]

DKW eşitsizliği her **IID** aday–amaç marjinali için `P(sup_x |F̂−F|>ε) ≤ 2e^(−2nε²)` verir. Toplam `M=4C` marjinal için union bound:

\[
 \varepsilon=\sqrt{\frac{\log(2M/\delta)}{2n}}, \qquad
 \Pr\left(\text{bütün marjinal CDF hataları }\leq\varepsilon\right)\geq 1-\delta.
\]

Bant kayması en fazla `range×ε` (ortalama), üst-kuyruk CVaR için en fazla `range×ε/(1−q)` olur: sonuncusu kuantil fonksiyonlarının üst kuyruk integrali üzerinden, bounded-support Wasserstein-1/CDF alanı sınırıyla gelir. Böylece

\[
 \boxed{ |R_{cj}-\widehat R_{cj}|\leq (b_j-a_j)\left(1+\frac{\lambda}{1-q}\right)\sqrt{\frac{\log(2M/\delta)}{2n}}. }
\]

Burada `λ=.5,q=.9` ile çarpan **6**'dır. Aralıklar ayrıca bilinen `[(1+λ)a_j,(1+λ)b_j]` ile kesiştirilir (kapsama kaybı yaratmaz). **i'nin j'ye baskınlığı**, ancak tüm dört amaçta `U_ik < L_jk` olduğunda sertifikalanır. Böylece aynı anda bütün marjinler kapsanırsa yanlış sertifikalı baskınlık veya yanlış Pareto eleme mümkün değildir:

\[
 \Pr(\text{en az bir yanlış sertifikalı Pareto eleme})\leq\delta,
\]

**Sadece bu varsayımlar altında.** Bunlar veriyle bağımsız olarak doğrulanmadığı sürece bir saha güvenlik sertifikası değildir; zamansal bağımlı günlerde iddia geçerli değildir.

## 4. 60 tekrarlı deney bulguları

5 aday, 4 amaç, iki inverter/gün; nominal α=0.05; 7 senaryo × 60 tekrar = **420 sentetik panel**. Güçlü seri bağımlılık ve eksik veri senaryoları sertifika kapsamına sokulmaz. B=3 kapasitesi yalnız sentetik stres testidir, **R19 B=10 değişmedi**.

| Sentetik senaryo | Gün | Koşullu sertifikalı karar | Yanlış eleme | Ortalama tutulan aday |
|---|---:|---:|---:|---:|
| Kolay IID | 200 | 0/60 | 0/60 | 5 |
| Kolay IID | 4000 | **60/60** | 0/60 | **3** |
| Yakın-performans IID | 200 | 0/60 | 0/60 | 5 |
| Yakın-performans IID | 4000 | 0/60 | 0/60 | 5 |
| Güçlü AR(1) gün bağımlılığı | 200 | 0/60, **engellendi** | **ölçülmedi** | — |
| Güçlü AR(1) gün bağımlılığı | 4000 | 0/60, **engellendi** | **ölçülmedi** | — |
| Eksik inverter ölçümü | 200 | 0/60, **engellendi** | **ölçülmedi** | — |

Koşullu-güvenilir IID senaryolarda kapsam ihlali/yanlış eleme gözlenmemesi, ampirik `%0` gerçek hata garantisi değildir. 60'da 0 yanlışlık için Wilson %95 üst sınırı **%6,02**. İspatlanan α=%5 üst sınırı ise yalnız doğru IID/destek varsayımlarından kaynaklanır, bu 60 gözlemden değil.

## 5. Güç/maliyet uygunluğu: olumsuz ama kritik bulgu

Destek aralığı genişliği 4, C=256 kontrolcü, dört amaç ve δ=0.05 için, iki adayın gerçek risk değerleri arasındaki en dar dört-amaç marjının `γ` olması halinde `2×risk_halfwidth < γ` için yeterli günlük örnek sayısı:

\[
 n>\frac{[2(b-a)(1+\lambda/(1-q))]^2\log(2\times4C/\delta)}{2\gamma^2}.
\]

| Varsayımsal en küçük risk baskınlık marjı γ | C=256 için yeterli IID gün sayısı |
|---|---:|
| 1.95 (büyük fark) | **3.220** |
| 0.18 (yakın fark) | **377.620** |

Bu üstten garanti türetilen **yeterlilik sınırlarıdır**; herhangi bir algoritmanın gerekli örnek sayısının alt sınırı değildir. Ancak CRMT'nin hedeflediği günlük mikroşebeke zaman ölçeğinde uygulanabilir olmama sorununu güçlü biçimde gösterir. C=5 kolay senaryonun 4.000 günde çalışması, C=256 / daha büyük fiziksel destek aralığı için saha uygulanabilirliğini kanıtlamaz.

## 6. Gerçek OpenCEM TRAIN denetimi

SHA-256 ile doğrulanmış R16 orijinal TRAIN `candidate_metrics.csv` dosyaları kullanıldı; F0/F1 ham amaçları ve çift kimlikleri eşleşiyor. Üç seed: 1001, 1004, 1005. Her biri 256 aday ve 12.600 controller-block kaydı. Aday başına gün sayısı sırasıyla **9–106, 5–106, 5–106**; aynı aday için iki inverterin tam günü de en az 9, 5, 5 güne kadar iniyor.

Gerçek TRAIN için yöntem **`BLOCKED_REAL_TRAIN_IID_AND_SUPPORT_UNVERIFIED_NOT_NEW_TEST`** üretir çünkü: IID günlerin dış kanıtı yoktur, dört amaç için önceden kilitli ve bütün olası değerleri kapsayan destek kataloğu yoktur, her adayın tüm ortak günlerinde gözlem bulunmaz ve veri tarihsel olarak zaten incelenmiştir.

## 7. Önceki çalışmayla ilişkisi

- R19'un **birincil F1−F0 kaçırma oranı, C1/A1 ve B10** karşılaştırması değiştirilmedi.
- R20'nin **eşit controller–block ≠ eşit toplam CPU / doğal arşiv belleği** bulgusu değiştirilmedi.
- R21'in iid/moving-block/bootstrap kalibrasyon başarısızlıkları geri alınmadı.
- R22, belirli ve açık varsayımlar altında **matematiksel garanti** veren alternatif araştırma denetleyicisidir. Eski F1'in alan geneli %5 FWER hatasını düzeltmiş sayılamaz.
- Henüz 30 yeni optimizer tohumu, yeni bağımsız kör TEST veya HIL/edge güvenliği gerçekleştirilmedi. Orijinal `seed1001/C1_F1_A1` yürütme SHA'sı `UNRECORDED_LOCAL_SHA` kalır.

## 8. Sonraki gerçek araştırma adımı

Pratik R23 için, gün düzeyinde zaman bağımlılığına **doğrulanmış** bir yapı (örneğin prospektif bağımsız epizodlar/tesisten ayrık kümeler), önceden sabitlenen mühendislik destek sınırları veya istatistiksel model varsayımları ile ve yeterli veriyle daha kısa güven aralıkları üretilebilmesi gerekir. Dağılımdan bağımsız bir garanti ile küçük örneklem / dar fark / düşük bellek maliyeti aynı anda vaat edilemez. Başarısız koşullarda `ABSTAIN` korunmalıdır.

**Bilimsel sonuç:** Sertifikalı yaklaşımın teoremi koşulludur; sentetik IID kolay senaryoda kapasite sağlasa da yakın-dominans ve gerçek OpenCEM şartlarında mevcut deneyle güvenilir bir saha seçimi elde edilmedi. **Yeni F1 saha üstünlüğü / bağımsız TEST: NO-GO**.
