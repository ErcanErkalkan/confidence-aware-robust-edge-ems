# CRMT — Rainflow ve Terminal SOC Metrik Etki Analizi (Aşama 1)

**Tarih:** 28 Ekim 2026  
**Durum:** `RETROSPECTIVE_ENGINEERING_PILOT_COMPLETE` — **tarihsel bilimsel deneyin yeniden yürütülmüş versiyonu değildir.**  
**Kod kaynağı:** `main` `2dcbaa49db42e7a0d4cb6edde3977f0384db1679`  
**Metrik:** `CRMT-METRICS-v2-RAINFLOW-TERMINAL-SOC`

## 1. Neyi gerçekten çalıştırdık?

- Kanonik Drive'dan kurtarılan özgün `seed1001_C1_A1` F0 **18 adaylık arşivin tamamı**, F1 **236 adaylık arşivden F0'ın 18 üyesi ve aday kimliğine göre sıralı ilk 10 ek üye** kullanıldı: toplam **28 aday**.
- OpenCEM, geçmişte kullanılmış **TRAIN** blokları: 2 Ağustos 2025 ve 31 Ağustos 2025, her gün inverter 1 ve inverter 2; 4 adet **720 kayıtlı ve 2 dakika aralıklı** blok.
- **112/112** aday–blok kombinasyonu için gerçek CRMT/EMS kontrolcü kodu yeniden yürütüldü. `simulate_controller` tek bir SOC/komut/şebeke izini oluşturdu; aynı iz hem orijinal `compute_metrics` hem `compute_metrics_v2` ile değerlendirildi.
- Ek çapraz doğrulama: orijinal tarihsel `candidate_metrics.csv` içindeki dört blok ve aday eşleştirildi. **Yeni simülasyon, özgün tarihsel yürütmenin eksiksiz tekrarlandığı varsayılmadan** ayrık tutuldu.
- **72/72** F0 olayının ikinci tekrarı, ilk pilotun eski/yeni sayısal değerleriyle **birebir** eşleşti. `tests/test_future_metrics_v2.py`: **9/9** başarılı.
- Bu, önceden maruz kalınmış verinin keşifsel mühendislik analizidir. **Yeni bağımsız TEST, R19 prospective AUDIT veya batarya ömür doğrulaması değildir.**

## 2. Metrik etkisi

| Ölçüt | Orijinal tarihsel legacy metriğiyle eşleşen olay | Aynı yeni simülasyonda eski→v2 değeri değişen olay | Ortalama v2−legacy farkı |
|---|---:|---:|---:|
| `cap_violation_pct_total` | 56/112 | 0/112 | 0 |
| `lfp_cycle_loss_pct` | 112/112 | 112/112 | -0.000138990256 |
| `ramp95_kw_per_min` | 112/112 | 0/112 | 0 |
| `flip_per_day` | 112/112 | 0/112 | 0 |
| `efcrf` | 112/112 | 112/112 | -0.0109425025 |
| `idod` | 112/112 | 112/112 | 7.64026341e-05 |

`lfp_cycle_loss_pct` için:

- v2−legacy farkı **112/112** olayda sıfırdan farklı.
- **85** olayda düzeltme daha düşük, **27** olayda daha yüksek model tabanlı kayıp verdi.
- Ortalama mutlak yönlü fark **-0.000138990 yüzde puan**; medyan fark **-0.000075361 yüzde puan**.
- Olay bazındaki yüzdesel değişimin medyanı **-23.51%** (her bir olayın legacy kaybına göre; yayımlanmış toplam kayıp tahmini değildir).
- En küçük / en büyük fark: **-0.000450334 / 0.000043559 yüzde puan**.

Sayısal karşı örnek: SOC `[0.2, 0.8, 0.2]` için legacy ağırlıklı çevrim derinliği **0.3**, v2 **0.6**. Legacy algoritmasının ara dönüş noktasını yanlış çıkarması geri dönüş yarım çevrimini düşürebilir. Ayrıca legacy `compute_metrics` yalnız `soc` sütununu kullanırken v2 son `soc_next` durumunu trajektoriye ekler.

**Sabit simülasyon izindeki diğer üç ana amaç değişmedi:** kapasite ihlali, `ramp95_kw_per_min`, `flip_per_day`. Bu, v2 kodunun bu alanları yeniden hesaplamayı değiştirmeyip legacy sonucunu korumasıyla tutarlıdır; başka bir tarihte yeniden yürütülmüş simülatör çıktı farkı yaratabileceği iddiası değildir.

### Tarihsel CSV ile birebirlik sınırlaması

Tarihsel `candidate_metrics.csv` ile yeni koşudaki *legacy* sonuçlar karşılaştırıldığında `lfp_cycle_loss_pct`, `ramp95_kw_per_min`, `flip_per_day`, `efcrf`, `idod` alanları **112/112** olayda `1e-9` tolerans içinde eşleşiyor. `cap_violation_pct_total` alanı **56/112** olayda farklı: `opencem:inv1:2025-08-02` ve `opencem:inv2:2025-08-31` için her olayda fark **+0.1388889 yüzde puan (1/720 tick)**. Diğer iki blok 56/56 eşleşiyor.

