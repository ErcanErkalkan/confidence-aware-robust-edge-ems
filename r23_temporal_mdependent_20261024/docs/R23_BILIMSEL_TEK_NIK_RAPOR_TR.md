# CRMT R23 — Sonlu Zaman Bağımlılığında Varyans-Duyarlı, Havuzlanmış CVaR Pareto Sertifikası

**Tarih:** 24.10.2026  
**Araştırma durumu:** Koşullu yöntem kanıtı + sentetik simülasyon; **saha garantisi, bağımsız TEST ve dergi kabul kanıtı değildir.**

## 1. Gerekçe ve R22'ye göre düzeltme

R21 analizinde, bağımsız örnekler varsayıldığında CVaR bootstrap arşiv-geneli eşzamanlı güven kapsamasının ciddi sapabildiği gösterildi. R22 koşullu DKW sınırı oluşturdu ancak günlük iki inverter kaybını **önce ortalayıp**, ardından bu günlük kaybın CVaR'ını aldı. Bu, özgün CRMT optimizasyonundaki **havuzlanmış controller–block riskinden farklıdır.**

R23'ün risk hedefi değiştirilmemiştir. Dört amaç için:

\[
 R_{c,j}=\mathbb E[X_{c,j}]+\lambda\operatorname{CVaR}_{q}(X_{c,j}),\quad
 q=0.90,\;\lambda=0.5.
\]

Burada \(X_{c,j}\), rastgele seçilen günün iki inverterinden **rastgele seçilen tek bir inverter/blok kaybıdır**. Bir günde iki inverterin ölçümleri birbirine bağımlı olabilir. Ampirik hedef bütün \(2n\) inverter–gün ölçümünden hesaplanır; günlerin ortalama kaybının CVaR'ı **değildir**. Bu tanım için marjinal dağılımın günler boyunca sabit kalması gerekir.

## 2. Açık varsayımlar ve kanıt kapsamı

**Koşullu matematiksel garanti ancak şu koşullarda geçerlidir:**

1. Kontrolcü aday havuzu (\(C\)), dört amaç, kuyruk katsayıları, amaçların kesin gerçek desteği \([a_j,b_j]\), \(K\) adet eşit aralıklı eşik ve tek test anı sonuç görülmeden önce sabitlenmiştir.
2. Her günde tüm adaylar için aynı gün 2 inverter × 4 amaç eksiksizdir; uydurma, doldurma, winsorization veya clipping **yoktur**.
3. Tüm kontrolcüler ve amaçlar için gün vektörü dizisi **katı durağan** ve bilinen sonlu \(m\)-bağımlıdır: zaman aralığı \(m\)'den büyük olan sigma-cebirleri bağımsızdır. Bu çok güçlü bir varsayımdır, **AR(1) genelde sonlu \(m\)-bağımlı değildir**.
4. Gün vektörleri, aday seçimi ve deney protokolünün hazırlanmasında kullanılmamıştır; ayrı AUDIT-TRAIN kullanılıyorsa R19'daki ön seçim kilidi ayrıca geçerlidir.
5. Tek seferlik \(\delta=0.05\) değerlendirme yapılır. Güven bandına bakarak durma zamanı seçmeye ilişkin anytime/optional-stopping garantisi **yoktur**.

Hiçbirinin gerçek OpenCEM için doğrulanmış bir belgesi bulunmamaktadır. `SyntheticDesign` veri tipindeki işaretler yalnız deney üreticisinin kod içi kimliğidir; gerçek tesis için bağımsız dış onay değildir. Kaynak kodunu çağıran kişi sahte bir işaret üretebilir. Bu nedenle **R23 gerçek veriye sertifikalı güvenilirlik uygulamıyor**.

## 3. Teorem ve uygulama

İki inverterin tek gün üzerindeki ortalaması üzerinden, her sabit eşik için

\[
G_{c,j,t}(u)=\frac12\sum_{v=1}^2 (X_{c,j,t,v}-u)_+
\]

tanımlanır. Bu, günlük **CVaR kaybı değildir**: havuzlanmış blok dağılımının pozitif-parça beklentisi için bağımlılığı kümeler içinde tutan yansız bir terimdir.

Rockafellar–Uryasev temsili:

\[
 \operatorname{CVaR}_q(X)=\inf_{u\in[a_j,b_j]}
 \left(u+\frac{\mathbb E[G(u)]}{1-q}\right).
\]

Destek boyunca sonuçlar görülmeden belirlenmiş \(K=31\) eşit eşiğe sahip ızgarada \(u_1,\dots,u_K\), aralık uzunluğu \(h=(b_j-a_j)/(K-1)\) olur.

