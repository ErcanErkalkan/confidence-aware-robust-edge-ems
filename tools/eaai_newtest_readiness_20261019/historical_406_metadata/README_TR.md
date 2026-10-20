# CRMT-EAAI — OpenCEM 406 tarihsel blokların gerçek zaman envanteri (2026-10-20)

## Veri kaynağı ve güven sınırları

Doğrudan Drive'daki `06_OPENCEM_RECOVERY/VERIFICATION_REPORTS/QA_20261009_001/canonical_block_manifest.csv` dosyasından hesaplanmıştır. Orijinal dosyanın SHA-256 değeri **3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1** ve `block_lock.json` içindeki 406 satır, 210 TRAIN + 118 VALIDATION + 78 historical INTERNAL_TEST ile eşleşmektedir. Kaynak commit `5884d253a5267fb240b7a8df6fa9e4d49a905167`.

- `out/HISTORICAL_406_WINDOWS_METADATA_ONLY.csv`: 406 gerçek block_id, split, inverter kimliği, UTC başlangıç, UTC bitiş (son ölçülen tick + 2 dakika; half-open interval), n_ticks ve kaynak kimliği.
- `out/HISTORICAL_406_AUDIT_STATUS.json`: özet, hesaplanan CSV SHA, eksikler, tam blok aralıkları.
- `audit_historical_406.py`: aynı frozen manifestten, **yalnızca yeni çıktı klasörüne** yeniden üretim; yanlış kaynak SHA, sayı, tarih, overlap ve mevcut hedef dosyalarda hata ile durur.

Önemli: Canonical blok dosyasında ham veri dosyasının her blok için SHA-256 değeri **yoktur**. Bu nedenle CSV özellikle `raw_sha256` kolonu taşımaz; `pretest_readiness.py` girdisi olarak kullanılamaz ve TEST uygunluk denetiminden geçmesi amaçlanmamıştır. Daha önceki OPSD dış maruziyetinin tam zaman envanteri de burada yoktur. Bu eksikleri sahte SHA veya varsayılan tarihlerle doldurmayınız.

## Doğrulama / kullanım

Aşağıdaki kod yalnızca kopya manifest ve yeni hedef klasör üzerinden çalışır:

```powershell
$Py = 'E:\CRMT_EAAI_WORK\.venv_qa_314\Scripts\python.exe'
$Tool = 'E:\CRMT_EAAI_WORK\HISTORICAL_406_AUDIT_TOOLS\audit_historical_406.py'
$Original = 'E:\Google Drive\My Drive\01_ACTIVE_RESEARCH\MICROGRID_EMS_RESEARCH\02_CONFIDENCE_AWARE_ROBUST_EDGE_EMS\09_EAAI_REVISION_2026_10_08\06_OPENCEM_RECOVERY\VERIFICATION_REPORTS\QA_20261009_001\canonical_block_manifest.csv'
$Output = 'E:\CRMT_EAAI_WORK\HISTORICAL_406_META_CHECK_NEW'
& $Py $Tool --canonical $Original --output-dir $Output
if ($LASTEXITCODE -ne 0) { throw 'Historical 406 metadata audit FAIL' }
```

Üretilmiş CSV SHA-256: `85c295e39f43f0a64d06f720f7486255601f0ffa2486b56661bb98781da37f18` (aynı kod ve kaynakla, LF CSV satır sonları korunursa).

**Yeni TEST durumu: BLOCKED.** Gelecekte gerçekten yeni ham veriler / maruziyet kayıtları ve fiziksel hedef karşılaştırma koşulları dondurulduktan sonra ayrı bir onay gerekir. Burada hiçbir kontrolcü simülasyonu çalıştırılmamış, TEST sonucu hesaplanmamış, önceden kilitlenen dosya değiştirilmemiştir.
