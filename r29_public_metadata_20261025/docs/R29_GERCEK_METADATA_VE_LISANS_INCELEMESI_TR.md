# CRMT R29 — Pecan Street kamu metadata kohort taraması ve Brazil STAR lisansının kayıt-özel doğrulanması

**Tarih:** 25 Ekim 2026  
**Bilimsel kapsam:** Kamuya açık metadata ve kayıt lisansı. Orijinal Pecan CSV baytları, lisanslı hane zaman serileri, Brazil STAR ZIP verileri ve yeni bağımsız TEST **elde edilmedi / işlenmedi**.  
**Sürüm:** R29-v1; R19 B=K=10, C1/A1 hipotezi ve eski kod değiştirilmedi.

## 1. Kaynak ve sınırlamalar

- Pecan Street kamu tablosu: https://dataport.pecanstreet.org/metatable
- Kamu CSV bağlantısı: https://dataport.pecanstreet.org/static/metadata.csv
- API / metin çıkarma: Tavily advanced text. CSV 624 bin karakterlik normalize edilmiş **metin** olarak döndü, satır sonları boşlukla değiştirilmiş ve `_` karakterleri kaçışlıydı. Özgün CSV'nin baytları indirilemedi. Bu nedenle **resmî CSV SHA-256'sı yoktur**; orijinal dosyanın bire bir dijital imzası iddia edilmez. Alan ve satır yeniden yapılandırmasındaki varsayımlar saklanmıştır.
- Sınanmış ayrıştırma: `Single-Family`, `Town Home`, `Apartment`, `Commercial`, `Duplex`, `Condo`, `Multi-Family`, `Mobile Home`, `Sales` kayıt türlerinden önceki kimlik biçimi; `csv` alıntılama kuralları. **2072/2072 satır 130 alan**, **0 tekrar kimlik**. Başka bir tarihte dosyanın güncellenmesi beklenebilir.
- Anonim toplu istatistik dışında site ID, lisanslı hane verisi veya bireysel tüketim serisi pakette yeniden yayımlanmaz. Kamu metadata kaynak metninin kendisi pakette tutulmaz.

## 2. Hesaplanan gerçek, fakat metadata-seviyesi sayımlar

| Koşul | Kayıt |
|---|---:|
| Toplam metadata satırı | 2072 |
| Metadata sütunu | 130 |
| `pv=yes` | 551 |
| `grid=yes` | 1078 |
| `solar=yes` | 405 |
| `pv`, `grid`, `solar` evet + bildirilen geçerli 1 dakikalık pencere ve pozitif erişilebilirlik | **385** |
| Adaylar arasında bildirilen erişilebilirlik en az %90 | **308** |
| Adaylar arasında bildirilen erişilebilirlik en az %95 | **258** |
| Adaylar arasında `battery1=yes` | **6** (tüm satırlarda 8) |
| Adaylar arasında `energy_storage_system=yes` | **1** (tüm satırlarda 4) |
| Adaylar arasında `active_record=yes` | **265** |

Beş eyaletin aday dağılımı: Texas 292, New York 53, Delaware 15, California 13, Colorado 12 (toplam 385). Bu sayımlar gerçek batarya SOC zaman serisini, kimyasını, kontratlı şebeke kapasitesini veya kontrolcü anahtarlama eylemini doğrulamaz. `egauge_1min_data_availability` bütün PV/grid/SOC kanallarının *aynı zamanlarda* bulunduğunu göstermez. Aynı hanelerin kayıt aralıkları ile kaynak-ayrıklık denetimi henüz yapılmadı.

## 3. Brazil STAR için yeni lisans bulgusu

Kaynak-özel Zenodo API URL'sinden çıkartılan bir yanıtın `metadata.license.id` değeri **`cc-by-4.0`** olarak görüldü:
https://zenodo.org/api/records/3959739
Bu, R27'de yalnız HTML Rights alanında boş görünen lisans bilgisini açıklığa kavuşturuyor. Üçüncü taraf batarya veri kataloğu da CC BY 4.0 bilgisini destekler:
https://astrolabe-analytics.github.io/public-battery-field-data/dashboard/

**Kanıt sınırlaması:** Zenodo API'nin özgün yanıt baytları bu çalışma ortamında tutulamadı; sonraki sorgu içerik çıkarıcısı bazen yalnız tanımlama metnini verdi. Dolayısıyla bu, kayıt-özel lisans kimliğine ilişkin güçlü kamu metadata bulgusudur, imzalı haricî erişim belgesi değildir. CC BY 4.0 tipik olarak atıf koşuluyla yeniden kullanıma ve türetmeye izin verir; her hâlükârda kullanıcı verisi/etik, dosya bütünlüğü ve fiziksel uygunluk ayrıca denetlenmelidir.

Orijinal 6.674.556 baytlık `Brazil_STAR_Microgrid_Monitoring.zip` doğrudan indirmeye tekrar çalışıldı fakat başarısız oldu. Yayıncı MD5: `b4f4bad22ba1d896937cfe555f41b25c`; gerçek ZIP SHA-256 **yoktur**. Ada tipi birimler için şebeke alış/satış ölçümü ve kontratlı grid cap belgelenmediğinden CRMT'nin dört fiziksel amacı **eşdeğer değildir**. Bu kaynak ancak izinli ikincil batarya/PV analizlerine aday olabilir.

## 4. Test, ön kayıt ve operasyonel karar

R19 sabit: C1/A1, B=K=10, 256 aday ve discovery her kol için 12.600; tam havuz TRAIN-AUDIT 60 blok. R25 kayıt-özel dış zaman kilidi ve 30 tohum güç onayı tamamlanmadı. Pecan Street'in üniversite lisansı için yazılı açıklaması gelmedi; mevcut Gmail e-posta taslağı **gönderilmedi**. Eski OpenCEM, OPSD ve diğer iç TEST'ler zaten araştırmacı tarafından görülmüş kayıtlar olmaya devam ediyor.

**SON DURUM: `NO_GO_NEW_INDEPENDENT_TEST`; `NO_R19_NEW_OPTIMIZATION_RUNS`; `NOT_NATIVE_GRID_PV_SOC_CERTIFIED`**. İlk fırsatta sağlayıcının tam veri sözlüğünü ve lisans/AI analizi iznini yazılı al, ardından tüm 4 kaybın simülatörde anlamını koruduğunu doğrula; bundan önce nihai hipotez farkı için p-değeri üretme.

## 5. Tekrarlanabilirlik

Gelecekte kamu CSV'sinin özgün baytları edinilirse:

```bash
python tools/public_cohort_audit.py public_metadata.csv --mode original --out independent_aggregate.json
pytest -q tests
python tools/verify_release.py
```

Metin çıkarıcıyla dönüştürülmüş tek satırlı metin için `--mode text_extractor_flattened` kullanılır. **Yerel dosyanın SHA-256 değeri, sağlayıcının özgün dosyasının SHA-256 değeri değildir**. R29 sonuç dosyası şu anda yalnız haklı şekilde kaynaklanmış toplu analitik kayıttır; sağlayıcının ham dosyası paket içinde dağıtılmaz.
