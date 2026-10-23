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
- GitHub dal temizliği **tamamlandı**. [GitHub Actions tek seferlik temizleme işlemi](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/39909877273) başarılı sonuçlandı. Bağlayıcı üzerinden alınan dal listesi yeniden kontrol edildi: depoda **yalnızca `main`** mevcut.
- Silinen tarihsel dal referansları: `audit/crmt-eaai-gate2-30seed-20261009` ve `revision/crmt-eaai-evidence-sync-20261011`. Her ikisi silinmeden önce `main` karşılaştırmasında `ahead_by=0` idi. Eski commit'ler ve bilimsel kayıtlar `main` geçmişinde korunmuştur; force-push uygulanmadı. Temizlikte kullanılan geçici workflow dosyası da `main`den kaldırıldı.

## Çalışmanın tek bilimsel kronolojisi

1. Problem ve kontrolcü tasarımı: risk kalibreli dört amaç, dondurulmuş EMS kontrolcüsü ve veri semantiği.
2. Ana karşılaştırma: 30 optimizer seed; ortak bütçeli Sobol, NSGA-II, MOPSO, MODE ve CRMT; geçmiş TRAIN/VAL/internal TEST/OPSD aşamalarına özgü sonuçlar.
3. Faktöriyel mekanizma analizi: C (risk ağırlığı), F (arşiv yöntemi), A (adaptif bütçe), 5 seed × 8 = 40 TRAIN koşulu.
4. R6: 5 × 256 × 118 = 151.040 **tarihsel VALIDATION** controller–block kaydı.
5. R7/R8: F0/F1 arşiv ve kapasite tanılaması. F0 ve F1'in 20 eşleştirilmiş nihai K20 kısa listesi aynı; F1'in daha büyük arşivi tek başına operasyonel üstünlük göstermez.
6. R9: eşit kapasite ve değerlendirme bütçeli mekanizma testi ve *yeni bağımsız TEST* için ön kayıt taslağı. Henüz yeni bağımsız TEST yapılmamıştır; **NO-GO**.

## 23 Ekim 2026 veri kurtarma ve kanıt durumu

