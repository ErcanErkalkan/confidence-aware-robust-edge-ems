# CRMT R9 — Eşit kapasite F0/F1 TRAIN politikası ve G2 teknik taslağı

**23 Ekim 2026 · Statü: DRAFT / YÖNTEM PROTOTİPİ / ÖN-KAYIT DEĞİL / TEST YAPILMADI / NO-GO**

## 23 Ekim 2026 tarihsel TRAIN kaynak ve preflight güncellemesi

**Yeni doğrulama (ön-kayıt değildir):** Ayrı Drive paketlerinde eksik sanılan `candidate_metrics.csv`, `ledger.csv`, `optimizer_front.csv` ve `run_summary.json` orijinal 5-tohum TRAIN ağacında **40/40 koşul için bulundu**; [160 dosyalık kaynak envanteri ve 20 eşit F0/F1 ledger denetimi](R9_HISTORICAL_TRAIN_SOURCE_AUDIT_20261023.md) GitHub `main` üzerinde belgelendi. **20/20 çift** aynı 12.600 benzersiz controller–block olayına sahiptir. Bir gerçek örnek çiftte dört bilimsel amaçta 12.600/12.600 eşleşme bulundu; bu tek örnek sonucu tüm 20 çift için genellememek gerekir.

Makineyle tekrarlanabilir, veri değiştirmeyen SHA ve semantik denetim aracı: [`r9_train_artifact_preflight.py`](../tools/r9_equal_capacity_20261023/r9_train_artifact_preflight.py) ve [sentetik regresyon testleri](../tests/test_r9_train_artifact_preflight.py). Bu kod, indirilecek tüm 40 hücrenin `run_summary.json` SHA-256 kayıtlarını, risk/faktör eşlemelerini, TRAIN-etiketli 12.600 metriği, arşiv adaylarını ve F kollarının bilimsel metrik eşitliğini **ancak gerçekten yürütüldüğünde** doğrulayacaktır. Bugünkü taramada bütün 160 ham dosyanın SHA-256 geri okuması yapılmadı; `G2` hâlâ tam kanıt kapanışı değil.