Bu, kapasite ihlali karşılaştırmasının eski yürütme ile tam pariteye ulaşmadığını gösterir. Orijinal zaman-adımı düzeyinde kontrolcü/şebeke izleri mevcut değilken kesin neden atfetmek doğru olmaz. Bu sorun sonraki gerçek tarihi yeniden yürütme çalışmasının açık doğrulama maddesidir.

## 3. Pareto duyarlılığı — yalnız sabit dört blok ortalaması

**Dikkat:** Aşağıdaki sonuç, tarihsel mean+CVaR / 12.600 olaylık bir optimizasyonun yeniden hesaplaması değildir. F0 ve seçilmiş F1 alt kümesinde dört ortak blok üzerindeki aritmetik ortalamalar ile **tam karşılaştırma** (dört minimizasyon amacı, exact dominance) yapılmıştır.

| Keşifsel aday kümesi | Eski front üye sayısı | v2 front üye sayısı | Pareto üyeliği değişen |
|---|---:|---:|---:|
| F0 (tam tarihsel 18 üye) | **9** | **10** | **1** |
| F1 (236 üyeden seçilmiş 28) | **12** | **13** | **3** |

Değişen kimlikler:

| Pilot küme | Aday | Eski front üyeliği | v2 front üyeliği |
|---|---|---|---|
| F0 | `CRMT-c0057` | False | True |
| F1 | `CRMT-c0004` | False | True |
| F1 | `CRMT-c0011` | True | False |
| F1 | `CRMT-c0057` | False | True |

Bu sonuçlar **metrik düzeltmesinin Pareto ilişkilerini değiştirebildiğini** gösterir. Ancak bu dört blokla tam F1 arşivinin yeniden sıralandığı veya yayımlanmış üstünlük iddiasının geçersiz olduğunun ispatlandığı söylenemez.

## 4. Tarihsel bilimsel çıkarım açısından durum

- Orijinal aday–blok *legacy* amaç değerleri korunmuştur; dosyalar üstüne yazılmadı.
- Bu pilotta gerçekten değişen ve tarihsel CSV'nin de doğruladığı amaç, model tabanlı `lfp_cycle_loss_pct`'dir. Diğer üç amaç aynı simülasyon izi için değişmedi.
- Eski bilimsel Pareto frontları, hypervolume, IGD, aday seçimi veya F0/F1 üstünlük iddiası **tam tarihsel kapsamda yeniden hesaplanmadı**. Yeni sonuç olarak etiketlenmeleri yasaktır.
- Tarihsel per-tick SOC/komut dizileri özgün candidate_metrics/optimizer_front/ledger dosyalarında bulunmuyor; yeniden simüle edilmiş güncel trajektorilerin özgün yürütmeye tam eşdeğer olduğu onaylanmış değil.
- Özgün fiziksel kimya/lifetime kanıtı yok. `lfp_cycle_loss_pct`, model vekilidir.

## 5. Devam için en önemli uygulanabilir adımlar

1. **Cap parity farkı:** 56/112 olayda bir zaman adımlık farkın, gerçek timestamp/şebeke/limit/boundary kararlarından hangisine bağlı olduğunu per-tick iz üzerinden araştır.
2. **F1 tamamı:** 236 adayın tamamı için ortak blok pilotunu parçalı çalıştırma/yeniden başlatma ile bitir; seçili 28 alt kümenin sonucu genellenmesin.
3. **Tam tarihsel pencere:** 20 koşulun tümünde adayın gerçekten değerlendirildiği blokları ve tam parametre tablolarını doğrula. Eski trajectory mevcut değilse aynı source ref ve özgün protokolle tekrar üret; yeni deney ID ve metrik sürümü kullan.
4. **Risk/Pareto:** Tam destek üzerinde eski-v2 `mean + lambda×CVaR` yeniden hesapla; Pareto/HV/ranking değişikliklerini aynı normalizasyon ve referans koşullarında ölç; delta için bağımsız birimi seed olarak belirle.
5. **Makale v14:** Bu pilotun sınırlı bulgusunu Methods/Limitations ekine koy; tarihsel üstünlüğü doğruladığını veya çürüttüğünü iddia etme.

## 6. Kaynak ve yeniden üretim

- [GitHub güncel kaynak](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/tree/2dcbaa49db42e7a0d4cb6edde3977f0384db1679)
- [Eski metrik kodu](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/blob/2dcbaa49db42e7a0d4cb6edde3977f0384db1679/src/jer_microgrid/metrics.py)
- [v2 metrik kodu](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/blob/2dcbaa49db42e7a0d4cb6edde3977f0384db1679/src/crmt_edge_ems/metrics_v2.py)
- [Orijinal OpenCEM lineage arşivi](https://drive.google.com/file/d/1_DFkvXdHMPROrfid3G8DRrztcwxg0E_J/view)
- [Tarihsel TRAIN aday dosyaları](https://drive.google.com/drive/folders/1yAzApyF0a05BpfOB-b0z_JrkGRZaDdN8)

SHA-256 kimlikleri `METRIC_SENSITIVITY_STATISTICS.json` içindedir. Bu rapor, kendi araştırma bağlamını ve kanıt kapsamını sınırlı tutar; kesin bilimsel onay verilmemiştir.
