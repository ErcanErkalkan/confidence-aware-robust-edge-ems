# CRMT / EAAI — Gate 2, 30 Tohum İçin Kilitli TRAIN Adayları ve Geçmiş VAL Kapsamı

**Tarih:** 9 Ekim 2026  
**Kanıt sınıfı:** Yalnızca geçmiş TRAIN ve geçmiş VALIDATION arşivi yeniden denetimi. **Yeni optimizasyon / replay / TEST sonucu DEĞİLDİR.**  
**Kaynak:** `ErcanErkalkan/confidence-aware-robust-edge-ems`, dondurulmuş OpenCEM manifest SHA-256 `3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1`.

## Doğrulanmış somut çıktı

- 30 tohum (1001–1030) × 5 yöntem (CRMT/SOBOL/NSGAII/MOPSO/MODE) = **150/150 kaynak TRAIN çalışması**, her biri özgün `run_summary.json`, 12.600 değerlendirmelik ledger ve dosya SHA kilidi doğrulanarak okundu.
- **150 adet tam K20 TRAIN-only aday listesi** üretildi; **3.000** aday slotu ve **354.000** nominal VALIDATION controller-block değerlendirme gereği.
- Önceki 5 tohumluk Gate 2 pilotundaki **25 aday CSV dosyasının tamamı bayt düzeyinde özdeş**; önceki 500 satırlık VAL-cache raporunun tamamı yeni raporun ilk 500 satırıyla özdeş.
- **23 kaynak Actions ZIP arşivi** (13 TRAIN, 10 tarihsel VAL) SHA-256, bayt boyu ve içerik sayısı bakımından daha önce kaydedilmiş 43-arşiv yedek manifestiyle eşleşti; ZIP CRC 23/23 başarılı.
- Tam 30 tohumdaki eski VALIDATION skorları ve blok kayıtlarının SHA-256 ve 118-blok kapsamına göre **2.193/3.000** adayın geçmiş sonuçları mevcut, **807/3.000** adayın kullanılabilir kesin eşleşmesi yok. Bu 807'nin 2'sinde eski TRAIN-front aynı fiziksel parametreleri birden çok `front_id` ile gösteriyor: bu belirsizlik **cache'e yazılmadı, tekrar değerlendirmeye ayrıldı**.
- Geçmiş arşivdeki eksikliği kapatmanın **teorik** simülasyon gereği 807 × 118 = **95.226 controller-block**. Gerçekten eşit ve tek ortamlı temiz tekrar için **3.000 × 118 = 354.000 controller-block** önerilir. Hiçbiri burada çalıştırılmadı.
- **17/17** yerel birim/integrite testi başarılı. Ancak end-to-end OpenCEM simülatör testi değildir.

## Yöntem bazında tarihi kayıt kapsamı

| Yöntem | K20 aday slotu | 118-blok eşleşmiş | Yeni replay gerektiren veya belirsiz |
|---|---:|---:|---:|
| CRMT | 600 | 599 | 1 |
| SOBOL | 600 | 600 | 0 |
| NSGAII | 600 | 229 | 371 |
| MOPSO | 600 | 600 | 0 |
| MODE | 600 | 165 | 435 |
| **TOPLAM** | **3000** | **2193** | **807** |

Bu tablo **yöntem başarısını karşılaştırmaz**. Yalnızca eski kayıtların hangi adayları içerdiğini gösterir.

## Paketin yapısı

