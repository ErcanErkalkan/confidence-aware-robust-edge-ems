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

## R9 tarihsel TRAIN kaynak commit engeli (23 Ekim 2026 denetim düzeltmesi)

- 40/40 koşulda kaynak CSV bağlantıları bulunuyor; **39/40** historical `run_summary.json` dosyası beklenen donmuş Git SHA'yı *bildiriyor*. **seed1001/C1_F1_A1** dosyası `original_git_sha=UNRECORDED_LOCAL_SHA` içeriyor, bu yüzden aynı yürütme commit'i henüz ispatlanamıyor. Orijinal source summary değiştirilmeyecek.
- 20/20 F0/F1 çiftinin run summary'sindeki ledger SHA-256'lar eşit; candidate_metrics ham SHA-256'lar farklı. **8/20 çiftin gerçek Drive CSV baytları** SHA-256 ve TRAIN ölçüm alanlarıyla yeniden doğrulandı; beş tohumdan örnekler ve A0/A1 koşulları mevcut. **Kalan 12 çiftin** non-CPU bilimsel eşitliği henüz ispatlanmamıştır. [8/20 kanıt fişi](../reproducibility/r9_historical_train_sources_20261023/R9_EIGHT_PAIR_BYTE_AUDIT_RECEIPT.json) ve [güncel metodoloji sınırı](R9_TRAIN_PROVENANCE_BLOCKER_20261023.md).
- Düzeltme ve kapı raporu: [R9_TRAIN_PROVENANCE_BLOCKER_20261023.md](R9_TRAIN_PROVENANCE_BLOCKER_20261023.md). Genel koşul manifesti: [GLOBAL_SOURCE_PROVENANCE_GATE_20261023.json](../reproducibility/r9_historical_train_sources_20261023/GLOBAL_SOURCE_PROVENANCE_GATE_20261023.json). GitHub sadece tek `main` dalında kalır.
- **R9 bağımsız TEST: NO-GO**. B/K/hipotez/ön-kayıt ve yeni bağımsız veri kilidi yoktur.

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

## Current evidence addendum — 24 October 2026 (R18)

**This is a current-state addendum, not a rewriting of historical 23 October receipts.** The previous 8/20 byte-audit figure above describes the earlier GitHub snapshot, not current cumulative archive-membership coverage.

