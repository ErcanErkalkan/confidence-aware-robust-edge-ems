# CRMT Adım 2 — 3/19 kaynak ile OpenCEM ölçüm yeniden hesaplama eki

Tarih: 28 Ekim 2026. **İlgili tarihsel veriler yeniden hesaplanmıştır; bilimsel NO_GO değişmemiştir.**

## Ölçülen kapsam

- Kapsama eklenen özgün üçüncü ham CSV: `2025-09-a.csv` (SHA256 geçişi); diğer iki kaynak `2025-08-a.csv` ve `2025-08-b.csv`.
- Kaynak sayısı: **3/19**; tarihsel dondurulmuş replay blokları: **36**; iki dakikalık kabul edilen bin sayısı: **25910**.
- Kesintisiz 720 kayıtlık günler: **32**. Tam olmayanlar: **4**. Tam günün şartı 720 benzersiz, artan ve 2 dakika aralıklı timestamp.
- Üç kaynaktan geri bağlanan gerçek ham satırlar: **57112**; bu kapsamda bozuk row-ID, timestamp, inverter, bin veya load/PV kanal bayrağı yok.
- `load_kw` maksimum mutlak fark **2.220446049250313e-16**; `pv_kw` **4.440892098500626e-16**; `base_kw` **4.440892098500626e-16**. Test toleransı `atol=1e-10, rtol=0`; tüm eşleşmeler geçti.
- Önceki 2/19 kapsamındaki 4.316 adet kabul edilen binin tümü 3/19 sonucu içinde korundu, 3 temel fiziksel kanal için eski-yeni yeniden hesaplama farkı tam olarak sıfır.

## Açık erişim sınırlaması

`2025-09-b.csv` dosyası bağlı Drive'ın listeleme arayüzünde bulunmasına karşın, dosyanın ham içeriğini alma isteği **404 File not found** döndürdü. İlk materialization başarısızlığı ve bir doğrudan provider fetch denemesi kaydedildi. Bu dosyanın içeriği **okunmuş veya doğrulanmış sayılmadı**. Eksik dosyanın toplam 19 kaynak için 19/19 değer doğrulama yapıldığı iddiasına dönüştürülmesi yasaktır.

## İddia sınırları

- `PASS`: yalnız üç kaynak dosyasının ham ölçüm kanal değerleriyle, bunlardan bütünüyle beslenen 36 tarihsel blok için 2 dakikalık replay değerlerinin ve satır bağlantılarının bağımsız yeniden hesaplanması.
- `NOT_DONE`: kalan 16 CSV'nin ölçüm değerlerinden gerçek tekrar üretim; 381 tarihsel tam-gün adayının tamamı; özgün controller input tensor kimliği; gerçek EMS kontrolcü yeniden koşusu; bağımsız yeni TEST; fiziksel HIL/saha.
- Tarihsel TRAIN/VAL/TEST split'leri değiştirilmedi ve tarihsel veriler yeni independent TEST olarak kullanılmadı.

Bu ek, önceki iki kaynaklı paketin üzerine yazmaz. Her ikisi ayrı kanıt sürümü olarak saklanır.