- `prepare_30seed.py` — 13 dondurulmuş TRAIN Actions ZIP'inden 150 SHA kilitli aday listesini tekrar üretir.
- `build_replay_worklist.py` — eski VAL-cache raporuyla yalnızca aday kimliklerini eşleştirir; eksik 807 adayın parametreleriyle iş listesi oluşturur.
- `gate1/src/` — özgün Gate1 eşit kota seçici kodu (yan paket, orijinal CRMT çalışma kodu değil).
- `cache_code/` — eski Gate2 cache denetiminin 30-tohumluk genişletilmiş sürümü; belirsiz eşleşmeleri **fail-conservative** olarak işaretler.
- `tools/preflight_30seeds.py` — kaynak lock, 150 liste, 19 gerçek ham CSV, doğrulama CSV, kanonik *üretilmiş* blok kilidi, 10 kritik orijinal kod dosyası/commit denetimlerini yapar.
- `tools/p0_gate2_run_30seeds.py` — yalnızca orijinal simülatör modülleri ile gerçek VALIDATION replay çalıştırıcısı; bu pakette **çalıştırılmamıştır**.
- `RUN_GATE2_FULL_30SEED_SAFE.ps1` — Windows ön kontrol + ancak `-ExecuteAll` verilirse gerçek replay; önceki deney dizinini silmez.
- `outputs/locked_30seed/shortlists/seed1001/...seed1030/` — 150 aday CSV+JSON kilidi.
- `outputs/historical_cache_30seed/` — tüm 3.000 aday için tarihsel cache durumu.
- `outputs/replay_worklist/` — 807-aday iş listesi ve 150 tohum-yöntem kotası.
- `SOURCE_ARTIFACT_LOCK_23_TRAIN_VAL.json`, `MANIFEST_SHA256.json`, `tests/` — kaynak ve paket bütünlüğü.

## Yalnızca ön kontrol — Windows PowerShell

Aşağıdaki yollar **örnektir**, gerçek Windows dizinlerinize göre düzenleyin. Orijinal repo `main` üzerinde hiçbir değişiklik yapmayın. Bu ZIP kendi kendine OpenCEM ham verisini içermez.

```powershell
$Stage = 'E:\CRMT_EAAI\GATE2_30SEED_2026_10_09'
$Repo = 'E:\CRMT_EAAI\original_source_frozen'
$Raw = 'G:\My Drive\CRMT_OPEN_CEM_RAW_BACKUP'
$Verification = 'E:\CRMT_EAAI\data\opencem_download_verification.csv'
$BlockLock = 'E:\CRMT_EAAI\canonical\block_lock.json'
$Output = 'E:\CRMT_EAAI\gate2_30_seed_RUN001'
Set-Location $Stage
python -m pytest .\tests -q
.\RUN_GATE2_FULL_30SEED_SAFE.ps1 `
  -RepoRoot $Repo `
  -StageRoot $Stage `
  -RawRoot $Raw `
  -VerificationCsv $Verification `
  -BlockLockJson $BlockLock `
  -OutputRoot $Output
```

Çıktı `GATE2_PREFLIGHT_30SEED.json` dosyasında `READY_TO_RUN_GATE2_30SEED` **veya** `BLOCKED_DO_NOT_RUN` olur. 19 ham CSV'nin tamamı güncel baytlarla doğrulanmadıysa işlem **durdurulur**. Başarılı olduktan sonra yeni bir çıktı klasörü adı belirleyip aynı komuta **açıkça** `-ExecuteAll` eklenebilir; bu 30 tohum × 5 yöntem × 20 aday × 118 blokluk çalışmayı yürütür.

**Not:** `opencem_split_lock_v1.json` dosyası **kanonik türetilmiş `block_lock.json` dosyasının yerine geçmez**. Eski internal-test / OPSD sonuçları yeni kör test değildir. Gerçek OpenCEM ham veri dosyaları ve orijinal Git checkout'u bu ZIP'e dahil edilmemiştir.

## Zorunlu araştırma sınırı

1. Kaydedilen tüm sonuçlar tarihsel/keşifsel denetimdir; yeni yöntem üstünlüğü/HV/IGD+ istatistiği iddia edilmedi.
2. 807 eksik adayın skoru tahminle doldurulmadı; iki belirsiz çift de cached olarak işaretlenmedi.
3. K20 yalnızca VAL aday sayısını eşitler; tüm optimizasyon maliyeti, TRAIN değerlendirme sayısının adaylara dağılımı ve CPU süresi eşitlenmiş değildir.
4. EAAI için önce mevcut Gate 2 VALIDATION replay, sonra Gate 3 faktöriyel gerçek simülasyon ve gerçekten yeni bağımsız test veri protokolü gereklidir.
5. Orijinal ASOC v12/GitHub `main` ve bütün geçmiş kaynaklar değiştirilmedi.