- OpenCEM dondurulmuş kaynak commit'i: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- 19 ham CSV parçasının **19'u da** tek Drive klasöründe; toplam **883.382.698 bayt**. Önceki 18 dosyanın Drive geri okuma SHA/Git blob denetimi başarılıdır; son parça da özgün pinned kaynaktan alınıp **Drive'a yüklenmiş ve bağımsız geri okuma ile doğrulanmıştır**. Her birinin SHA-256 değeri kayıtlıdır.
- Son kurtarılan kaynak: `data/measurements/2025-08-b.csv` (**2.493.086 bayt**) — [kanonik Drive dosyası](https://drive.google.com/file/d/1Gwdk8zwXFcibbONNAt9ZcscrV3NR1azc/view). Kaynak Git blob SHA-1 `ffbefbaca56761ee180074d0feb5d83553527c7e`, son dosya SHA-256 `d889a3b06693d76a5d04cc21b4c6d2ce4edf29710a021438a7979a6ad31ae041`. [GitHub Actions bağımsız pinned kurtarma](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/39919083779) başarılıdır; geçici recovery workflow dosyası `main`den kaldırılmıştır.
- Ham kaynak klasörü: https://drive.google.com/drive/folders/1vYO1Z7perxj-G3_nbeIys7ObSXFoHZYP (19/19, 883.382.698 bayt). Eski 18/19 CSV doğrulama tablosu tarihsel arşive taşındı; güncel 19/19 kapanış JSON/CSV kanıtı tek Drive projesine ayrıca kaydedilir.
- Kurtarma için kullanılan geçici GitHub Actions iş akışı başarıyla çalışıp silindi. Daha önce hazırlanan PowerShell aracı tarihsel kurtarma destek dosyasıdır; işlem şu anda tamamlanmıştır.

## R9 G2 prototipi — 23 Ekim 2026 (geliştirme, yeni TEST değil)

- [Yeni yöntem taslağı](R9_EQUAL_CAPACITY_POLICY_DRAFT_20261023.md) ve [TRAIN-only kaynak kodu](../tools/r9_equal_capacity_20261023/r9_capacity.py) mevcuttur; sentetik örnek ve 22 sentetik pytest testi ile yerelde doğrulandı. Çalışmanın tamamı için GitHub Actions pytest sonucu ayrıca kontrol edilmelidir.
- Bu politika F0/F1'in **aynı aday–TRAIN blok değerlendirme izini** ve ortak kullanılan bellek kapasitesini denetler. Eksik doğal arşiv slotlarını ortak TRAIN adaylarından tamamlayarak **yeni etkin bellek** üretir. Tarihsel orijinal F0/F1 arşivinin gerçek kapasitesi veya K20 seçimlerinin değiştiği anlamına gelmez.
- B=20, K=20 aday tasarım koşuludur; kilitlenmiş ön kayıt değildir. Birincil hipotez (C/A HV mi F0/F1 utility mi), B/K seçimi, tek nihai kontrolcü selector, yeni bağımsız TEST kaynağı ve örneklem birimi **onaylanmadı**. R9 G2 yalnız teknik ön prototip olarak ilerledi; G3–G4 BLOCKED ve yayın **NO-GO** devam eder.

## R7/R8 düzeltme ve araştırma sınırları

- R8 CSV'de `C0 → λ=0`, `C1 → λ=0.5` doğrulanmıştır. R8 metninin A0/A1'e bağladığı tanım raporlama hatasıdır.
- F1−F0 ortalama TRAIN arşiv farkı **143.35** (226.95−83.60) olup R7 metnindeki 143.45 ifadesi tutarsızdır.
- Düzeltme eki: https://drive.google.com/file/d/11SEgPZeU1Y3k7VzBM8kL1anAi8RDFw-Q/view
- Eski 78 internal TEST bloğu ve OPSD replay, yeni bağımsız kör TEST olarak yeniden adlandırılamaz.
- Arşiv büyüklüğü ve nihai K20 kontrolcü seçimi aynı nesne değildir. Yeni mekanizma üstünlüğü, istatistiksel anlamlılık ve saha performansı iddiaları doğrulanmamıştır.

## R9 retrospektif TRAIN kaynak denetimi (23 Ekim 2026)

- Google Drive'da 5 seed × 8 koşul = **40/40** ayrı TRAIN koşulunda `run_summary.json`, `candidate_metrics.csv`, `ledger.csv`, `optimizer_front.csv` bulundu (**160** dosya). Beş seed için kaynak yol/boyut envanteri `reproducibility/r9_historical_train_sources_20261023/seed1001.csv` … `seed1005.csv` altında.
- **40/40** run summary dosyasında seed, koşul, TRAIN split, 256 aday, 12.600 controller–block bütçesi ve C/F/A mod etiketleri denetlendi. 20 eşleştirilmiş F0/F1 çifti için **ledger SHA kimlikleri 20/20 aynı**, ancak `candidate_metrics.csv` ham SHA kimlikleri **20/20 farklı**. Bu ilk bulgu run-summary **beyan edilen hashler** üzerindendir.
- Örnek `seed1001, C0, A0` çifti için iki klasörün üçer CSV'si kaynak hashleriyle **6/6** eşleşti. 12.600×2 satır için ledger, dört bilimsel amaç ve tüm timing-dışı metrikler aynı; ham CSV farkları yalnız `mean_cpu_ms` (12.600 satır) ve `max_cpu_ms` (12.599 satır). Diğer **19 çift henüz bağımsız byte düzeyinde** yeniden incelenmedi.
- 20 çiftte tarihsel doğal arşiv ortalamaları **F0=83,60**, **F1=226,95**, **F1−F0=+143,35**. Bu eşit kapasite B deneyinin sonucu değildir.
- Kaynak doğrulama kodu: [TRAIN pair preflight](../tools/r9_equal_capacity_20261023/r9_train_pair_preflight.py); sentetik regresyon [12 test](../tests/test_r9_train_pair_preflight.py); [kanıt raporu](R9_HISTORICAL_TRAIN_INPUT_AUDIT_TR_20261023.md). Kod gerçek TRAIN verisi üzerinde 1 çift için çalıştı ve GitHub Actions pytest kontrolü başarılıdır.
- **R9 deneyi HENÜZ ÇALIŞTIRILMADI.** B/K, backfill, C riskine göre dört amaç için TRAIN agregasyonu, tek birincil hipotez ve bağımsız yeni TEST veri kilidi hâlâ açık; **NO-GO**.

## Repo – Drive ayrımı ve yeniden üretilebilirlik

- GitHub `main` **güncel geliştirilen kaynak/metadata** konumudur. Büyük ham veri dosyaları ve deney sonuçları Git deposuna yüklenmez.
- Drive `CRMT_RESEARCH_PROJECT` veri, deney arşivi, makale ve raporların tek üst klasörüdür.
- Bilimsel yeniden üretim için her deney kendi **dondurulmuş commit** ve kaynak kilidine bağlanır; örnek: eski R6–R8 çalışmalarıyla ilişkilendirilen yürütme commit'i `be5756321617087ca421a639d60a99513f29d889`. GitHub'daki en yeni `main` commit'i geçmiş deneyin çalıştırıldığı commit'in yerine geçirilmez.
- Proje **yönetim düzeni** ve GitHub dal birleştirme tamamdır. Tam veri aktarımı, bazı dış test ön koşulları ve nihai yayın kanıtları açık kalır.

## Kalan eylemler

- [x] Dalların ve dosyaların karşılaştırılması.
- [x] 14 tarihsel araştırma dosyasının PR #2 ile `main`e birleştirilmesi.
- [x] Eski dalların `main`den ileride olmadığına dair karşılaştırma.
- [x] Eski iki dalın GitHub Actions ile güvenli şekilde kaldırılması; son dal listesinde yalnızca `main` görülmesi.
- [x] `2025-08-b.csv` özgün kaynağının eksiksiz aktarılması, sha eşlemesi ve bağımsız Drive geri okuması.
- [x] R9 G2 için TRAIN-only deterministik eşit bellek / eşit değerlendirme izi prototipi ve sentetik testleri (`tools/r9_equal_capacity_20261023/`, `tests/test_r9_capacity_policy.py`).
- [ ] R9 G2 tasarımının araştırmacı onayı, B/K ve backfill ön kilidi, GERÇEK eşit bütçeli TRAIN çalışma loglarının kilitlenmesi.
- [ ] R9 G3–G4 yeni bağımsız veri, maruziyet ayrıklığı ve tek birincil uç / güç / safety ön kayıt kilitleri.
- [ ] Yeni bağımsız TEST'in protokole uygun çalıştırılması ve makalenin yeni kanıtlarla güncellenmesi.

**Ana kural:** Depoda yalnız `main` dalı bulunur. Her yeni uygulama ve düzeltme yalnız `main`e girer; ikinci bir aktif araştırma dalı oluşturulmaz. Bu dosyanın son commit'i, geçmiş deney kanıtlarını yeniden etiketlemez.