Sonlu \(m\)-bağımlı dizi \(m+1\) renk sınıfına \(t\bmod(m+1)\) ile ayrılır. Sınıf içindeki gün vektörleri **bağımsızdır**. Katı durağanlık aynı fonksiyon beklentisinin her renk için aynı olmasını sağlar.

Her renk için, gün ortalaması ve sabit eşiklerin pozitif-parça ortalamalarının beklenen değerleri, iki taraflı Hoeffding veya örneklem varyansına duyarlı Maurer–Pontil Empirical Bernstein (EB) güven aralığıyla kontrol edilir:

\[
 e_{r,f}=\sqrt{\frac{2\widehat V_{r,f}\log(4F(m+1)/\delta)}{n_r}}
 +\frac{7(b_j-a_j)\log(4F(m+1)/\delta)}{3(n_r-1)},
\]

\(F=4C(K+1)\), \(\widehat V\) örneklem varyansı, \(n_r\) o renk sınıfındaki gün sayısıdır. `hoeffding` seçeneğinde ilk toplam yerine doğrudan \((b_j-a_j)\sqrt{\log(4F(m+1)/\delta)/(2n_r)}\) kullanılır. Renk sınıfı güven yarıçapları \(n_r/n\) ağırlıklarıyla birleştirilir. Bu, tüm \(F(m+1)\) sabit fonksiyon/renk olaylarına union-bound sağlar; renkler arası bağımsızlık iddiası yapılmaz.

\(\phi(u)=u+(1-q)^{-1}\mathbb E[(X-u)_+]\) fonksiyonunun Lipschitz sabiti \(L_\phi=\max(1,q/(1-q))=9\)'dur. Böylece gözlenen ızgara minimumu \(\widehat\phi_{\min}\), ortak hinge yarıçapı \(e_h\) ve ızgara aralığı \(h\) için:

\[
\operatorname{CVaR}_q(X)\in
[\widehat\phi_{\min}-e_h/(1-q)-L_\phi h/2,\;
 \widehat\phi_{\min}+e_h/(1-q)].
\]

Bu CVaR bandı ortalama güven bandıyla \(\lambda=0.5\) kullanılarak birleştirilir ve fiziksel destekten gelen \([(1+\lambda)a_j,(1+\lambda)b_j]\) sınırına kesiştirilir. Bütün adaylar, renkler, amaçlar ve önceden belirlenmiş eşikler için bu olay aynı anda sağlandığında, sertifikalı \(i\to j\) baskınlığı:

\[
\forall k\in\{1,2,3,4\}:\quad U_{i,k}<L_{h,k}
\]

şartına göre kurulur; burada \(i\) ve \(h\) adayları, \(k\) ise amaç kimliğini gösterir. Kodda `upper_risk[i,k] < lower_risk[h,k]` uygulanır. Bu çok katı tüm-amaçlarda-iyileşme kuralıdır; klasik Pareto için gerekli olmayan şartlarla, bilerek konservatif seçilmiştir. İstenen kapasiteye sertifikalı eleme ile inilemiyorsa sonuç **ABSTAIN** olur.

**Teoremin sonucu:** Yukarıdaki tüm varsayımlar altında bir defalık, sabit sonlu aday havuzunun herhangi bir gerçek Pareto adayını yanlış sertifikalı eleme olasılığı en fazla \(\delta\)'dır. Bu gerçek saha iddiası veya gelecekte seçilen başka aday havuzlarına yönelik koşulsuz garanti değildir.

## 4. Sentetik deney tasarımı

- Beş sabit aday, dört amaç, iki inverter; amaç kaybı gerçek desteği [0,4], her koşul 30 bağımsız sentetik tekrar.
- `iid`: gün vektörleri IID; `finite_MA` 2-gecikmeli sonlu bağımlılık üretir; m=2 dış girdisi sentetik üreticiden bilinir.
- Yakın adaylar gerçek Pareto sınırına çok yakındır; `AR1` (sonsuz kuyruk bağımlılığı) için model tanıklığı yoktur; eksik blok koşulunda kaynak reddedilir.
- Karşılaştırma `hoeffding` ve `empirical_bernstein`, aynı eşikler K=31, aynı risk, aynı \(\delta\), aynı tam veri üzerinde yapılmıştır.
- Stres testi arşivi B=3; R19 birincil B=K=10 **değiştirilmedi**. Bu sentetik referans gerçek CRMT 256 adaylı maliyet hesabı değildir.

## 5. Bulgular (30 tekrar/koşul)