- [R18 canonical evidence report](CRMT_R18_CURRENT_STATUS_20261024.md) and [20-pair membership receipt](../reproducibility/r18_archive_membership_20261024/R18_MEMBERSHIP_20.csv) are now the current **TRAIN archive membership** summary.
- R18 fetched original F0/F1 optimizer-front candidate-ID sets for **20/20 historical seed×C×A pairs**; 12 pairs have locally rehashed original front bytes bundled in the Drive R18 package, and 8 pairs have remote source-membership readouts only (no current R18 local raw-byte recheck).
- **18/20 pairs** have F0 set included in F1; two are exceptions: `seed1001/C0/A0` and `seed1001/C1/A0`, each with F0-only `CRMT-c0089`. Never claim universal F0 subset F1.
- Historical natural archive means are **F0=83.60**, **F1=226.95**. This is not an equal-native-B performance study. Identical historical K20 selections do not demonstrate a beneficial F effect.
- The original `seed1001/C1_F1_A1` **runtime Git SHA remains unresolved**, even though the R17 post-hoc checkout audit verified frozen HEAD `be575632...`; do not modify the immutable `run_summary.json` marker `UNRECORDED_LOCAL_SHA`.
- R9 prospective method lock, complete exposure non-leakage, new independent unseen TEST and independently reviewed preregistration remain **BLOCKED**; EAAI prospective performance **NO-GO**. R10–R13 remain synthetic exploratory work and ASOC v12 preparation is not proof of actual portal submission.
- Source ZIP and R18 verification scripts: [Google Drive R18 control folder](https://drive.google.com/drive/folders/13v08AhC4ktFHlxrEDNUQ0_LUt0jye6a-). The original historical source files and experimental artifacts have not been changed by this addendum.

## 24 October 2026 R18-v2 final source-front byte audit

The earlier R18 addendum below the 23 October historic status accurately described the **R18-v1** intermediate snapshot (12 locally rehashed pairs and 8 connector-read pairs). **R18-v2 has superseded that current coverage**: all 40 original `optimizer_front.csv` files for 20 matched F0/F1 historical TRAIN pairs are now included in the independently runnable R18-v2 ZIP and their local SHA-256 values match recorded original-run-summary or original-summary-derived source review checksums. The 20 paired membership outcomes were recomputed from all 40 local files. The old original TRAIN outputs are unchanged.

- Current report: [R18-v2 original-archive SHA / membership coverage](CRMT_R18_CURRENT_STATUS_20261024.md).
- Current source-checked receipt: [R18 20-pair membership CSV](../reproducibility/r18_archive_membership_20261024/R18_MEMBERSHIP_20.csv).
- Original-source package and 12 locally successful regression tests: [R18-v2 Drive folder](https://drive.google.com/drive/folders/13v08AhC4ktFHlxrEDNUQ0_LUt0jye6a-), file `CRMT_R18_V2_Tum20Cift_KaynakSHA_Dogrulanmis_20261024.zip`.
- **18/20** F0 archives are subsets of F1; two exceptions `seed1001/C0/A0` and `seed1001/C1/A0` each contain F0-only `CRMT-c0089`.
- The source-code execution moment for `seed1001/C1_F1_A1` remains **UNRESOLVED**, not repaired by post-hoc HEAD evidence. Prospective equal-B/K strategy, independent unseen TEST, human-reviewed preregistration and physical safety are still **BLOCKED**. EAAI new superiority claim remains **NO-GO**.

## 24 October 2026 R19 — primary scientific question resolution (design-only)

The **first P0 research design gap** (a single primary R9/F mechanism question) has been resolved as a **reviewable internal design draft** at [R19 protocol and source](../r19_primary_hypothesis_20261024/README_TR.md). The proposed single contrast is **F1−F0 missed Pareto fraction** at C1/A1, B=K=10, no backfill; same 12,600 controller×discovery-TRAIN events, with all 256 candidates uniformly rescored on separately held-out **TRAIN-only AUDIT** blocks before calculating the paired seed-level difference. Source-linked historical B10 feasibility covers 20/20 old F0/F1 pairs. R19 includes machine-readable config and fail-closed discovery/audit two-phase code; **25 local tests passed**; the independently re-opened ZIP passed the same 25 tests and file SHA checks.

**Important restrictions:** Chosen after historical results were inspected; `locked=false`, NOT independent preregistration, NOT new TEST, and no R19 prospective new-30-seed runs were performed. Thirty seeds are a **provisional** seed manifest pending power analysis: a normal paired approximation suggests 32 seeds are needed even under assumed SD 0.10 to detect a five-percentage-point effect with 80% power. The source split, temporal independence/embargo, CPU/memory and physical safety, external time-stamped preregistration, original missing seed1001 run SHA, and new blinded TEST remain unresolved / NO-GO. The B10 bound is a **post-archive output shortlist capacity**, not equal native archive construction memory cost. The original historical `src/`, R6–R18 outputs, and old run_summary records remain immutable.

Source bundle and design evidence: [R19 Drive control folder](https://drive.google.com/drive/folders/1MmiNVDJTHyYGkOUQCKKjkugb-cTHyov2) — use the `11_PROJECT_CONTROL_20261022/R19_20261024` sibling of R18 (see repository R19 README for the exact deliverables and canonical project tree).

## 24 October 2026 R20 — Equal-budget and native archive cost audit

**R19 scientific primary contrast remains unchanged** (C1/A1, F1−F0 missed finite TRAIN-AUDIT Pareto fraction, B=K=10, no backfill); R20 adds distinct **cost accounting** under this output-capacity design. Do not interpret equal simulator evaluation budgets or B10 post-archive shortlist sizes as equal *native archive memory* or equal *total CPU*.

- [R20 source/tests, resource protocol and report](../r20_equal_cost_20261024/README_TR.md) added separately. The original frozen CRMT `src/` or historical results were **not modified**.
- [R20 full portable source ZIP with original historical R16 bundle and 28 passing tests](https://drive.google.com/drive/folders/1NrpG1JxfXRpgVcA6JOLY34H7PGsyukyP), separate revisioned `11_PROJECT_CONTROL_20261022/R20_20261024` folder.
- R20 rechecked **10/10** locally available historical paired TRAIN source sets with original summary SHA, exact 12,600 F0/F1 controller-block ledgers and four identical science objectives. **Only three C1/A1 seed pairs** are present with complete original R16 raw files; all are historical/seen.
- Those C1/A1 pairs have F0 native archive sizes 18/22/17 and F1 236/240/237, respectively; exported B10 is identical but native storage is not equal.
- Historical `mean_cpu_ms*n_ticks` sums give simulator-tick CPU **proxies only**, not original archive/bootstrap CPU or total measured wall/CPU. Those historical fields are **NOT_RECORDED**.
- Opt-in R20 CPU microbenchmark uses the **exact source Git blobs** for `risk.py`, `dominance.py`, `archive.py` (reverified after GitHub publication), but replays only 8, 16 and 32 original TRAIN candidates for each of two seeds, **n_boot=200**; no full-256 or original-config runtime claim permitted. New run instrumentation contract verifies matched source/ledger/hardware and requires explicit real phase-level timing.
- **E2 equal *total* CPU or bounded *native* archive-capacity experiment is a separate research estimand, not executed**. R19 new seeds=NOT_RUN, original run SHA for seed1001/C1_F1_A1 remains UNRECORDED_LOCAL_SHA, new unseen independent TEST **NO-GO** and hardware/SOC safety **NOT_TESTED**.

## 24 October 2026 R21 — archived confidence calibration under dependence

[GitHub R21 code, 26 regression tests, report, results](../r21_confidence_calibration_20261024/README_TR.md) and [R21 complete portable source ZIP including historical SEEN TRAIN](https://drive.google.com/drive/folders/1hUW55PnxyQJD3Cjins2BxSzDmPjiRuCx). This addition does **not** modify frozen `src/` or any historic run records.

- Distinct exploratory **step 3**, not R19's B=K=10 primary confirmatory design: 5 Gaussian synthetic scenarios × 4 methods × 80 replicates = **1600 method-repetition results**; 5 candidates, 4 objectives, 48 time blocks, artificial B=3 stress capacity, 350 bootstrap draws.
- The original unmodified Git blob `risk.py`, `dominance.py`, `archive.py` are verified, and a test reproduces actual `ConfidenceArchive` member selection with R21 ordered-pair calls.
- In IID clear/near scenarios, the **archive-wide any-objective any-ordered-pair bootstrap upper-bound undercoverage** of F1 legacy was 54/80 and 62/80, compared with exploratory shared max-T IID 8/80 and 9/80. Neither is a demonstrated global 5% error guarantee.
- With strong AR(1) rho=0.87 the global upper-bound noncoverage in near-serial was 80/80 even with IID and moving-block lengths 3, 6 or 12. NOTE: bound noncoverage is **not** the same event as actual false controller elimination; both are reported separately.
- In artificial flat-null serial scenario all 5 candidates are truly Pareto-optimal; no false-removal guarantee and capacity B=3 can be met simultaneously. Max-T shared moving-block removed none in 80 replicates but retained 5/5 (100% capacity overflow), and zero/80 does not imply zero true risk.
- On three historic original R16 C1/A1 TRAIN sources, each arm 12,600 verified observations but each controller had **10–210 / 18–210 variable blocks** and as few as **5 calendar days**, making IID assumptions unverified. These are seen TRAIN data only.
- **NO-GO:** No proven source-wide confidence coverage guarantee; no truly independent TEST, no confirmed equal total compute/hard native memory cap, no R19 prospective new30 run and no retroactive replacement of `seed1001/C1_F1_A1` missing execution Git SHA.