Doğrulama komutu (Drive'dan alınan özgün TRAIN dizini yerel olarak aynı alt klasörlerle kurulduğunda):

```bash
python tools/r9_equal_capacity_20261023/r9_train_artifact_preflight.py \
  --root /path/to/TRAIN \
  --output-json ./r9_historical_train_preflight.json
pytest -q tests/test_r9_train_artifact_preflight.py
```

**Bilimsel kapı değişmez:** Birincil hipotez, nihai B/K/backfill onayı, bağımsız TEST kaynağı ve ön-kayıt halen **NO-GO**. Tarihsel TRAIN uygunluğu gelecekteki TEST'e geçme izni vermez.

## Bilimsel gerekçe

Bu belge *tek CRMT projesinin* R9 aşamasına aittir. Önceki R1–R8 deneyleri dondurulmuştur. R6'nın 151.040 kaydı tarihsel VALIDATION'dır. R7'de 20 F0/F1 K20 çiftinin **tamamı aynı sıralı adaylardan** oluşmuştur. R8'de F1 çok daha büyük arşive sahipken daha yüksek recall göstermiştir; bu, eşit kapasitede F1 üstünlüğü değildir. R7/R8'nin C0→λ0; C1→λ0,5 raporlama düzeltmesi önceki kayıtlardan ayrı erratum ile yapılmıştır.

## Uygulanan prototip ve sınırları

Kod: `tools/r9_equal_capacity_20261023/r9_capacity.py`; sentetik regresyon: `tests/test_r9_capacity_policy.py`. Mevcut `src/crmt_edge_ems/study.py`, eski K20, `archive.py`, orijinal deney arşivleri ve 30-seed release değişmez.

1. **TRAIN zorunlu:** Girdi `source_role=TRAIN` olarak bildirilmelidir; VALIDATION, TEST veya fazladan alanlar reddedilir. Bu metinsel etiket gerçek maruziyetin bağımsız kanıtı **değildir**. Kullanıcı ayrıca ham veri/split/commit/seed kayıtlarını bağımsız doğrulamalıdır.
2. **Dört hedef:** Her adayda dört sonlu, minimize edilen TRAIN amaç değeri gerekir. Risk ayarı ve C/A hücresi dış manifestte tanımlanmalıdır; riskleri/ölçekleri farklı hücrelerde aynı kıyaslamaya koymayın.
3. **TRAIN referansıyla sabit sıra:** Ortak TRAIN havuzundaki her amaç için min–max; sabit hedef 1e-12 veya daha az aralığa sahipse 0; sıra `(normalized Linf, normalized L1, lexical candidate_id)`; TEST/VAL sonucu kullanılmaz. Bu TRAIN referansı deneysel K20 kuralı olup eski tarihsel K20'nin aynı formülü kullanmış olduğunu iddia etmez.
4. **Eşit kullanılan hesaplama:** F0/F1 olay listelerinde tam aynı `(candidate_id, block_id)` çiftlerinin birer kez bulunması, aynı `expected_evaluations` sayısına ulaşması zorunludur. Aynı koşulda F yalnız arşiv son işlemine ait olduğundan *paylaşılan TRAIN değerlendirme izi* doğal bir karşılaştırmadır. CPU süresi, bootstrap maliyeti ve duvar zamanı ayrıca kaydedilmelidir; controller–block maliyeti eşitliği bunların eşitliği değildir.
5. **Ortak bellek üst sınırı B, nihai K:** F0/F1 kendi doğal arşiv üyelerini yukarıdaki TRAIN sırasıyla en çok `B` üyeye budar. Doğal arşiv `B`'den küçükse boş yerleri **aynı TRAIN havuzunda arşiv dışı adaylardan**, aynı sıralamayla doldurur. Çıktı her iki tarafta tam `B` benzersiz aday içeren **yeni etkin bellek**; K≤B ilk K adayı ayrı listelenir. `backfill_ids`, `backfill_count` ve `pruned_native_count` tutulur.
6. **Yorum sınırı:** F0 için eklenen adaylar artık tarihsel *özgün* F0 arşivinin üyesi değildir. Deney, *bounded TRAIN membership + common deterministic backfill* politika bileşiminin farkını tanımlar; doğal arşiv algoritmalarının kendiliğinden eşit 20 üye ürettiğini iddia etmez. Eski TRAIN ile ancak açıkça `historical exploratory reprocessing` olarak yorumlanır.
7. **Kapı:** Modül TEST verisine erişmez, TEST değerlendirme kodu içermez, beş tohumun yirmi faktöriyel hücresini 20 bağımsız örnek saymaz; veri yaşını/kaynağını tek başına doğrulayamaz. Sonuç etiketi `OFFLINE_DRAFT_ONLY_NOT_PREREGISTERED_NOT_INDEPENDENT_TEST` olarak zorunludur.

## Henüz onaylanmamış tasarım seçimleri

- `B=20`, `K=20` **önerilen ön çalışma senaryosudur; dondurulmuş hiperparametre değildir**. `B=32`, `K=20` sadece aday duyarlılık koşuludur. Gerçek nihai B/K araştırmacı onayıyla TEST'e bakılmadan kayda alınmalıdır.
- F0 doğal arşivinde 15 üyeli tarihsel hücre gözlendiği için 20 nihai aday zorlamanın backfill etkisi özellikle raporlanmalıdır. B değişirse politika etkisi değişebilir.
- K20 listesinden **tek nihai kontrolcüyü** seçme kuralı, normalizasyon ve önceden onaylanan `U_TEST` ağırlıkları/safety veto eşikleri bu prototipte yoktur. Bu bilinçli bilimsel engeldir; sayısal kazanç veya p değeri raporlanamaz.
- Birincil bilimsel hipotez hâlâ karara bağlanmadı: önceki Gate3 `C1_A1−C0_A0` 4D HV mi, R9 F0/F1 son kontrolcü utility farkı mı? İkisi *aynı birincil* olamaz. Hiyerarşi, çoğulluk ve bağımsız örnekleme birimi önceden onaylanmalı.
- `C0→λ=0`, `C1→λ=0.5` mevcut arşiv CSV koşulu olarak doğrulandı. A faktörü değerlendirme bütçesi dağıtımıdır. Yeni C/A/F konfigürasyonu ayrı SHA/commit ile kilitlenmeli.

## Bilimsel kapılar

| Kapı | Teknik statü | TEST öncesi eksik |
|---|---|---|
| G0: Kaynak ve geçmiş kilitler | 19 OpenCEM ham CSV SHA/Git blob doğrulandı; tarihsel frozen commit biliniyor | Yeni R9 koşusunun commit/konfig/split/run SHA'ları |
| G1: Faktör sözlüğü | C/A raporlama erratum ayrı belgede; ana kod okunabilir | C/A/F yeni deneyde makine doğrulaması ve bağımsız onay |
| G2: Eşit bütçeli kapasite politikası | Deterministik prototip + sentetik testler **hazır** | B/K ve backfill araştırmacı onayı; gerçek TRAIN log ve sonuç testleri; kaynak freeze |
| G3: Yeni bağımsız TEST kaynağı | **BLOCKED** | Yeni kaynak/saha/zaman, lisans, ham SHA, maruziyet çakışması kontrolü |
| G4: Ön kayıt | **BLOCKED** | Tek birincil uç, α, güç, safety, net fayda eşiği, imza |
| G5: Kör TEST | **ÇALIŞTIRILMADI** | G0–G4 geçip verinin tek seferlik açılması |
| G6: Yayın kararı | **NO-GO** | Karşılaştırma sonuçları ve bütünlük/şeffaflık denetimleri |

## Çalıştırma (sentetik örnek)

```bash
python tools/r9_equal_capacity_20261023/r9_capacity.py \
  --input-json tools/r9_equal_capacity_20261023/example_synthetic_pair.json \
  --output-json r9_draft_synthetic_result.json
pytest -q tests/test_r9_capacity_policy.py
```

Çıktıda giriş JSON SHA-256 kimliği, ortak TRAIN değerlendirme olay kümesi SHA-256 kimliği, her koşulun doğal arşiv sayısı, budananlar, backfill ve K sırası bulunur. `example_synthetic_pair.json` 8 uydurma adaylıdır, **OpenCEM deney sonucu değildir**.

## Kaynak bağlantıları

- Tek Google Drive proje kökü: https://drive.google.com/drive/folders/1g8afkrJCfF4fFSNxS1kJo9aQISGOlBne
- Dondurulmuş eski yürütme commit'i: `be5756321617087ca421a639d60a99513f29d889`
- Güncel `main` kodu: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems
- Tarihsel R7/R8 raporlama erratum: https://drive.google.com/file/d/11SEgPZeU1Y3k7VzBM8kL1anAi8RDFw-Q/view
- 22 Ekim taslak: `R9_DETAILED_PREREG_DRAFT_20261022.md` (önceki belge olduğu gibi korunur).

**Sonuç:** G2 politika prototipi, testler ve denetim alanları hazırlanmıştır; gerçek eşit bütçeli R9 çalışma çıktısı veya bağımsız TEST üretilmemiştir.
