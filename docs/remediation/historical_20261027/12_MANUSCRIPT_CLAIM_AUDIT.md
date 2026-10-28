# v13 yayın iddiası denetimi

Durum: PARTIAL. v12 PDF/ZIP aynen korundu. Ayrı v13 orijinal LaTeX kaynağından üretildi; abstract, introduction/related-work ifadeleri, methodology confidence tanımı, results kalite etiketi, discussion, limitations, reproducibility ve conclusion değiştirildi. Yanlış etiket taşıyan optimizer-quality grafikler özgün CSV sayılarıyla yeniden çizildi; iki eski vektör şeması v13'te açık evidence-layer metin şemasıyla değiştirildi. Sayısal tarihsel tablolar korunur; yeni operasyonel sonuç yazılmadı.

C07 ölçüm adı: **Validation-evaluated approximation-set quality of TRAIN-generated fronts.** Eşit TRAIN bütçesi eşit toplam maliyet diye sunulmuyor. C03 için30/30 objective eşitliği yeni CSV kontrolü, selected-controller kimlik eşitliği ise önceki rapor kapsamı olarak ayrıldı. C11 evrensel subset çıkarıldı; C12 archive95% garantisi kaldırıldı. R22/R23 koşullu, R19 taslak, R26–R30 metadata olarak sınırlandı. LFP proxy ve HIL/field/hard-real-time sınırlamaları açık.

MiKTeX pdflatex + BibTeX ile **34 sayfa** derlendi; final logda undefined citation/reference veya overfull kutu yok. Önceki tüm35 sayfa contact sheetlerde, başlık düzeni düzeltmesinden sonra final başlık ayrıca gözden geçirildi. Bu, bilimsel hakem/yazar onayı değildir. Orijinal bibliography korunmuş, her referansın yayıncı metadatası bu çalışmada bağımsız yeniden doğrulanmamıştır. Yazar beyanı/onayı uydurulmadı; taslak açıkça author-review-pending'dir. Cover letter ve bağımsız tam nicel iddia doğrulaması açık.

| İddia | v13 izin verilen kapsam | Hâlâ açık |
|---|---|---|
| C01 | Donmuş raporlardaki hedefe özgü iç TEST farkları sınırlarıyla aktarılabilir | Bu tur tüm 30-seed istatistikleri yeniden hesaplanmadı |
| C02 | Tarihsel K20 seçimi aynı; yeni B10 farklılığı tek başına fayda değil | Tarihsel TRAIN betimleyici yeniden hesaplama |
| C03 | Adaptive bir tasarım bileşeni; bağımsız operasyonel kazanım kanıtı sınırlı | Tarihsel iddia sınırı; bu tur yeni adaptive deneyi yok |
| C04 | Önceden incelenmiş dış OOD sonuçlarını hedef bazında raporla | Tarihsel OOD; yeni bağımsız TEST değil |
| C05 | Yazılım testi ve belirli ortamda süre ölçümü yalnız mühendislik kanıtıdır | Yerel regresyon; fiziksel güvenlik yok |
| C06 | lfp_cycle_loss_pct model tabanlı stres/kayıp vekilidir | Fiziksel hedef yorum sınırı |
| C07 | TRAIN ile üretilen adayların VALIDATION üzerinde ölçülen kalitesini ve eşit TRAIN simülatör bütçesini açıkça ayır | v12 C7 ve ilgili tablo/şekil kaynak üzerinden revize edilmeli |
| C08 | 160/160 dosya kanonik kökte; 20 tam çiftin bayt ve bilimsel alanları doğrulandı; strict preflight 19 geçiş ve 1 istisna | Üst dizinden kurtarma; UNRECORDED_LOCAL_SHA ve yeni TEST eksikliği sürüyor |
| C09 | Doğrulanmış paket ve üç referans modül kimliği; eski tam frozen manifestiyle farklar açık | UNRECORDED_LOCAL_SHA korunuyor; tam gelecek commit kilidi gerekli |
| C10 | Paket kaynakları loglar ortam sürümleri ve ayrı Windows türeviyle yerel tekrar üretim | 356 özgün paket + 29 Windows türevi + 34 R9 testi |
| C11 | 20 çiftin 18'inde F0 altküme; iki seed1001 hücresinde CRMT-c0089 yalnız F0'da | Tarihsel TRAIN arşiv üyeliği |
| C12 | R21'de sınır ihlali yanlış dominance ve yanlış eleme ayrı olaylar; mevcut kapsama hedefi tutmadı | Mevcut 1600 sentetik kaydın yeniden toplaması; yeni stokastik koşu değil |
| C13 | R22 günlük ortalama estimandı değiştirir; R23 pooled risk için güçlü önceden belirlenmiş varsayımlar altında koşullu prototiptir | Gerçek saha destekleri ve bağımlılık varsayımları doğrulanmadı |
| C14 | C1/A1 B=K10 doğal arşiv shortlist sadakati için yanlışlanabilir taslak | locked=false; B10 native bellek sınırı değil |
| C15 | R30 385 aday ve 7 depolama bayrağı bildiriyor; özgün sağlayıcı CSV kimliği doğrulanmadı | Lisanslı zaman serisi edinilmemiş; yalnız metadata kanıtı |


Kaynak/diff/build fişleri: `06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13/`. Doğrulanmış yeni operational TEST veya preregistration yokken MANUSCRIPT_V13_READY=PARTIAL; submission-ready değil.
