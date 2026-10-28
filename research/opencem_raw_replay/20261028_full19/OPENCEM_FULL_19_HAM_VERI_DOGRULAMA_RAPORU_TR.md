# CRMT — OpenCEM 19/19 ham kaynaktan replay ölçüm doğrulaması

**Tarih:** 28 Ekim 2026  
**Kanıt sınıfı:** Historik, önceden kullanılmış ölçümlerin mühendislik veri bütünlüğü kontrolü. **Yeni bağımsız TEST değildir.**  
**İncelenen özgün kaynak:** `OpenCEM-platform/opencem-dataset` commit `5884d253a5267fb240b7a8df6fa9e4d49a905167`.  
**Temel donmuş referans:** `CRMT_EAAI_EXACT_BIN_LINEAGE_20261020.zip`, SHA-256 `bc8809c811c8538bde363dccd83f1096a01eb95e41daae3205bdbee1ace3be99`.

## Gerçekten yapılan kontrol

1. Google Drive'dan özgün 19 CSV bölümünün tamamı okundu ve daha önce sabitlenmiş SHA-256 değerleriyle doğrulandı. İki Temmuz kaynağında daha önce kullanılan 406 bloktan birine eşlenmiş satır yoktur; fakat kaynak bütünlüğü doğrulandı.
2. Her bölümde tekrarlanan `(read_ts, inverter)` kayıtları için faz/pv kanalları ortalama alınarak tarihsel dönüşüm semantiği bağımsız bir Python uygulamasında tekrarlandı. Ölçümler iki dakikalık UTC binlerine alındı; yerel gün sınırı Asia/Shanghai (UTC+8) olarak uygulandı. Ham ölçümden `load_kw`, `pv_kw`, `base_kw`, kanal gözlem sayıları ve özgün zaman damgası sayısı yeniden hesaplandı.
3. Donmuş satır haritasındaki `(dosya, satır numarası, timestamp, inverter, bin)` ilişkileri, sınır ve kanal varlığı kontrolleriyle CSV'nin gerçek satırlarına geri bağlandı.
4. Tek büyük yürütme süresi sınırını aştığı için kanıt iki **örtüşen** ve birbirinden bağımsız bitirilen kapsamda oluşturuldu: 2025 kaynakları (12 kaynak) ve Aralık/2026 kaynakları (8 kaynak). Ortak dosya 2025-12-b.csv'dir. Ortak 21.596 bin iki çalışmada birebir yeniden hesaplandı ve değerleri karşılaştırıldı; tekrar sayılmadı.
5. Her iki kapsamın günlük/ölçüm sonuçlarının birleşimi, özgün 406 blokluk manifest ve 292.256 donmuş ölçüm kaydıyla birebir sayım ve değer karşılaştırmasına tabi tutuldu.

## Tam kapsam sonucu

| Kontrol | Sonuç |
|---|---:|
| SHA-256 doğrulanan ham CSV | **19/19** |
| Okunan özgün satır | **4.021.635** |
| Ham satıra geri bağlanan eşleme | **3.853.508** |
| Karşılaştırılan iki dakikalık ölçüm kaydı | **292.256 / 292.256** |
| Karşılaştırılan tarihsel blok | **406 / 406** |
| Kesintisiz 720 kayıtlı tam gün | **381** |
| Kısmi gün, tam-gün olarak reddedilen | **25** |
| Kesişim kaydı | **21.596**, uyuşmazlık **0** |
| Kaynak-satır/bin eşleme hatası | **0** |
| Yük/PV/net güç farkının maksimum mutlak değeri | **4,44×10⁻¹⁶** |

Tarihsel ayrımlar: TRAIN 210 blok / 195 tam gün; VALIDATION 118 / 112; daha önce görünür internal TEST 78 / 74. Bu TEST ayrımı **yeni ya da kör bağımsız değerlendirme değildir**, yalnız eski blokların ham ölçüm bütünlüğü denetlenmiştir.

## Önemli kaynak erişim kaydının düzeltilmesi

Önceki `SCOPE3_SOURCE_ACCESS_BLOCKER.json` belgesindeki `2025-09-b.csv` 404 açıklaması geçerli bir veri erişim engeli değildi. İndirmenin ilk denemesinde dosya kimliğinin son karakteri eksik kullanılmıştı; doğru, tam dosya kimliği ile dosya başarıyla indirildi, sabit SHA-256 doğrulandı ve veri yeniden hesaplandı. Önceki kanıt belgesi değiştirilmiyor; yeni doğrulama bu eski yorumu **düzeltir**.

## İddia sınırları

- Bu işlem orijinal kontrolcü komut ve SOC tensorlerinin byte/eşdeğer yürütme kimliğini **kanıtlamaz**. Metrik hesabı için özgün yürütme izleri hâlâ eksiktir.
- 381 tam gün, sadece tarihsel dönemin donmuş ölçüm/replay uygunluğunu gösterir; bağımsız TEST, gerçek batarya fiziksel güvenliği, R19 prospektif deney veya veri sağlayıcı yetkilendirmesi değildir.
- Eski veri üzerinde dönüşüm kontrollerinin başarılı olması, CAL-v2 güven garantisini ya da F1'in bilimsel üstünlüğünü kanıtlamaz.
- Orijinal dosyaların hiçbiri değiştirilmedi; yeni rapor/CSV/komut dosyaları sürümlü ek çıktı olarak saklandı.

**Karar:** `A17` ham kaynak-replay değer/lineage mühendislik alt kapsamı **tamamlandı**. A17'nin daha geniş özgün controller input tensor ve bağımsız geçerlilik boyutları açık kalır; genel proje ve makale durumu **SCIENTIFIC NO_GO**.