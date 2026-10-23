# CRMT | Tek kanonik proje ve GitHub main kaydı

**Durum tarihi:** 2026-10-23  
**Kanonik GitHub kod deposu:** https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems  
**Kanonik çalışma dalı:** `main`  
**Kanonik Google Drive proje klasörü:** https://drive.google.com/drive/folders/1g8afkrJCfF4fFSNxS1kJo9aQISGOlBne

## Tek proje ilkesi

CRMT (Confidence-Aware Risk-Calibrated Multiobjective Tuning for Edge Microgrid Energy Management under Distribution Shift) başlangıçtan bugüne **tek araştırma projesidir**. Applied Soft Computing v12 ve daha sonra EAAI/Gate3 diye anılan dosyalar iki ayrı proje değil, aynı projenin geçmiş makale ve deney aşamalarıdır. Ancak **bilimsel örneklemler, veri kümeleri ve TEST statüleri birleştirilmez**. Tarihsel iddia ve kaynak kimlikleri korunur.

## Dal birleştirme (tamamlandı)

23 Ekim 2026'da [PR #2](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/pull/2) ile `revision/crmt-eaai-evidence-sync-20261011` dalının tamamı `main`e birleştirildi. Bu dal, `audit/crmt-eaai-gate2-30seed-20261009` geçmişini de içermektedir.

- Merge commit: `d8615d8a71880f13945e8f3407b226e08d7e1e5d`.
- Main üzerinde eklenen tarihsel içerik: `research_audits/` altında 14 dosya, yalnız ekleme (1.618 satır); yürütme kodunun mevcut `src/` dosyaları birleştirmeden değişmedi.
- Birleştirme sonrasında her iki eski dalın `main`e göre `ahead_by=0` olduğu ayrıca doğrulandı.
- GitHub dal silme işlemi henüz **tamamlanmadı**. Eski dal adları silinene kadar `main` tek **yetkili/aktif** daldır, fakat depoda fiziksel olarak birden fazla dal bulunmaktadır.
- GitHub dal temizliği için silinecekler: `audit/crmt-eaai-gate2-30seed-20261009`, `revision/crmt-eaai-evidence-sync-20261011`. GitHub arayüzünde repo → Branches ekranından `main` dışındaki iki dal silinebilir. **`main` silinmez ve force-push yapılmaz.**

## Çalışmanın tek bilimsel kronolojisi

1. Problem ve kontrolcü tasarımı: risk kalibreli dört amaç, dondurulmuş EMS kontrolcüsü ve veri semantiği.
2. Ana karşılaştırma: 30 optimizer seed; ortak bütçeli Sobol, NSGA-II, MOPSO, MODE ve CRMT; geçmiş TRAIN/VAL/internal TEST/OPSD aşamalarına özgü sonuçlar.
3. Faktöriyel mekanizma analizi: C (risk ağırlığı), F (arşiv yöntemi), A (adaptif bütçe), 5 seed × 8 = 40 TRAIN koşulu.
4. R6: 5 × 256 × 118 = 151.040 **tarihsel VALIDATION** controller–block kaydı.
5. R7/R8: F0/F1 arşiv ve kapasite tanılaması. F0 ve F1'in 20 eşleştirilmiş nihai K20 kısa listesi aynı; F1'in daha büyük arşivi tek başına operasyonel üstünlük göstermez.
6. R9: eşit kapasite ve değerlendirme bütçeli mekanizma testi ve *yeni bağımsız TEST* için ön kayıt taslağı. Henüz yeni bağımsız TEST yapılmamıştır; **NO-GO**.

## 23 Ekim 2026 veri kurtarma ve kanıt durumu

- OpenCEM dondurulmuş kaynak commit'i: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- 19 ham CSV parçasından **18'i** tek Drive klasöründe; toplam **880.889.612 bayt**. Bu 18 kopya gerçek içerikten hesaplanan Git blob SHA-1 ile eşleşti; SHA-256 her kopya için kaydedildi.
- Eksik tek kaynak: `data/measurements/2025-08-b.csv` (**2.493.086 bayt**, beklenen Git blob SHA-1 `ffbefbaca56761ee180074d0feb5d83553527c7e`). GitHub'daki dondurulmuş kaynak blob mevcut, fakat Drive'a aktarım henüz yapılmadı.
- Doğrulama tablosu: https://drive.google.com/file/d/11oMMP7d1G2wHrFiLFjFlcgttpWKY3vMS/view
- Kaynak kurtarma aracı: https://drive.google.com/file/d/1RGQOhMeBR2oKK4k1wHfNFq3dtmEUBvuc/view

## R7/R8 düzeltme ve araştırma sınırları

- R8 CSV'de `C0 → λ=0`, `C1 → λ=0.5` doğrulanmıştır. R8 metninin A0/A1'e bağladığı tanım raporlama hatasıdır.
- F1−F0 ortalama TRAIN arşiv farkı **143.35** (226.95−83.60) olup R7 metnindeki 143.45 ifadesi tutarsızdır.
- Düzeltme eki: https://drive.google.com/file/d/11SEgPZeU1Y3k7VzBM8kL1anAi8RDFw-Q/view
- Eski 78 internal TEST bloğu ve OPSD replay, yeni bağımsız kör TEST olarak yeniden adlandırılamaz.
- Arşiv büyüklüğü ve nihai K20 kontrolcü seçimi aynı nesne değildir. Yeni mekanizma üstünlüğü, istatistiksel anlamlılık ve saha performansı iddiaları doğrulanmamıştır.

## Repo – Drive ayrımı ve yeniden üretilebilirlik

- GitHub `main` **güncel geliştirilen kaynak/metadata** konumudur. Büyük ham veri dosyaları ve deney sonuçları Git deposuna yüklenmez.
- Drive `CRMT_RESEARCH_PROJECT` veri, deney arşivi, makale ve raporların tek üst klasörüdür.
- Bilimsel yeniden üretim için her deney kendi **dondurulmuş commit** ve kaynak kilidine bağlanır; örnek: eski R6–R8 çalışmalarıyla ilişkilendirilen yürütme commit'i `be5756321617087ca421a639d60a99513f29d889`. GitHub'daki en yeni `main` commit'i geçmiş deneyin çalıştırıldığı commit'in yerine geçirilmez.
- Proje **yönetim düzeni** ve GitHub dal birleştirme tamamdır. Tam veri aktarımı, bazı dış test ön koşulları ve nihai yayın kanıtları açık kalır.

## Kalan eylemler

- [x] Dalların ve dosyaların karşılaştırılması.
- [x] 14 tarihsel araştırma dosyasının PR #2 ile `main`e birleştirilmesi.
- [x] Eski dalların `main`den ileride olmadığına dair karşılaştırma.
- [ ] Eski iki dalın GitHub'dan kaldırılması (dal silme yeteneği mevcut bağlayıcıda yok).
- [ ] `2025-08-b.csv` özgün kaynağının eksiksiz aktarılması ve hash doğrulaması.
- [ ] R9 eşit bütçe ve bağımsız veri ön kayıt kilitlerinin tamamlanması.
- [ ] Yeni bağımsız TEST'in protokole uygun çalıştırılması ve makalenin yeni kanıtlarla güncellenmesi.

**Ana kural:** Her yeni uygulama ve düzeltme yalnız `main`e girer; ikinci bir aktif araştırma dalı oluşturulmaz. Bu dosyanın son commit'i, geçmiş deney kanıtlarını yeniden etiketlemez.
