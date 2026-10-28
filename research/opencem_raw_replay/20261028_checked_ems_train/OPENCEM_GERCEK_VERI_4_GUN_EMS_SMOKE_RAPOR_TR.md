# CRMT — 4 gün doğrulanmış OpenCEM TRAIN girdisiyle gerçek EMS simülasyonu

**Kanıt:** Önceki 19 kaynak/406 blok tam ham veri yeniden hesaplamasının `FULL_292256_RECONSTRUCTED_VALUES.csv` dosyasındaki **ham değerlerden yeniden oluşturulan** dört kesintisiz 720 tick günlük profil; kaynak dosya SHA-256 `145caf611ce23d3527162f27012d4af15126f9979bd4a1e86a72f0ab98f2fa2d`.

## Yöntem ve durum

- Tarihsel TRAIN grubundaki iki inverter için 2025-08-02 ve 2025-08-31 günleri önceden sabit seçildi; seçilmemiş veya yeni bağımsız TEST verisi kullanılmadı.
- F0 tarihsel aday arşivindeki kimlik sırasına göre ilk aday (`CRMT-c0016`) alındı; yeni optimizasyon, aday taraması veya R19 yapılmadı.
- Gerçek `build_tuned_controller` + `simulate_checked` + `SafetyLimits.from_site` + `compute_metrics_v2` zinciri çalıştırıldı. Güvenlik parametreleri senaryo **model varsayımıdır**, fiziksel donanım sertifikası değildir. Process-level timeout etkin değildi.
- **4/4 koşu başarılı, toplam 2.880 tick** simüle edildi; başarılı simülasyon sayısı gerçek saha başarısı anlamına gelmez.
- `lfp_cycle_loss_pct` ve `efcrf` tarihsel metrik yolundan farklı bulundu; kaynak eski koşuların orijinal SOC tensorleri olmadığından bilimsel geriye dönük kesin oran üretmez.

## Yeni kritik bulgu: kayan nokta hassasiyetinden kaynaklanan sahte ihlal kayıtları

Güvenlik veto sözleşmesi kapasite kontrolünde `+1e-12 kW` tolerans kullanırken eski `jer_microgrid.metrics.compute_metrics` katı `grid > cap` hesabını kullanır. Yalnız hassasiyet farkından dolayı **7 tick**, ikisinde ihlal oranı sıfırdan büyük olan iki blokta, ihlal olarak sayıldı. Bu 7 olayda kapasite aşımı **en çok 1,11e-16 kW** idi. Güvenlikteki `1e-12 kW` toleransına göre bu dört günde **sıfır aşım** vardı. `metrics_v2` eski fonksiyondan aynı kapasite ölçütünü devralmaktadır.

**Bu hata tarihsel amaç dosyalarına sessiz düzeltme uygulanmasını haklı çıkarmaz.** Gelecek bir metrik sürümünde kapasite karşılaştırma toleransı açıkça sürümlenmeli ve eski–yeni sonuçlara etkisi ölçülmelidir.

## Sınırlar

Bu çalışma 19 kaynaklık ham->replay veri bütünlüğünü aşarak gerçek EMS motorunda sadece dört **tarihsel TRAIN** gününün sentetik fiziksel model/senaryo simülasyonudur. Yeni bağımsız TEST, prospektif R19, saha güvenliği, HIL, gerçek şebeke sözleşmesi veya fiziksel batarya ömrü doğrulaması değildir. Tarihsel özgün kontrolcü izlerinin geri kazanıldığı iddia edilmez. Genel karar **SCIENTIFIC NO_GO**.