| Senaryo | Gün | Hoeffding kapasite kararı | EB kapasite kararı | EB yanlış Pareto eleme |
|---|---:|---:|---:|---:|
| IID kolay | 600 | 0/30 | 0/30 | 0/30 |
| IID kolay | 2.000 | 0/30 | **30/30** | 0/30 |
| IID kolay | 4.000 | 30/30 | 30/30 | 0/30 |
| MA(2) kolay | 2.000 | 0/30 | 0/30 | 0/30 |
| MA(2) kolay | 4.000 | 0/30 | **30/30** | 0/30 |
| MA(2) yakın | 4.000 | 0/30 | 0/30 | 0/30 |
| AR1 / sonlu m belirsiz | 400 | BLOCKED | BLOCKED | Ölçülmedi |
| Eksik blok | 600 | BLOCKED | BLOCKED | Ölçülmedi |

Her uygun sentetik senaryoda yanlış Pareto eleme gözlemi sıfırdır; özellikle **0/30**, gerçek hata oranının sıfır olduğunu göstermez. Aynı sentetik üretim koşullarında daha küçük örneklemle karar verebilmek, yalnız **bu dağılımlar, bu önceki destek aralığı ve bu adaylar** için geçerlidir. Daha büyük destek, daha yüksek varyans veya farklı korelasyonda sonuç değişebilir.

## 6. Gerçek TRAIN veri kontrolü

R16'nın orijinal SHA doğrulanmış dosyalarından `seed1001`, `seed1004`, `seed1005` koşulları ham F0/F1 bilimsel metrikleri ve 12.600'er kontrolcü-blok değerlendirimi bazında yeniden eşleştirildi. En az 5–9 takvim günü gören kontrolcüler ve 106 gün gören kontrolcüler aynı çalışma içinde bulunmaktadır. Aynı 256 kontrolcünün tümü için eksiksiz eş zamanlı gün paneli; destek sınırlarının ön kaydı; sonlu m-bağımlılık ve durağanlık kanıtı **yoktur**. R23 gerçek OpenCEM'e **sertifikalı karar uygulamamıştır**.

## 7. Sınırlar / yapılması gerekenler

- **Bağımlılık:** AR(1) gibi sonsuz etkili zaman bağımlılığına `m=2` seçmek bilimsel olarak yanlış olur. Yerel otokorelasyon görselleştirmesi sonlu m-bağımlılığı kanıtlamaz. Fiziksel/üretim süreçleri için yapısal bağımlılık kanıtı, ya da farklı hata garantili bir yöntem gerekir.
- **Varyans duyarlılığı:** EB sınırı örneklem varyansına dayanır; bu yalnız garanti varsayımları altında avantaj sağlar. Veri dağılımını görerek destek sınırı daraltmak garanti ihlalidir.
- **Maliyet:** EB işlem zamanı ve K eşikli hinge hesabı ölçülmediği sürece R20 eşit toplam CPU kabul edilemez. Bu sürüm hesaplama karşılaştırması değil, istatistiksel karar oranı karşılaştırmasıdır.
- **R19:** C1/A1, B=K=10, 12.600 discovery değerlendirimi, ayrı TRAIN-AUDIT referansı ve 2001–2030 tohum planı korunur. 30 yeni tohum çalıştırılmadı, bu protokol dışarıdan ön-kayıtlı değil.
- **Fiziksel güvenlik:** Pareto seçimi sadece istatistiksel ve çok amaçlı sıralama iddiasıdır; SOC, inverter koruma veya batarya ömrü saha testlerinin yerine geçmez.
- **Tarihsel SHA:** seed1001/C1_F1_A1 özgün run Git SHA hâlâ `UNRECORDED_LOCAL_SHA`. Değiştirilmedi.
- **Yeni TEST:** bağımsız, hiç görülmemiş ve onaylı kaynak henüz yok. **EAAI/new superiority NO-GO**.

## 8. Yöntem ve akademik kaynaklar

- Maurer, A. & Pontil, M. (2009), *Empirical Bernstein Bounds and Sample Variance Penalization*, arXiv:0907.3740. https://arxiv.org/abs/0907.3740
- Rockafellar, R. T. & Uryasev, S., *Optimization of Conditional Value-at-Risk*, Journal of Risk (2000), tail-risk variational representation.
- Hoeffding, W. (1963), *Probability Inequalities for Sums of Bounded Random Variables*, JASA 58.

**Ürün:** kaynak/doğrulama/test/protokol/sonuçların birlikte olduğu sürümlü R23 ZIP. Bu belge önceki R22 bulgularını geçersiz kılmaz; farklı varsayım sınıfında, orijinal risk estimand'ını koruyan daha az konservatif koşullu yöntem araştırmasıdır.
