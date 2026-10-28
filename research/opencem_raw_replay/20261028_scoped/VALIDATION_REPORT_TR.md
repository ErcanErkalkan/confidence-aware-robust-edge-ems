# CRMT Adım 2 — OpenCEM ham ölçümden replay girişine bağımsız kapsamlı olmayan doğrulama

Tarih: 28 Ekim 2026. Kanıt sınıfı: **tarihsel mühendislik yeniden hesaplaması**. Bilimsel kapı: **NO_GO**.

## Kanıt kaynakları

- Değişmez OpenCEM kaynak referansı: `5884d253a5267fb240b7a8df6fa9e4d49a905167`.
- İncelenen iki gerçek kaynak dosya: `2025-08-a.csv`, `2025-08-b.csv`. Yerel bayt SHA-256, donmuş `RAW_19_SOURCE_HASHES.csv` kaydıyla iki dosyada da bire bir eşleşti.
- Donmuş kaynak–bin izi: `CRMT_EAAI_EXACT_BIN_LINEAGE_20261020.zip`, SHA-256 `bc8809c811c8538bde363dccd83f1096a01eb95e41daae3205bdbee1ace3be99`.

## Gerçekte yapılan işlem

Özgün CSV içindeki `read_ts`, `inverter`, `outsumw`, yük fazları ve PV kanalları yeniden okundu. Aynı `(read_ts,inverter)` tekrarları sinyal bazında ortalandı. Öncelikli yük kanalı `outsumw`; mevcut değilse fazların toplamı kullanıldı. Üç PV güç kanalı toplamından PV oluşturuldu. Negatif yük/PV ve eksik iki kanaldan herhangi birine sahip zaman binleri dışlandı. UTC temelinde 2 dakika gridine alındı; Asia/Shanghai (+08:00) yerel günlük blok anahtarları oluşturuldu. Bu, tarihsel dönüşümün koddan bağımsız bir yeniden uygulamasıdır.

- Ham dosyalardan **4.316 kabul edilmiş iki dakikalık kayıt** yeniden hesaplandı ve donmuş girişteki 6 blokla eşleştirildi.
- `load_kw`, `pv_kw`, `base_kw`, `n_load`, `n_pv`, `n_distinct_raw_timestamps` sütunlarında eşleşmeyen kayıt sayısı **0** (`atol=1e-10`, `rtol=0`).
- Yük için maksimum mutlak fark `1.1102230246251565e-16`, PV için `4.440892098500626e-16`, net güç için `2.220446049250313e-16`.
- Donmuş ilişkilendirmede iki kaynak dosyası için sırasıyla **3.132 + 7.264 = 10.396** ham satır–bin eşleşmesi fiziksel ham CSV satırından geri okunarak doğrulandı. Bu kapsamda geçersiz satır/anahtar/kanal-bulunma bayrağı yok.
- **4 tam (720 tick)** ve **2 kısmi (718 tick)** gün bulundu. Kısmi günler inv1 ve inv2 için 2025-08-30, tam günler her iki inverter için 2025-08-02 ve 2025-08-31.

## Sınırlar ve kabul kararı

**PASS — yalnız bu iki ham dosya ve bu altı donmuş tarihsel blok kapsamındaki değer eşitliği.** Bu dosya, 19 parçanın tümünün yeniden hesaplandığı, 381 tam günün tam doğrulandığı, özgün tarihsel kontrolcü tensorlarının bire bir yeniden üretildiği veya yeni bir gerçek EMS operatör testi yürütüldüğü anlamına gelmez. 406 blok toplamına ilişkin önceki sayım ve hash denetimleri ayrı tarihsel kayıtlardır. Tarihsel TEST olarak etiketlenmiş veriler yeni bağımsız TEST kabul edilemez. Kullanım hakları ve fiziksel onay ayrı engeller olarak kalır.

Bir sonraki teknik iş, kalan 17 kaynağın özgün baytlarını erişilebildiği ve izinli olduğu ölçüde tek tek içeri almak; aynı fail-closed script ile her ham dosya / ortak sınır blokları üzerinde değersel doğrulama yapmak; sonrasında yetkili tam günlük EMS simülasyonuna geçmektir.

## Yeniden üretim ve bütünlük

Uygulama: `validate_raw_to_replay_scoped.py`; girişler: iki orijinal CSV ve donmuş lineage ZIP. Çıkışlar: `SCOPED_RESULT.json`, `SCOPED_FULL_DAY_VALIDATION.csv`, `SCOPED_RAW_TO_REPLAY_COMPARISON.csv`. Orijinal dosyalarda hiçbir değişiklik yapılmadı. Hash'ler `SCOPE_HASH_MANIFEST.json` içinde.
