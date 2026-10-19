# CRMT-EdgeEMS — EAAI eksik deneyleri kapatma araçları (19.10.2026)

**Statü: yeni TEST yapılmadı, güvenilirlik mekanizması katkısı henüz gösterilmedi, EAAI NO-GO.** Bu paket tüm girdileri yalnızca okur, yeni sonuçları yazmaz, frozen TRAIN/VAL/TEST kanıtlarına dokunmaz. Buradaki sentetik testler gerçek harici veri üzerinde yapılmış değerlendirme değildir.

## 1. Bağımsız yeni TEST meta ön-denetimi

`pretest_readiness.py` için üç girdiye ihtiyaç vardır:
- `--manifest`: doldurulmuş, tarihlendirilmiş yeni kaynak manifesti (şablon `PROSPECTIVE_NEW_TEST_MANIFEST_TEMPLATE.json`; başlangıç değerleri **bilerek geçmez**)
- `--proposed-windows`: yeni TEST blokları ve ham SHA-256, başlık için `REQUIRED_WINDOWS_HEADERS.csv`; `split=new_test`
- `--historical-windows`: eskiden incelenmiş TÜM 210 TRAIN + 118 VALIDATION + 78 internal TEST + daha önce kullanılmış dış/OPSD bloklarını içeren geçmiş kaynak günlüğü; `split=train|validation|internal_test|historical_external`. Tarihler UTC `[start,end)` ve kimlikler gerçek kaynak kayıtlarından türetilmeli, **uydurulmamalıdır**.
- `--expected-history-sha256`: yukarıdaki geçmiş envanterin, gelecekte test outcomes görülmeden bağımsız olarak kilitlenmiş beklenen hash değeri. Henüz sabitlenmemişse denetimi PASS gösteremezsiniz.
- `--raw-root`: dosyaların kök dizini; manifestteki her `raw_files[].path` bu köke göre göreli ve SHA-256'a tabi olmalı.

Örnek komut (gerçek dosyaları hazırladıktan sonra):

```powershell
$Py = 'E:\CRMT_EAAI_WORK\.venv_qa_314\Scripts\python.exe'
$Pkg = 'E:\CRMT_EAAI_WORK\EAAI_NEXT_GATES_20261019'
& $Py (Join-Path $Pkg 'pretest_readiness.py') `
  --manifest 'E:\CRMT_EAAI_WORK\NEW_TEST_CANDIDATE\dataset_manifest.json' `
  --proposed-windows 'E:\CRMT_EAAI_WORK\NEW_TEST_CANDIDATE\proposed_windows.csv' `
  --historical-windows 'E:\CRMT_EAAI_WORK\NEW_TEST_CANDIDATE\frozen_prior_exposure_registry.csv' `
  --raw-root 'E:\CRMT_EAAI_WORK\NEW_TEST_CANDIDATE\RAW' `
  --expected-history-sha256 '<ONCEDEN_KILITLENMIS_GERCEK_SHA256>'
```

`NEW_TEST_GATE_BLOCKED` çıktısı varsa **test başlatmayın**. PASS sonucunda `ELIGIBLE_FOR_MANUAL_REVIEW_ONLY` görünür: bu da TEST sonuçlarının incelendiği veya teste geçişin onaylandığı anlamına **gelmez**. Kontrol, meta-kanıt ve aralık temelli olduğundan kaynaklar arası eşanlamlı inverter adları, sahadaki fiziksel farklar ve bağımsız sağlayıcı yetkileri ayrıca denetlenmeli.

## 2. Confidence arşiv güvenilirliği tanısı

`archive_fidelity.py` tüm 256 adayın **aynı eşit bütçeli ortak blok referansıyla yeniden puanlandığı** bir referans tabloyu bekler. `--reference` CSV başlıkları: `candidate_id,cap_violation_pct_total,lfp_cycle_loss_pct,ramp95_kw_per_min,flip_per_day`; her aday için tam bir satır. `--f0` ve `--f1` arşivleri için `candidate_id` kolonu gerekir.

```powershell
& $Py (Join-Path $Pkg 'archive_fidelity.py') `
  --reference 'E:\CRMT_EAAI_WORK\ARCHIVE_REFERENCE\fixed_common_pool_scores.csv' `
  --f0 'E:\CRMT_EAAI_WORK\ARCHIVE_REFERENCE\F0.csv' `
  --f1 'E:\CRMT_EAAI_WORK\ARCHIVE_REFERENCE\F1.csv'
```

Eğer ortak, eşit bütçeli ve tam aday referansı **mevcut değilse**, F0/F1 için yanlış eleme, doğru saklama ve kalibrasyon rakamlarını **hesaplamayınız**. Çıktı sadece tanısaldır: cihaz üstü enerji yararı, bağımsız test veya confidence doğruluğu kanıtı değildir. Yalnız grup üyeliğinden bootstrap çıkarım üretmeyin. Eski seed1001 TRAIN auditinde F1/F0 terminal arşivleri farklı ama K20 listeleri özdeştir; bu, yeni testte F performans etkisinin ölçülemeyeceğini gösterir.

## 3. Mevcut çalışmaya dokunmama ve kaynaklar

- Dondurulmuş source: `be5756321617087ca421a639d60a99513f29d889`; OpenCEM source: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- 5-seed VALIDATION analiz manifesti: `a85ed87afdf171dbeea1c9b87e662e65aa3ffaa0b6333e2a06d05f0e7028446e`.
- F0/F1 K20 ve hedef skorları beş seedin tamamında özdeş.
- Önceki 78 internal TEST bloğu ve OPSD dış testleri *yeni blind TEST olamaz*.
- `python -m pytest tests -q -p no:cacheprovider` ile sentetik/negatif testler.
- Bu araçlar upstream veri indirip açmaz, kaynak uyarlayıcısı oluşturmaz, harici TEST'i çalıştırmaz ve performans sonuçlarını bulgulara dönüştürmez.

## Güvenlik / veri yönetimi

GitHub herkese açık; gerçek ham dosyalar, siteye özgü sır niteliğindeki ölçümler, kişisel veriler veya doğrulanmamış lisanslı veri GitHub'a konulmamalı. Drive arşivi yeni doğrulanabilir kaynak ve protokolleri taşır; imzasız yeni TEST verisini "doğrulandı" olarak işaretlemez.
