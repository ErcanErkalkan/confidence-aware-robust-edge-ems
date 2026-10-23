# CRMT R9 — Gerçek tarihsel TRAIN kaynak keşfi ve F0/F1 muhasebe denetimi

**Tarih:** 23 Ekim 2026  
**Kapsam:** Beş tohum × sekiz 2×2×2 faktöriyel koşul = 40 gerçek geçmiş TRAIN hücresi; **bağımsız yeni TEST değildir**. Bu belge daha önce "üçlü dosyalar mevcut değil" ifadesini düzeltir.

## Doğrulanmış kaynak envanteri

Özgün geçmiş Google Drive klasörü: [5-tohum TRAIN ağacı](https://drive.google.com/drive/folders/1auSnDAdA_A6XNfb5rLuwn9SJN-sdTw8S). Her tohum için C0/C1 × F0/F1 × A0/A1 kombinasyonlarının sekiz hücresinin tamamı doğrudan tarandı.

**40/40 hücrede 4/4 kaynak dosya var ve Google Drive boyutu sıfırdan büyük:** `run_summary.json`, `candidate_metrics.csv`, `ledger.csv`, `optimizer_front.csv`. Toplam **160/160** öğe. Bu ilk aşama **dosya adı, bağlantı, Drive boyutu** envanteridir; 160/160 bayt SHA eşitliği kontrolü olduğu iddia edilmez.

Beş dosyalık kalıcı adres+boyut manifesti:
- [seed1001.csv](../reproducibility/r9_historical_train_sources_20261023/seed1001.csv)
- [seed1002.csv](../reproducibility/r9_historical_train_sources_20261023/seed1002.csv)
- [seed1003.csv](../reproducibility/r9_historical_train_sources_20261023/seed1003.csv)
- [seed1004.csv](../reproducibility/r9_historical_train_sources_20261023/seed1004.csv)
- [seed1005.csv](../reproducibility/r9_historical_train_sources_20261023/seed1005.csv)

Bu CSV'ler her özgün koşul için `seed,condition,file_name,file_id,size_bytes,source_url,source_cell_folder` alanlarını saklar. Araştırmanın tek ana çalışma dalı `main`dir; tarihsel kaynaklar Drive'da kalır, kaynak büyük CSV'ler GitHub deposuna kopyalanmaz.

## Ledger'ların gerçek içerik denetimi

40 `ledger.csv` dosyasının **tam satır içerikleri** Google Drive'dan okunup yalnız `(candidate_id,block_id)` alanlarıyla, koşullar `seed,C,A` bazında F0/F1 eşleştirilerek karşılaştırıldı:

- **20/20** gerçek eşleşme için her kolda **12.600** satır ve **12.600** benzersiz `candidate_id|block_id` çifti.
- Her eşleştirmede **F0-only = 0** ve **F1-only = 0**. Gerçek değerlendirme kimlikleri tam eşit; yalnız başlık/tek sayı karşılaştırması yapılmadı.
- Toplam 40 ledger × 12.600 = **504.000 kayıt** incelendi; eşleşmiş F kollarını iki bağımsız istatistiksel tekrar olarak yorumlamayın.
- Bu kontrol, ledger'a **kaydedilmiş** controller–block çağrıları için eşitliktir. Ham CSV hash paritesi, fiziksel değerlendirmenin yeniden çalıştırılması, işlemci süresi ve bootstrap maliyeti **bu denetimin kapsamı dışında**.

Her tohumun ayrıntılı 4 çiftlik kaydı:
- [seed1001](../reproducibility/r9_historical_train_sources_20261023/seed1001_paired_ledger_audit.json)
- [seed1002](../reproducibility/r9_historical_train_sources_20261023/seed1002_paired_ledger_audit.json)
- [seed1003](../reproducibility/r9_historical_train_sources_20261023/seed1003_paired_ledger_audit.json)
- [seed1004](../reproducibility/r9_historical_train_sources_20261023/seed1004_paired_ledger_audit.json)
- [seed1005](../reproducibility/r9_historical_train_sources_20261023/seed1005_paired_ledger_audit.json)

**Örnek derin kontrol:** `seed1001/C1_A0` F0/F1 `candidate_metrics.csv` dosyalarında 12.600 benzersiz TRAIN satırı bulunmuştur; ortak değerlendirme anahtarlarında dört fiziksel amaç (`cap_violation_pct_total`, `lfp_cycle_loss_pct`, `ramp95_kw_per_min`, `flip_per_day`) 1e-12 toleransta **12.600/12.600 eşleşmektedir**. Bunun öteki 19 eşleşme için de kesinleştiği ileri sürülmez.

## Bilimsel sınırlama ve R9 G2 yol haritası

1. Mevcut dört dosyanın geri kazanılması **R9 bağımsız TEST** verisi elde edildiği anlamına gelmez. Hepsi geçmiş TRAIN'dir.
2. Kaynak `run_summary.json` dosyalarında commit, C/A/F, risk, durum, 12.600 bütçe ve üç CSV için SHA-256 bulunur. **Kullanımdan önce her 40 hücrede dosya SHA-256 hash'ini bu kayıtla eşleştirmek gerekir**; yukarıdaki metadata envanteri bunu yapmış sayılmaz.
3. Yeni G2 backfill politikası, tarihsel öz F0/F1 arşiv algoritmalarıyla **aynı şey değildir**. `B=20, K=20` ve `B=32, K=20` yalnız onaylanmamış duyarlılık adaylarıdır. G2 hesaplama eşitliği gözlenmiş olsa da arşiv kapasitesi/nihai karar hipotezi onaylanmamıştır.
4. Yeniden işleme yalnız **historical TRAIN exploratory** başlığı altında yürütülebilir. Orijinal 40 arşiv/K20 ve R6–R8 validasyon sonuçları değiştirilmez.
5. Kullanılacak daha yeni bağımsız TEST kaynağı, sızıntı/uygulanabilirlik kapısı, risk referansı ve ön kayıtlı birincil sonlanım olmadan **R9-G5 NO-GO** devam eder.

**Kritik düzeltme:** Önceki pakette dört kaynak dosyanın bulunmadığı sanılıyordu. Gerçekte eski `10_GATE3_PILOT_TRAIN_RESULTS_2026_10_11` klasöründeki pilot tek tohumun yanında, daha kapsamlı beş-tohum TRAIN ağacında orijinaller mevcuttur. Bunları kayıp ilan etme veya deney sonuçlarını yeniden üretme zorunluluğu yoktur. Ancak yalnız dosyaların bulunmuş olması 40 hücrenin bilimsel SHA kilidinin doğrulandığı anlamına gelmez.
